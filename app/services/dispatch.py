import math
import os
import json
import uuid
import requests
import firebase_admin
from firebase_admin import credentials, messaging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.models import Agent, Dispatch, Event
from twilio.rest import Client

api_key = os.getenv("GEMINI_API_KEY")

# Twilio Credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
TWILIO_TARGET_NUMBER = os.getenv("TWILIO_TARGET_NUMBER")  # Número del motorista (por ahora uno general para pruebas)

def send_whatsapp_notification(agent: Agent, event_obj: Event, ai_reason: str):
    """Envía un WhatsApp vía Twilio al motorista despachado con la ruta de Google Maps."""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_TARGET_NUMBER:
        print("Twilio no está configurado. Faltan variables en .env")
        return False

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={event_obj.lat},{event_obj.lon}"
        
        msg_body = (
            f"🚨 *NUEVO DESPACHO AI-911*\n"
            f"Agente: {agent.name}\n"
            f"Tipo: *{str(event_obj.event_type).upper()}*\n\n"
            f"Evaluación IA: {ai_reason}\n\n"
            f"📍 *Ruta:* {maps_url}"
        )

        message = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            body=msg_body,
            to=TWILIO_TARGET_NUMBER
        )
        print(f"WhatsApp enviado a {TWILIO_TARGET_NUMBER} (SID: {message.sid})")
        return True
    except Exception as e:
        print(f"Error enviando WhatsApp: {e}")
        return False

# Inicializar Firebase Admin SDK (Cargar desde la raíz del proyecto)
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("firebase-key.json")
        firebase_admin.initialize_app(cred)
        print("✔️ Firebase Admin inicializado correctamente en el servicio de despacho.")
except Exception as e:
    print(f"⚠️ Alerta: No se pudo inicializar Firebase Admin: {e}. (Ignora esto si no usas notificaciones Push)")

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_driving_eta(lat1, lon1, lat2, lon2):
    """
    Usa la API pública de OSRM (Open Source Routing Machine) para calcular
    el tiempo real de manejo en lugar de distancia en línea recta.
    Si falla, cae en la fórmula de Haversine por seguridad.
    """
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            data = response.json()
            if data.get("routes") and len(data["routes"]) > 0:
                duration_seconds = data["routes"][0].get("duration", float('inf'))
                distance_meters = data["routes"][0].get("distance", float('inf'))
                return duration_seconds, distance_meters / 1000.0  # en km
    except Exception as e:
        print(f"OSRM Error: {e}, falling back to haversine")
    
    # Fallback to haversine distance
    dist = haversine(lat1, lon1, lat2, lon2)
    # Estimate time assuming 40 km/h average speed in city
    duration_seconds = (dist / 40.0) * 3600
    return duration_seconds, dist

def send_push_notification(agent: Agent, event_obj: Event, message_text: str):
    """Envía la notificación push a la unidad asignada vía Firebase, incluyendo coordenadas."""
    if not agent.fcm_token:
        print(f"⚠️ No se pudo enviar Push a {agent.name}: Falta token FCM.")
        return False
    
    try:
        message = messaging.Message(
            data={
                "type": "EMERGENCY_DISPATCH",
                "event_id": str(event_obj.event_id),
                "title": "🚨 ¡NUEVO DESPACHO ASIGNADO!",
                "message": message_text,
                "lat": str(event_obj.lat),
                "lon": str(event_obj.lon),
                "event_type": str(event_obj.event_type)
            },
            token=agent.fcm_token,
        )
        response = messaging.send(message)
        print(f"✔️ Notificación enviada a {agent.name} (MsgID: {response})")
        return True
    except Exception as e:
        print(f"❌ Error enviando notificación a {agent.name}: {e}")
        return False

