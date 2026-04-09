from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import json
import os
from app.services.websocket_manager import manager
from app.database.database import get_db
from sqlalchemy.orm import Session
from app.models.models import Event, Agent, Dispatch
from fpdf import FPDF
from datetime import datetime
import tempfile

router = APIRouter(tags=["Dashboard"])

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # We don't really expect clients to send data, but just in case
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@router.get("/logs")
def get_logs():
    if not os.path.exists("interactions.jsonl"):
        return []
    logs = []
    with open("interactions.jsonl", "r") as f:
        for line in f:
            if line.strip():
                logs.append(json.loads(line))
    return logs[::-1]  # Newest first

@router.get("/interactions", response_class=HTMLResponse)
def get_interactions():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>IA Interactions Log</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css" rel="stylesheet">
        <style>
            body { background-color: #0f172a; color: #f8fafc; font-family: monospace; }
            .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
            pre { margin: 0; white-space: pre-wrap; word-wrap: break-word; }
        </style>
    </head>
    <body class="h-screen w-screen p-6 flex flex-col">
        <header class="mb-4">
            <h1 class="text-2xl font-bold text-blue-400">🤖 AI Dispatch Reasoning Logs</h1>
            <p class="text-slate-400 text-sm">Raw JSON payloads and Gemini's evaluation</p>
        </header>
        <div id="logs-container" class="flex-1 overflow-y-auto space-y-4">
            <p class="text-slate-500">Cargando interacciones...</p>
        </div>
        <script>
            async function fetchLogs() {
                try {
                    const res = await fetch('/logs');
                    const data = await res.json();
                    const container = document.getElementById('logs-container');
                    container.innerHTML = '';
                    
                    if(data.length === 0) {
                        container.innerHTML = '<p class="text-slate-500">No hay logs registrados todavía.</p>';
                        return;
                    }

                    data.forEach(log => {
                        const date = new Date(log.timestamp).toLocaleString();
                        const el = document.createElement('div');
                        el.className = 'glass p-4 rounded-lg';
                        el.innerHTML = `
                            <div class="flex justify-between items-center mb-2 border-b border-slate-700 pb-2">
                                <span class="text-green-400 font-bold">${date}</span>
                                <span class="text-xs px-2 py-1 rounded ${log.ai_response.dispatch ? 'bg-red-500/20 text-red-400 border border-red-500/50' : 'bg-green-500/20 text-green-400 border border-green-500/50'}">
                                    DISPATCH: ${log.ai_response.dispatch ? 'YES' : 'NO'}
                                </span>
                            </div>
                            <div class="grid grid-cols-2 gap-4">
                                <div class="bg-slate-900 p-2 rounded text-xs border border-slate-700">
                                    <h3 class="text-slate-400 mb-1 border-b border-slate-700 pb-1">IN: Raw Payload</h3>
                                    <pre class="text-yellow-300">${JSON.stringify(log.payload, null, 2)}</pre>
                                </div>
                                <div class="bg-slate-900 p-2 rounded text-xs border border-slate-700">
                                    <h3 class="text-slate-400 mb-1 border-b border-slate-700 pb-1">OUT: AI Decision</h3>
                                    <pre class="text-blue-300">${JSON.stringify(log.ai_response, null, 2)}</pre>
                                </div>
                            </div>
                        `;
                        container.appendChild(el);
                    });
                } catch(e) {
                    console.error(e);
                }
            }
            setInterval(fetchLogs, 3000);
            fetchLogs();
        </script>
    </body>
    </html>
    """

@router.get("/reports/pdf/{event_id}")
def export_event_pdf(event_id: str, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        return JSONResponse({"error": "Event not found"}, status_code=404)
    
    dispatch = db.query(Dispatch).filter(Dispatch.event_id == event_id).first()
    agent = None
    if dispatch:
        agent = db.query(Agent).filter(Agent.id == dispatch.agent_id).first()

    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_fill_color(15, 23, 42)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_font("Arial", 'B', 24)
    pdf.set_text_color(59, 130, 246)
    pdf.text(10, 25, "NIGHTWATCH TACTICAL REPORT")
    
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(255, 255, 255)
    pdf.text(10, 33, f"Document ID: {event.event_id} | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    pdf.set_y(50)
    pdf.set_text_color(0, 0, 0)
    
    # Event Details
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "1. EVENT INFORMATION", ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 8, f"Type: {event.event_type.upper()}", ln=True)
    pdf.cell(0, 8, f"Status: {event.status.upper()}", ln=True)
    pdf.cell(0, 8, f"Priority: {event.priority.upper()}", ln=True)
    pdf.cell(0, 8, f"Timestamp: {event.timestamp}", ln=True)
    pdf.cell(0, 8, f"Location: {event.lat}, {event.lon}", ln=True)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "2. AI EVALUATION", ln=True)
    pdf.set_font("Arial", 'I', 11)
    pdf.multi_cell(0, 6, event.ai_reason or "No AI commentary available.")
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "3. DISPATCH LOGS", ln=True)
    pdf.set_font("Arial", '', 12)
    if agent:
        pdf.cell(0, 8, f"Assigned Unit: {agent.name}", ln=True)
        pdf.cell(0, 8, f"Dispatched At: {dispatch.assigned_at}", ln=True)
        pdf.cell(0, 8, f"Deployment Status: {dispatch.status.upper()}", ln=True)
    else:
        pdf.cell(0, 8, "No unit was dispatched for this event.", ln=True)

    # Footer
    pdf.set_y(-30)
    pdf.set_font("Arial", 'I', 8)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 10, "NIGHTWATCH AI Dispatcher - Proprietary Tactical Data - DO NOT DISTRIBUTE", align='C')

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        return FileResponse(tmp.name, filename=f"Report_{event.event_id}.pdf", media_type="application/pdf")

@router.get("/history", response_class=HTMLResponse)
def get_history_page():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>NIGHTWATCH - Historical Records</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css" rel="stylesheet">
        <style>
            body { background-color: #0f172a; color: #f8fafc; font-family: 'Segoe UI', sans-serif; }
            .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
            .btn-pdf { background: #3b82f6; transition: all 0.2s; }
            .btn-pdf:hover { background: #2563eb; transform: scale(1.05); }
        </style>
    </head>
    <body class="p-8">
        <div class="max-w-6xl mx-auto">
            <div class="flex justify-between items-center mb-8">
                <div>
                    <h1 class="text-3xl font-bold text-blue-400 tracking-wider">📜 HISTORICAL RECORDS</h1>
                    <p class="text-slate-400">Tactical event archive and resolution logs</p>
                </div>
                <div class="flex gap-4">
                    <a href="/interactions" class="px-4 py-2 bg-purple-900/30 rounded border border-purple-500/30 text-purple-200 hover:bg-purple-800/50 transition flex items-center gap-2">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                        REASONING LOGS
                    </a>
                    <a href="/dashboard" class="px-4 py-2 bg-slate-800 rounded border border-slate-700 hover:bg-slate-700 transition">← Back to Live Map</a>
                </div>
            </div>
            
            <div class="glass rounded-2xl overflow-hidden">
                <table class="w-full text-left">
                    <thead class="bg-slate-900/80 border-b border-slate-700">
                        <tr>
                            <th class="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400">Timestamp</th>
                            <th class="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400">ID</th>
                            <th class="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400">Type</th>
                            <th class="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400">Priority</th>
                            <th class="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400">Status</th>
                            <th class="px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-400">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="history-body" class="divide-y divide-slate-800">
                        <tr><td colspan="6" class="px-6 py-8 text-center text-slate-500 italic">Retrieving archive records...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            async function loadHistory() {
                try {
                    const res = await fetch('/events/history');
                    const data = await res.json();
                    const body = document.getElementById('history-body');
                    body.innerHTML = '';
                    
                    if(data.length === 0) {
                        body.innerHTML = '<tr><td colspan="6" class="px-6 py-8 text-center text-slate-500 italic">No historical records found.</td></tr>';
                        return;
                    }

                    data.forEach(ev => {
                        const date = new Date(ev.timestamp).toLocaleString();
                        const row = document.createElement('tr');
                        row.className = 'hover:bg-slate-800/30 transition';
                        row.innerHTML = `
                            <td class="px-6 py-4 text-sm font-mono">${date}</td>
                            <td class="px-6 py-4 text-sm font-bold text-blue-300">${ev.event_id}</td>
                            <td class="px-6 py-4"><span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-700 text-slate-200">${ev.event_type.toUpperCase()}</span></td>
                            <td class="px-6 py-4"><span class="text-xs ${ev.priority === 'high' ? 'text-red-400' : 'text-yellow-400'}">${ev.priority.toUpperCase()}</span></td>
                            <td class="px-6 py-4"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${ev.status === 'resolved' ? 'bg-green-900/40 text-green-400' : 'bg-red-900/40 text-red-400'} border border-current">${ev.status.toUpperCase()}</span></td>
                            <td class="px-6 py-4">
                                <a href="/reports/pdf/${ev.event_id}" target="_blank" class="btn-pdf px-3 py-1.5 rounded text-white text-xs font-bold flex items-center gap-2 w-max">
                                    <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M6 2a2 2 0 00-2 2v12a2 2 0 002 2h8a2 2 0 002-2V7.414A2 2 0 0015.414 6L12 2.586A2 2 0 0010.586 2H6zm5 6a1 1 0 10-2 0v3.586l-1.293-1.293a1 1 0 10-1.414 1.414l3 3a1 1 0 001.414 0l3-3a1 1 0 00-1.414-1.414L11 11.586V8z" clip-rule="evenodd"></path></svg>
                                    DOWNLOAD PDF
                                </a>
                            </td>
                        `;
                        body.appendChild(row);
                    });
                } catch(e) { console.error(e); }
            }
            loadHistory();
        </script>
    </body>
    </html>
    """

@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NIGHTWATCH - Tactical AI Dispatch</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            body { background-color: #0f172a; color: #f8fafc; overflow: hidden; margin: 0; padding: 0; }
            /* Map as background */
            #map { position: absolute; top: 0; left: 0; height: 100vh; width: 100vw; z-index: 0; background-color: #0f172a; }
            
            /* Overlay container */
            #ui-layer { position: absolute; top: 0; left: 0; height: 100vh; width: 100vw; z-index: 10; pointer-events: none; display: flex; flex-direction: column; }
            .pointer-events-auto { pointer-events: auto; }
            
            /* Glassmorphism */
            .glass { background: rgba(15, 23, 42, 0.75); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5); }
            
            /* Markers */
            .agent-marker { border-radius: 50%; border: 2px solid rgba(255,255,255,0.8); box-shadow: 0 0 15px rgba(0,0,0,0.8); }
            .agent-available { background-color: #10b981; }
            .agent-busy { background-color: #ef4444; }
            .agent-offline { background-color: #64748b; }
            
            .event-marker { 
                border-radius: 50%; 
                border: 2px solid #ef4444; 
                background-color: rgba(239, 68, 68, 0.8); 
                animation: radarPulse 2s infinite; 
            }
            @keyframes radarPulse { 
                0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.8); } 
                70% { box-shadow: 0 0 0 25px rgba(239, 68, 68, 0); } 
                100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); } 
            }
            
            /* Custom Scrollbar */
            ::-webkit-scrollbar { width: 4px; }
            ::-webkit-scrollbar-track { background: transparent; }
            ::-webkit-scrollbar-thumb { background: rgba(148, 163, 184, 0.3); border-radius: 2px; }
            ::-webkit-scrollbar-thumb:hover { background: rgba(148, 163, 184, 0.6); }
        </style>
    </head>
    <body>
        <!-- Map Background -->
        <div id="map"></div>

        <!-- UI Overlay Layer -->
        <div id="ui-layer">
            <!-- Header -->
            <header class="glass p-4 flex justify-between items-center pointer-events-auto border-b border-slate-700/50">
                <div class="flex items-center gap-3">
                    <svg class="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 11c0 3.517-1.009 6.799-2.753 9.571m-3.44-2.04l.054-.09A13.916 13.916 0 008 11a4 4 0 118 0c0 1.017-.07 2.019-.203 3m-2.118 6.844A21.88 21.88 0 0015.171 17m3.839 1.132c.645-2.266.99-4.659.99-7.132A8 8 0 008 4.07M3 15.364c.64-1.319 1-2.8 1-4.364 0-1.457.39-2.823 1.07-4"></path></svg>
                    <h1 class="text-2xl font-bold tracking-widest text-blue-400 uppercase">Nightwatch <span class="text-sm text-slate-400 font-light tracking-normal ml-2">Tactical Dispatch</span></h1>
                </div>
                <div class="flex gap-6 text-sm font-mono tracking-wider items-center">
                    <a href="/history" class="text-blue-400 hover:text-blue-300 border border-blue-500/30 px-3 py-1 rounded bg-blue-900/20 transition flex items-center gap-2">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                        HISTORY ARCHIVE
                    </a>
                    <div class="flex items-center gap-2"><span class="relative flex h-3 w-3"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span><span class="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span></span> ONLINE: <span id="count-online" class="text-green-400 font-bold">0</span></div>
                    <div class="flex items-center gap-2"><span class="w-3 h-3 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]"></span> BUSY: <span id="count-busy" class="text-red-400 font-bold">0</span></div>
                    <div class="flex items-center gap-2"><span class="w-3 h-3 rounded-full bg-slate-500"></span> OFFLINE: <span id="count-offline" class="text-slate-400 font-bold">0</span></div>
                </div>
            </header>

            <!-- Main Workspace -->
            <main class="flex-1 flex justify-between p-6 pointer-events-none overflow-hidden pb-8" style="height: calc(100vh - 72px);">
                
                <!-- Left Sidebar: Events & AI -->
                <div class="w-80 flex flex-col gap-4 h-full pointer-events-auto">
                    
                    <div class="glass rounded-xl p-4 flex-1 flex flex-col min-h-0 border border-red-900/30">
                        <h2 class="text-lg font-bold mb-3 border-b border-slate-700/50 pb-2 text-white flex items-center gap-2 uppercase tracking-wide shrink-0">
                            <svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                            Live Alerts
                        </h2>
                        <div id="events-list" class="flex-1 overflow-y-auto space-y-2 pr-1">
                            <p class="text-slate-500 text-sm italic font-mono">Monitoring signals...</p>
                        </div>
                    </div>

                    <div class="glass rounded-xl p-4 flex flex-col shrink-0 border border-purple-900/30">
                        <h2 class="text-lg font-bold mb-2 border-b border-slate-700/50 pb-2 text-purple-400 flex items-center gap-2 uppercase tracking-wide shrink-0">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                            AI Override
                        </h2>
                        <p class="text-[10px] text-slate-400 mb-3 font-mono">Inject raw payload to Gemini</p>
                        <div class="grid grid-cols-2 gap-2">
                            <button onclick="simulateAlarm('intrusion')" class="bg-purple-900/30 hover:bg-purple-800/80 border border-purple-500/50 text-purple-200 text-xs py-2 rounded transition shadow-[0_0_10px_rgba(168,85,247,0.1)]">INTRUSION</button>
                            <button onclick="simulateAlarm('panic')" class="bg-red-900/30 hover:bg-red-800/80 border border-red-500/50 text-red-200 text-xs py-2 rounded transition shadow-[0_0_10px_rgba(239,68,68,0.1)]">PANIC BTN</button>
                            <button onclick="simulateAlarm('battery')" class="bg-slate-800/50 hover:bg-slate-700/80 border border-slate-600/50 text-slate-300 text-xs py-2 rounded transition">BATTERY</button>
                            <button onclick="simulateAlarm('fire')" class="bg-orange-900/30 hover:bg-orange-800/80 border border-orange-500/50 text-orange-200 text-xs py-2 rounded transition shadow-[0_0_10px_rgba(249,115,22,0.1)]">FIRE</button>
                        </div>
                        <div id="ai-sim-result" class="mt-3 text-[10px] font-mono text-slate-300 bg-slate-900/80 p-2 rounded-lg hidden break-words border border-slate-700 overflow-y-auto max-h-24"></div>
                    </div>
                </div>

                <!-- Connection Status Overlay -->
                <div class="absolute bottom-4 left-1/2 transform -translate-x-1/2 glass px-4 py-1.5 rounded-full pointer-events-auto border border-blue-500/30 shadow-[0_0_20px_rgba(59,130,246,0.2)]">
                    <p class="font-mono text-[10px] text-blue-400 flex items-center gap-2">
                        <span class="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse"></span>
                        SECURE LINK ACTIVE
                    </p>
                </div>

                <!-- Right Sidebar: Agents & Admin -->
                <div class="w-80 flex flex-col gap-4 h-full pointer-events-auto">
                    <div class="glass rounded-xl p-4 flex-1 flex flex-col min-h-0 border border-cyan-900/30">
                        <h2 class="text-lg font-bold mb-3 border-b border-slate-700/50 pb-2 text-white flex items-center gap-2 uppercase tracking-wide shrink-0">
                            <svg class="w-5 h-5 text-cyan-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
                            Field Units
                        </h2>
                        <div id="agents-list" class="flex-1 overflow-y-auto space-y-2 pr-1">
                            <p class="text-slate-500 text-sm italic font-mono">Scanning grid...</p>
                        </div>
                    </div>

                    <div class="glass rounded-xl p-4 flex flex-col shrink-0 border border-blue-900/30">
                        <h2 class="text-lg font-bold mb-3 border-b border-slate-700/50 pb-2 text-blue-400 flex justify-between items-center uppercase tracking-wide shrink-0">
                            <div class="flex items-center gap-2">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                                Access Control
                            </div>
                        </h2>
                        <div class="flex gap-2 mb-2">
                            <input id="new-user-name" type="text" placeholder="Username" class="w-1/2 bg-slate-900/80 border border-slate-700 text-[11px] p-2 text-white rounded outline-none focus:border-blue-500 transition">
                            <input id="new-user-pwd" type="password" placeholder="Password" class="w-1/2 bg-slate-900/80 border border-slate-700 text-[11px] p-2 text-white rounded outline-none focus:border-blue-500 transition">
                        </div>
                        <div class="flex gap-2 mb-3">
                            <select id="new-user-role" class="w-1/2 bg-slate-900/80 border border-slate-700 text-[11px] p-2 text-white rounded outline-none focus:border-blue-500 transition cursor-pointer">
                                <option value="dispatcher">Dispatcher</option>
                                <option value="admin">Admin</option>
                                <option value="auditor">Auditor</option>
                                <option value="agent">Motorista</option>
                            </select>
                            <input id="new-user-agentid" type="number" placeholder="ID Patrulla" class="w-1/2 bg-slate-900/80 border border-slate-700 text-[11px] p-2 text-white rounded outline-none focus:border-blue-500 transition" title="Solo si rol es Motorista">
                        </div>
                        <button onclick="createUser()" class="w-full bg-blue-600/80 hover:bg-blue-500 text-white font-bold py-2 rounded text-[11px] transition border border-blue-400/50 shadow-[0_0_15px_rgba(37,99,235,0.3)]">CREATE CREDENTIAL</button>
                    </div>
                </div>
            </main>
        </div>

        <!-- Dispatch Modal -->
        <div id="dispatch-modal" class="fixed inset-0 bg-slate-900/80 backdrop-blur-sm hidden flex justify-center items-center z-[2000]">
            <div class="glass p-8 rounded-2xl w-[400px] relative shadow-2xl border border-blue-500/30">
                <h2 class="text-2xl font-bold mb-2 text-white flex items-center gap-2">
                    <svg class="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 19v-8.93a2 2 0 01.89-1.664l7-4.666a2 2 0 012.22 0l7 4.666A2 2 0 0121 10.07V19M3 19a2 2 0 002 2h14a2 2 0 002-2M3 19l6.75-4.5M21 19l-6.75-4.5M3 10l6.75 4.5M21 10l-6.75 4.5m0 0l-1.14.76a2 2 0 01-2.22 0l-1.14-.76"></path></svg>
                    MANUAL DISPATCH
                </h2>
                <p id="dispatch-agent-name" class="text-sm text-blue-300 mb-6 font-mono tracking-wide bg-blue-900/30 p-2 rounded inline-block"></p>
                <textarea id="dispatch-message" rows="4" class="w-full bg-slate-900/90 border border-slate-600 rounded-lg p-3 text-sm text-white mb-6 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none resize-none transition" placeholder="Enter tactical briefing or emergency details..."></textarea>
                <div class="flex gap-3 justify-end">
                    <button onclick="closeDispatchModal()" class="px-5 py-2.5 text-xs tracking-wider uppercase bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-300 font-bold transition border border-slate-600">ABORT</button>
                    <button onclick="submitManualDispatch()" class="px-5 py-2.5 text-xs tracking-wider uppercase bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-bold transition shadow-[0_0_15px_rgba(37,99,235,0.5)] border border-blue-400/50">TRANSMIT</button>
                </div>
            </div>
        </div>

        <script>
            // Init Map (Zoom out a bit for full screen view)
            const map = L.map('map', { zoomControl: false }).setView([14.6349, -90.5155], 14);
            L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                attribution: '&copy; <a href="https://carto.com/">CARTO</a>'
            }).addTo(map);
            L.control.zoom({ position: 'bottomright' }).addTo(map);

            // -------- AI SIMULATOR ---------
            async function simulateAlarm(type) {
                const resultBox = document.getElementById('ai-sim-result');
                resultBox.classList.remove('hidden');
                resultBox.innerHTML = "Injecting payload to Gemini...";
                
                const randLat = 14.6 + (Math.random() * 0.05 - 0.025);
                const randLon = -90.52 + (Math.random() * 0.05 - 0.025);

                const payloadMap = {
                    'intrusion': { client: "Bodega Principal", zone: "Puerta Trasera", code: "E130", desc: "Burglary Alarm", lat: randLat, lon: randLon },
                    'panic': { client: "Oficinas Centrales", zone: "Recepción", code: "E120", desc: "Panic Button Pressed", lat: randLat, lon: randLon },
                    'battery': { client: "Sucursal Norte", zone: "Panel", code: "E302", desc: "Low System Battery", lat: randLat, lon: randLon },
                    'fire': { client: "Data Center", zone: "Site A", code: "E110", desc: "Fire Alarm", lat: randLat, lon: randLon }
                };

                try {
                    const res = await fetch('/events/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payloadMap[type])
                    });
                    const data = await res.json();
                    
                    let color = data.dispatched ? 'text-red-400 font-bold' : 'text-yellow-400';
                    resultBox.innerHTML = `
                        <span class="${color}">ACTION: ${data.dispatched ? 'DISPATCHED' : 'IGNORED'}</span><br>
                        <span class="text-slate-400">DETAIL: ${data.message}</span>
                    `;
                    fetchData(); 
                } catch(e) {
                    resultBox.innerHTML = `<span class="text-red-500">SYS_ERR: ${e}</span>`;
                }
            }

            // -------- EVENTS MANAGER ---------
            async function deleteEvent(id) {
                if(!confirm("¿Deseas cerrar y borrar esta alerta del sistema manualmente?")) return;
                try {
                    const res = await fetch(`/events/${id}`, { method: 'DELETE' });
                    if(res.ok) fetchData();
                    else alert("Error cerrando alerta.");
                } catch(e) {
                    console.error("Error al borrar evento", e);
                }
            }

            // -------- USER MANAGER ---------
            async function createUser() {
                const un = document.getElementById('new-user-name').value;
                const pw = document.getElementById('new-user-pwd').value;
                const rol = document.getElementById('new-user-role').value;
                const aid = document.getElementById('new-user-agentid').value;

                if (!un || !pw) {
                    alert("Credentials required."); return;
                }
                
                const payload = {
                    username: un,
                    password: pw,
                    role: rol,
                    agent_id: (rol === 'agent' && aid) ? parseInt(aid) : null
                };

                try {
                    const res = await fetch('/auth/users', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    
                    const data = await res.json();
                    if(res.ok) {
                        alert(`Access granted. User ${data.username} registered as ${data.role}`);
                        document.getElementById('new-user-name').value = '';
                        document.getElementById('new-user-pwd').value = '';
                    } else {
                        alert(`Err: ${data.detail || JSON.stringify(data)}`);
                    }
                } catch (e) {
                    alert("Network Error: " + e);
                }
            }

            let agentMarkers = {};
            let eventMarkers = {};
            let selectedAgentId = null;

            function openDispatchModal(id, name) {
                selectedAgentId = id;
                document.getElementById('dispatch-agent-name').innerText = `TARGET: ${name}`;
                document.getElementById('dispatch-message').value = '';
                document.getElementById('dispatch-modal').classList.remove('hidden');
            }

            function closeDispatchModal() {
                document.getElementById('dispatch-modal').classList.add('hidden');
                selectedAgentId = null;
            }

            async function submitManualDispatch() {
                if (!selectedAgentId) return;
                const msg = document.getElementById('dispatch-message').value;
                if (!msg) {
                    alert("Require transmission body.");
                    return;
                }
                
                try {
                    const res = await fetch(`/agents/${selectedAgentId}/dispatch_manual`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: msg })
                    });
                    const data = await res.json();
                    if (data.status === 'success') {
                        alert(`Transmission Sent.\nFCM: ${data.push_sent ? 'OK' : 'FAIL'} | WA: ${data.whatsapp_sent ? 'OK' : 'FAIL'}`);
                        closeDispatchModal();
                        fetchData();
                    } else {
                        alert("Err: " + JSON.stringify(data));
                    }
                } catch (e) {
                    console.error(e);
                    alert("Link failure.");
                }
            }

            function createCustomIcon(status, isEvent=false) {
                let className = isEvent ? 'event-marker' : `agent-marker agent-${status}`;
                return L.divIcon({
                    className: className,
                    iconSize: isEvent ? [20, 20] : [12, 12],
                    iconAnchor: isEvent ? [10, 10] : [6, 6]
                });
            }

            async function changeAgentStatus(agentId, newStatus) {
                try {
                    const res = await fetch(`/agents/${agentId}/status`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ status: newStatus })
                    });
                    if (res.ok) {
                        fetchData(); 
                    } else {
                        alert("Status update failed");
                    }
                } catch (e) {
                    console.error("Status err:", e);
                }
            }

            async function fetchData() {
                try {
                    const agentsRes = await fetch('/agents/');
                    const agents = await agentsRes.json();
                    
                    let online = 0, busy = 0, offline = 0;
                    const agentsList = document.getElementById('agents-list');
                    agentsList.innerHTML = '';

                    agents.forEach(agent => {
                        if (agent.status === 'available') online++;
                        else if (agent.status === 'busy') busy++;
                        else offline++;

                        if (agentMarkers[agent.id]) {
                            agentMarkers[agent.id].setLatLng([agent.lat, agent.lon]);
                            agentMarkers[agent.id].setIcon(createCustomIcon(agent.status));
                            agentMarkers[agent.id].setPopupContent(`<div class="font-mono text-xs text-slate-800"><b>ID: ${agent.name}</b><br>STS: ${agent.status.toUpperCase()}</div>`);
                        } else {
                            const marker = L.marker([agent.lat, agent.lon], {icon: createCustomIcon(agent.status)})
                                .addTo(map)
                                .bindPopup(`<div class="font-mono text-xs text-slate-800"><b>ID: ${agent.name}</b><br>STS: ${agent.status.toUpperCase()}</div>`);
                            agentMarkers[agent.id] = marker;
                        }

                        const statusColors = {
                            'available': 'text-green-400',
                            'busy': 'text-red-400',
                            'offline': 'text-slate-400'
                        };
                        const colorClass = statusColors[agent.status] || 'text-white';
                        
                        const el = document.createElement('div');
                        el.className = 'bg-slate-800/60 p-3 rounded-lg border border-slate-700 hover:border-slate-500 transition shadow-sm';
                        el.innerHTML = `
                            <div class="flex justify-between items-center mb-2">
                                <span class="font-bold text-sm text-blue-100 flex items-center gap-2">
                                    <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
                                    ${agent.name}
                                </span>
                                <span class="text-[10px] font-mono tracking-widest ${colorClass} bg-slate-900 px-2 py-0.5 rounded border border-slate-700">${agent.status.toUpperCase()}</span>
                            </div>
                            <div class="flex gap-1.5 mt-3">
                                <button onclick="changeAgentStatus(${agent.id}, 'available')" class="flex-1 text-[10px] uppercase tracking-wider bg-green-900/30 hover:bg-green-800/80 border border-green-700/50 py-1.5 rounded transition text-green-200">Avail</button>
                                <button onclick="changeAgentStatus(${agent.id}, 'busy')" class="flex-1 text-[10px] uppercase tracking-wider bg-red-900/30 hover:bg-red-800/80 border border-red-700/50 py-1.5 rounded transition text-red-200">Busy</button>
                                <button onclick="changeAgentStatus(${agent.id}, 'offline')" class="flex-1 text-[10px] uppercase tracking-wider bg-slate-800/50 hover:bg-slate-700 border border-slate-600/50 py-1.5 rounded transition text-slate-300">Off</button>
                            </div>
                            <div class="mt-2">
                                <button onclick="openDispatchModal(${agent.id}, '${agent.name}')" class="w-full text-xs bg-blue-600/80 hover:bg-blue-500 py-2 rounded transition text-white font-bold tracking-widest border border-blue-400/50 shadow-[0_0_10px_rgba(37,99,235,0.2)]">DISPATCH UNIT</button>
                            </div>
                        `;
                        agentsList.appendChild(el);
                    });

                    document.getElementById('count-online').innerText = online;
                    document.getElementById('count-busy').innerText = busy;
                    document.getElementById('count-offline').innerText = offline;

                    const eventsRes = await fetch('/events/');
                    if (eventsRes.ok) {
                        const events = await eventsRes.json();
                        const eventsList = document.getElementById('events-list');
                        eventsList.innerHTML = '';
                        
                        if(events.length === 0) {
                            eventsList.innerHTML = '<p class="text-slate-500 text-sm font-mono italic">No active alerts.</p>';
                        }

                        // Limpiar marcadores viejos del mapa
                        const incomingIds = new Set(events.map(e => e.event_id));
                        for (let id in eventMarkers) {
                            if (!incomingIds.has(id)) {
                                map.removeLayer(eventMarkers[id]);
                                delete eventMarkers[id];
                            }
                        }

                        events.forEach(ev => {
                            if (!eventMarkers[ev.event_id]) {
                                const marker = L.marker([ev.lat, ev.lon], {icon: createCustomIcon('', true)})
                                    .addTo(map)
                                    .bindPopup(`<div class="font-mono text-xs text-red-800"><b>ALERT: ${ev.event_type.toUpperCase()}</b><br>ID: ${ev.event_id}</div>`);
                                eventMarkers[ev.event_id] = marker;
                            }
                            
                            const el = document.createElement('div');
                            el.className = 'bg-slate-900/60 p-3 rounded-lg border-l-4 border-l-red-500 border border-slate-700 hover:bg-slate-800 cursor-pointer transition relative group';
                            el.innerHTML = `
                                <div class="flex justify-between items-start mb-1 pr-6">
                                    <span class="font-bold text-red-400 text-sm tracking-wide">${ev.event_type.toUpperCase()}</span>
                                    <span class="text-[10px] text-slate-400 font-mono">${new Date(ev.timestamp).toLocaleTimeString()}</span>
                                </div>
                                <div class="text-[10px] text-slate-400 font-mono mb-1">EV_ID: ${ev.event_id}</div>
                                <div class="text-[10px] text-slate-500 font-mono flex justify-between">
                                    <span>PRI: ${ev.priority}</span>
                                    <span>LOC: ${ev.lat.toFixed(3)}, ${ev.lon.toFixed(3)}</span>
                                </div>
                                <button onclick="deleteEvent('${ev.event_id}')" class="absolute top-2 right-2 text-slate-600 hover:text-red-500 transition opacity-0 group-hover:opacity-100" title="Resolve Alert">
                                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                                </button>
                            `;
                            eventsList.appendChild(el);
                        });
                    }

                } catch (error) {
                    console.error("Link error:", error);
                }
            }

            function connectWebSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
                
                ws.onopen = function() {
                    console.log('Tactical link established.');
                };

                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    console.log('Signal received:', data);
                    if (data.type === 'refresh') {
                        fetchData();
                    }
                };
                
                ws.onerror = function(err) {
                    console.error('Comms error:', err);
                };

                ws.onclose = function() {
                    console.log('WS link lost. Retrying in 3s...');
                    setTimeout(connectWebSocket, 3000);
                };
            }
            
            fetchData();
            connectWebSocket();
        </script>
    </body>
    </html>
    """
