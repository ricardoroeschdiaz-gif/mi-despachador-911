# PROJECT_BRAIN.md - Autonomous AI Security Dispatcher

## 🎯 Objetivo Principal
Construir un MVP funcional de un sistema de despacho automático de seguridad (estilo 911) operado por un agente de Inteligencia Artificial. El sistema debe ser capaz de operar de manera autónoma 24/7, recibiendo eventos de alarmas, evaluando la situación y despachando al agente/patrulla más cercano.

## 🧠 Estado Actual de la Memoria (Última actualización: 21-Marzo-2026)
- **Fase actual:** Cerebro IA integrado. Endpoint agnóstico completado. Dashboard UI base construido.
- **Directorio del proyecto:** `C:\Users\UW11\.openclaw\workspace\dispatch_mvp`

## 🏗️ Arquitectura del MVP (V1.5)
- **Backend:** Python con FastAPI (Alto rendimiento, asíncrono).
- **Base de Datos:** PostgreSQL local usando Docker y SQLAlchemy.
- **Modelos de Datos:** 
  - `Agent` (id, name, lat, lon, status, last_update)
  - `Event` (event_id, event_type, lat, lon, priority, timestamp)
  - `Dispatch` (Relación entre Event y Agent).
- **Lógica Central:** 
  - **Endpoint agnóstico (`POST /events`)**: Recibe CUALQUIER carga JSON.
  - El payload se envía al LLM (Gemini 3 Flash Preview) usando un proxy REST para eludir conflictos de Python 3.14 con `grpcio`.
  - La IA extrae coordenadas, evalúa el tipo de emergencia y decide si se despacha o no.
  - Calcula distancia a agentes disponibles (Haversine).
  - Exige GPS reciente (< 60s) y asocia al agente cambiando su status a "busy".

## 🚀 Roadmap: Hacia el Agente Autónomo Completo
1. **[COMPLETADO] Integración del Cerebro IA:** IA integrada exitosamente para analizar payloads crudos/webhook de cualquier panel de alarma y tomar decisiones estructuradas.
2. **[COMPLETADO] Dashboard UI Base y WebSockets:** Interfaz visual con Leaflet y WebSockets integrados para ver eventos y patrullas moverse fluidamente en tiempo real (event-driven), eliminando el polling saturador.
3. **[COMPLETADO] Migración a la Nube (GCP):** El backend ya está en Google Cloud Platform y recibe correctamente conexiones desde la aplicación móvil.
4. **[COMPLETADO] Routing Inteligente:** Se implementó `get_driving_eta` usando la API de OSRM. Ahora el despachador de IA asigna la unidad basándose en tiempo real de conducción y tráfico, no en línea recta (Haversine se mantiene como fallback de seguridad).
5. **[PENDIENTE] Notificaciones Reales a los Agentes:** Enviar mensajes vía WhatsApp, SMS o Telegram al motorista despachado indicando las coordenadas, la ruta y el motivo del despacho en texto plano o audio. (FCM Push integrado parcialmente, falta refinar canales extra).

## 📝 Reglas de Operación (I/O)
- **Jimmy Night** debe leer este archivo antes de modificar el código del proyecto.
- Cualquier avance arquitectónico o de negocio debe registrarse aquí inmediatamente.