def parse_and_evaluate_with_ai(payload):
    if not api_key or api_key == "your_gemini_api_key_here":
        print("Fallback: No API key")
        return {
            "parsed_event": {
                "event_id": f"RAW-{uuid.uuid4().hex[:6].upper()}",
                "event_type": "unknown",
                "lat": 14.6349,
                "lon": -90.5155,
                "priority": "low"
            },
            "dispatch": False,
            "reason": "Fallback: cannot parse raw JSON without AI key"
        }
        
    prompt = f"""
    You are an elite AI security dispatcher. You receive raw JSON payloads from various alarm systems (Ajax, DSC, generic webhooks, legacy platforms, etc.).
    Your job is to parse the payload, extract the core event details, and decide if a patrol unit should be dispatched.

    Raw Payload:
    {json.dumps(payload)}

    Rules for Dispatch:
    - "panic", "intrusion", "fire", or "medical" are high priority and require dispatch.
    - "maintenance", "low_battery", "test" should NOT require dispatch.
    - If priority is "low" or unknown, reject unless the event context implies danger.
    - If coordinates (lat/lon) are missing, infer from address or default to 14.6349, -90.5155 (Guatemala City center).
    - If an event ID isn't provided, generate a short 6-character unique ID like "EVT-XYZ".
    
    Respond ONLY with a valid JSON object in this exact format:
    {{
        "parsed_event": {{
            "event_id": "string",
            "event_type": "string (e.g. intrusion, panic, medical, maintenance, test)",
            "lat": float,
            "lon": float,
            "priority": "high or low"
        }},
        "dispatch": true or false,
        "reason": "Short explanation of your parsing and decision"
    }}
    """
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2}
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=15)
        response.raise_for_status()
        
        res_json = response.json()
        text = res_json.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        print(f"AI Error: {e}")
        return {
            "parsed_event": {
                "event_id": f"ERR-{uuid.uuid4().hex[:6].upper()}",
                "event_type": "error",
                "lat": 14.6349,
                "lon": -90.5155,
                "priority": "low"
            },
            "dispatch": False,
            "reason": f"AI Parsing failed: {str(e)}"
        }

def process_and_dispatch_raw_event(db: Session, payload: dict):
    ai_response = parse_and_evaluate_with_ai(payload)

    with open("interactions.jsonl", "a") as f:
        f.write(json.dumps({"timestamp": datetime.utcnow().isoformat(), "payload": payload, "ai_response": ai_response}) + "\n")

    parsed = ai_response.get("parsed_event", {})
    should_dispatch = ai_response.get("dispatch", False)
    ai_reason = ai_response.get("reason", "Unknown reason")

    event_id = parsed.get("event_id", f"EVT-{uuid.uuid4().hex[:6].upper()}")
    
    # Save parsed event to DB
    existing = db.query(Event).filter(Event.event_id == event_id).first()
    if not existing:
        new_event = Event(
            event_id=event_id,
            event_type=parsed.get("event_type", "unknown"),
            lat=parsed.get("lat", 14.6349),
            lon=parsed.get("lon", -90.5155),
            priority=parsed.get("priority", "low"),
            ai_reason=ai_reason,
            status="active" if should_dispatch else "rejected",
            timestamp=datetime.utcnow()
        )
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        event_obj = new_event
    else:
        event_obj = existing
        event_obj.status = "active" if should_dispatch else "rejected"
        event_obj.ai_reason = ai_reason
        db.commit()

    if not should_dispatch:
        return {
            "event_id": event_id,
            "dispatched": False,
            "message": f"AI Rejected: {ai_reason}"
        }

    # Find nearest agent
    time_threshold = datetime.utcnow() - timedelta(seconds=60)
    available_agents = db.query(Agent).filter(
        Agent.status == "available",
        Agent.last_update >= time_threshold
    ).all()

    if not available_agents:
        return {
            "event_id": event_id,
            "dispatched": False,
            "message": f"AI Approved ({ai_reason}) BUT No available agents nearby or with recent location"
        }

    nearest_agent = None
    min_eta = float('inf')
    chosen_dist = 0

    for agent in available_agents:
        eta_seconds, dist_km = get_driving_eta(event_obj.lat, event_obj.lon, agent.lat, agent.lon)
        if eta_seconds < min_eta:
            min_eta = eta_seconds
            chosen_dist = dist_km
            nearest_agent = agent

    if not nearest_agent:
        return {
            "event_id": event_id,
            "dispatched": False,
            "message": "Could not determine nearest agent"
        }

    # Crear el despacho en BD
    dispatch = Dispatch(
        event_id=event_obj.event_id,
        agent_id=nearest_agent.id,
        status="assigned"
    )
    
    nearest_agent.status = "busy"
    
    db.add(dispatch)
    db.commit()
    db.refresh(dispatch)

    # MANDAR NOTIFICACIÓN REAL (Firebase Push)
    dispatch_msg = f"Evento: {event_obj.event_type} | ID: {event_id} | Razón: {ai_reason}"
    push_sent = send_push_notification(nearest_agent, event_obj, dispatch_msg)

    # Enviar WhatsApp por Twilio
    whatsapp_sent = send_whatsapp_notification(nearest_agent, event_obj, ai_reason)

    return {
        "event_id": event_id,
        "dispatched": True,
        "agent": nearest_agent,
        "push_notified": push_sent,
        "whatsapp_sent": whatsapp_sent,
        "message": f"AI: '{ai_reason}'. Agent {nearest_agent.name} dispatched (ETA: {int(min_eta/60)} min / {chosen_dist:.2f} km). Push sent: {push_sent}, WA sent: {whatsapp_sent}"
    }