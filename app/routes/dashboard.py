from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
import json
import os
from app.services.websocket_manager import manager

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

@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NIGHTWATCH - Dispatch Dashboard</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            body { background-color: #0f172a; color: #f8fafc; }
            #map { height: 100%; width: 100%; border-radius: 0.5rem; border: 1px solid #334155; }
            .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
            .agent-marker { border-radius: 50%; border: 2px solid white; box-shadow: 0 0 10px rgba(0,0,0,0.5); }
            .agent-available { background-color: #10b981; }
            .agent-busy { background-color: #ef4444; }
            .agent-offline { background-color: #64748b; }
            .event-marker { border-radius: 50%; border: 2px solid white; background-color: #f59e0b; animation: pulse 1.5s infinite; }
            @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.7); } 70% { box-shadow: 0 0 0 15px rgba(245, 158, 11, 0); } 100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); } }
            
            /* Custom Scrollbar */
            ::-webkit-scrollbar { width: 6px; }
            ::-webkit-scrollbar-track { background: transparent; }
            ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
            ::-webkit-scrollbar-thumb:hover { background: #475569; }
        </style>
    </head>
    <body class="h-screen w-screen overflow-hidden flex flex-col">
        <!-- Header -->
        <header class="glass p-4 flex justify-between items-center shadow-lg z-10">
            <div class="flex items-center gap-3">
                <span class="text-3xl">🚓</span>
                <h1 class="text-2xl font-bold tracking-wider text-blue-400">NIGHTWATCH <span class="text-sm text-slate-400 font-normal">| AI Dispatcher</span></h1>
            </div>
            <div class="flex gap-4 text-sm">
                <div class="flex items-center gap-2"><span class="w-3 h-3 rounded-full bg-green-500"></span> Online: <span id="count-online">0</span></div>
                <div class="flex items-center gap-2"><span class="w-3 h-3 rounded-full bg-red-500"></span> Busy: <span id="count-busy">0</span></div>
                <div class="flex items-center gap-2"><span class="w-3 h-3 rounded-full bg-slate-500"></span> Offline: <span id="count-offline">0</span></div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="flex-1 flex p-4 gap-4">
            <!-- Sidebar: Events -->
            <div class="w-1/4 glass rounded-lg p-4 flex flex-col">
                <h2 class="text-xl font-semibold mb-4 border-b border-slate-700 pb-2">🚨 Live Events</h2>
                <div id="events-list" class="flex-1 overflow-y-auto space-y-3 pr-2">
                    <p class="text-slate-400 text-sm italic">Cargando eventos...</p>
                </div>
            </div>

            <!-- Map -->
            <div class="w-2/4 relative">
                <div id="map"></div>
                <!-- Status Overlay -->
                <div class="absolute top-4 right-4 glass p-3 rounded-lg z-[1000] text-sm">
                    <p class="font-mono text-green-400">⚡ Live Connection</p>
                    <p class="text-slate-400 text-xs mt-1">Updating every 3s</p>
                </div>
            </div>

            <!-- Sidebar: Agents -->
            <div class="w-1/4 glass rounded-lg p-4 flex flex-col">
                <h2 class="text-xl font-semibold mb-4 border-b border-slate-700 pb-2">👮 Agents Control</h2>
                <div id="agents-list" class="flex-1 overflow-y-auto space-y-3 pr-2">
                    <p class="text-slate-400 text-sm italic">Cargando agentes...</p>
                </div>
            </div>
        </main>

        <!-- Dispatch Modal -->
        <div id="dispatch-modal" class="fixed inset-0 bg-black bg-opacity-70 hidden flex justify-center items-center z-[2000]">
            <div class="glass p-6 rounded-lg w-96 relative shadow-2xl">
                <h2 class="text-xl font-bold mb-2 text-blue-400">Despacho Manual</h2>
                <p id="dispatch-agent-name" class="text-sm text-slate-300 mb-4 font-mono"></p>
                <textarea id="dispatch-message" rows="3" class="w-full bg-slate-900 border border-slate-700 rounded p-3 text-sm text-white mb-4 focus:border-blue-500 outline-none" placeholder="Motivo o mensaje de la emergencia..."></textarea>
                <div class="flex gap-2 justify-end mt-2">
                    <button onclick="closeDispatchModal()" class="px-4 py-2 text-sm bg-slate-700 hover:bg-slate-600 rounded text-white font-medium transition">Cancelar</button>
                    <button onclick="submitManualDispatch()" class="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 rounded text-white font-bold transition shadow-lg">Enviar Push</button>
                </div>
            </div>
        </div>

        <script>
            // Init Map
            const map = L.map('map').setView([14.6349, -90.5155], 13);
            L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                attribution: '&copy; <a href="https://carto.com/">CARTO</a>'
            }).addTo(map);


            let agentMarkers = {};
            let eventMarkers = {};
            let selectedAgentId = null;

            function openDispatchModal(id, name) {
                selectedAgentId = id;
                document.getElementById('dispatch-agent-name').innerText = `Unidad Destino: ${name}`;
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
                    alert("Por favor escribe el motivo del despacho.");
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
                        alert(`¡Despacho enviado!\nPush: ${data.push_sent ? 'OK' : 'Fallo'} | WA: ${data.whatsapp_sent ? 'OK' : 'Fallo'}`);
                        closeDispatchModal();
                        fetchData();
                    } else {
                        alert("Error: " + JSON.stringify(data));
                    }
                } catch (e) {
                    console.error(e);
                    alert("Error conectando con el servidor.");
                }
            }

            function createCustomIcon(status, isEvent=false) {
                let className = isEvent ? 'event-marker' : `agent-marker agent-${status}`;
                return L.divIcon({
                    className: className,
                    iconSize: isEvent ? [20, 20] : [15, 15]
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
                        fetchData(); // Refresh UI immediately
                    } else {
                        alert("Error actualizando status");
                    }
                } catch (e) {
                    console.error("Error al cambiar status:", e);
                }
            }

            async function fetchData() {
                try {
                    // Fetch Agents
                    const agentsRes = await fetch('/agents/');
                    const agents = await agentsRes.json();
                    
                    let online = 0, busy = 0, offline = 0;
                    
                    const agentsList = document.getElementById('agents-list');
                    agentsList.innerHTML = ''; // Clear list

                    agents.forEach(agent => {
                        if (agent.status === 'available') online++;
                        else if (agent.status === 'busy') busy++;
                        else offline++;

                        // Update or Create Marker
                        if (agentMarkers[agent.id]) {
                            agentMarkers[agent.id].setLatLng([agent.lat, agent.lon]);
                            agentMarkers[agent.id].setIcon(createCustomIcon(agent.status));
                            agentMarkers[agent.id].setPopupContent(`<b>${agent.name}</b><br>Status: ${agent.status}`);
                        } else {
                            const marker = L.marker([agent.lat, agent.lon], {icon: createCustomIcon(agent.status)})
                                .addTo(map)
                                .bindPopup(`<b>${agent.name}</b><br>Status: ${agent.status}`);
                            agentMarkers[agent.id] = marker;
                        }

                        // Add to Agent Sidebar
                        const statusColors = {
                            'available': 'text-green-400',
                            'busy': 'text-red-400',
                            'offline': 'text-slate-400'
                        };
                        const colorClass = statusColors[agent.status] || 'text-white';
                        
                        const el = document.createElement('div');
                        el.className = 'bg-slate-800 p-3 rounded border border-slate-700';
                        el.innerHTML = `
                            <div class="flex justify-between items-center mb-2">
                                <span class="font-bold text-sm">${agent.name}</span>
                                <span class="text-xs font-mono ${colorClass}">● ${agent.status.toUpperCase()}</span>
                            </div>
                            <div class="flex gap-2 mt-2">
                                <button onclick="changeAgentStatus(${agent.id}, 'available')" class="flex-1 text-xs bg-green-600 hover:bg-green-500 py-1 rounded transition text-white">Avail</button>
                                <button onclick="changeAgentStatus(${agent.id}, 'busy')" class="flex-1 text-xs bg-red-600 hover:bg-red-500 py-1 rounded transition text-white">Busy</button>
                                <button onclick="changeAgentStatus(${agent.id}, 'offline')" class="flex-1 text-xs bg-slate-600 hover:bg-slate-500 py-1 rounded transition text-white">Off</button>
                            </div>
                            <div class="mt-2">
                                <button onclick="openDispatchModal(${agent.id}, '${agent.name}')" class="w-full text-xs bg-blue-600 hover:bg-blue-500 py-1.5 rounded transition text-white font-bold tracking-wide border border-blue-400/50">🚀 DESPACHAR</button>
                            </div>
                        `;
                        agentsList.appendChild(el);
                    });

                    document.getElementById('count-online').innerText = online;
                    document.getElementById('count-busy').innerText = busy;
                    document.getElementById('count-offline').innerText = offline;

                    // Fetch Events
                    const eventsRes = await fetch('/events/');
                    if (eventsRes.ok) {
                        const events = await eventsRes.json();
                        const eventsList = document.getElementById('events-list');
                        eventsList.innerHTML = '';
                        
                        if(events.length === 0) {
                            eventsList.innerHTML = '<p class="text-slate-500 text-sm">No active alerts.</p>';
                        }

                        events.forEach(ev => {
                            // Add marker
                            if (!eventMarkers[ev.event_id]) {
                                const marker = L.marker([ev.lat, ev.lon], {icon: createCustomIcon('', true)})
                                    .addTo(map)
                                    .bindPopup(`<b>🚨 ${ev.event_type.toUpperCase()}</b><br>ID: ${ev.event_id}`);
                                eventMarkers[ev.event_id] = marker;
                            }
                            
                            // Add to sidebar
                            const el = document.createElement('div');
                            el.className = 'bg-slate-800 p-3 rounded border border-slate-700 hover:border-blue-500 cursor-pointer transition';
                            el.innerHTML = `
                                <div class="flex justify-between items-center mb-1">
                                    <span class="font-bold text-red-400">${ev.event_type.toUpperCase()}</span>
                                    <span class="text-xs text-slate-400">${new Date(ev.timestamp).toLocaleTimeString()}</span>
                                </div>
                                <div class="text-xs text-slate-300">ID: ${ev.event_id}</div>
                                <div class="text-xs text-slate-500 mt-1">Pri: ${ev.priority} | Lat: ${ev.lat.toFixed(4)}, Lon: ${ev.lon.toFixed(4)}</div>
                            `;
                            eventsList.appendChild(el);
                        });
                    }

                } catch (error) {
                    console.error("Error fetching data:", error);
                }
            }

            // Replace polling with WebSocket
            function connectWebSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    if (data.type === 'refresh') {
                        fetchData();
                    }
                };
                
                ws.onclose = function() {
                    console.log('WebSocket disconnected. Reconnecting in 3s...');
                    setTimeout(connectWebSocket, 3000);
                };
            }
            
            // Initial fetch and WS connection
            fetchData();
            connectWebSocket();
        </script>
    </body>
    </html>
    """
