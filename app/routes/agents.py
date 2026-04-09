from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.database.database import get_db
from app.schemas.schemas import AgentResponse, LocationUpdate, AgentRegistration
from app.models.models import Agent, Event, Dispatch
from app.services.websocket_manager import manager
from app.services.dispatch import send_push_notification, send_whatsapp_notification
import asyncio
import uuid

router = APIRouter(prefix="/agents", tags=["Agents"])

class StatusUpdate(BaseModel):
    status: str

class ManualDispatchPayload(BaseModel):
    message: str
    lat: Optional[float] = None
    lon: Optional[float] = None

async def notify_clients():
    print("📡 Broadcasting refresh signal to all operators...")
    await manager.broadcast({"type": "refresh"})

@router.get("/", response_model=List[AgentResponse])
def get_agents(db: Session = Depends(get_db)):
    return db.query(Agent).all()

@router.post("/{agent_id}/register", response_model=AgentResponse)
def register_agent_token(agent_id: int, registration: AgentRegistration, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.fcm_token = registration.fcm_token
    db.commit()
    db.refresh(agent)
    
    return agent

@router.put("/{agent_id}/location", response_model=AgentResponse)
def update_agent_location(agent_id: int, location: LocationUpdate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.lat = location.lat
    agent.lon = location.lon
    agent.last_update = datetime.utcnow()
    
    db.commit()
    db.refresh(agent)
    background_tasks.add_task(notify_clients)
    
    return agent

@router.put("/{agent_id}/status", response_model=AgentResponse)
def update_agent_status(agent_id: int, status_update: StatusUpdate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    valid_statuses = ["available", "busy", "offline"]
    if status_update.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.status = status_update.status
    agent.last_update = datetime.utcnow()
    
    db.commit()
    db.refresh(agent)
    background_tasks.add_task(notify_clients)
    
    return agent

@router.post("/{agent_id}/dispatch_manual")
def dispatch_manual(agent_id: int, payload: ManualDispatchPayload, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    event_lat = payload.lat if payload.lat is not None else agent.lat
    event_lon = payload.lon if payload.lon is not None else agent.lon

    new_event = Event(
        event_id=f"MAN-{uuid.uuid4().hex[:6].upper()}",
        event_type="manual",
        lat=event_lat,
        lon=event_lon,
        priority="high",
        timestamp=datetime.utcnow()
    )
    db.add(new_event)
    
    dispatch = Dispatch(
        event_id=new_event.event_id,
        agent_id=agent.id,
        status="assigned",
        assigned_at=datetime.utcnow()
    )
    
    agent.status = "busy"
    db.add(dispatch)
    db.commit()
    db.refresh(new_event)
    db.refresh(agent)
    
    push_sent = send_push_notification(agent, new_event, payload.message)
    wa_sent = send_whatsapp_notification(agent, new_event, payload.message)
    
    background_tasks.add_task(notify_clients)
    
    return {
        "status": "success",
        "message": "Manual dispatch sent",
        "push_sent": push_sent,
        "whatsapp_sent": wa_sent
    }

@router.post("/{agent_id}/report")
async def upload_report(agent_id: int, photo: UploadFile = File(None), message: str = Form(""), db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Cerrar el despacho y borrar el evento activo para limpiar el mapa
    active_dispatch = db.query(Dispatch).filter(Dispatch.agent_id == agent_id, Dispatch.status == "assigned").first()
    if active_dispatch:
        active_dispatch.status = "completed"
        event_to_clear = db.query(Event).filter(Event.event_id == active_dispatch.event_id).first()
        if event_to_clear:
            db.delete(event_to_clear)
        db.commit()

    # Check if we got a photo
    filename = None
    if photo:
        filename = f"report_{agent_id}_{uuid.uuid4().hex[:8]}.jpg"
        print(f"Received photo {photo.filename}, mocking save as {filename}")
        
    print(f"Report received from {agent.name}: {message}")
    
    # Forzar actualización del Web Dashboard
    asyncio.create_task(manager.broadcast({"type": "refresh"}))
    
    return {
        "status": "success", 
        "message": "Report uploaded successfully", 
        "agent": agent.name,
        "photo_saved": bool(photo)
    }
