# CASO DE NEGOCIO Y ARQUITECTURA TÉCNICA
## Plataforma de Despacho Autónomo de Seguridad (AI-911)

### 1. Resumen Ejecutivo (Para Dirección y Finanzas)
**Contexto Actual:** El centro de monitoreo opera con 34 elementos que gestionan un ecosistema masivo: 6,500 cámaras, 500 sistemas de alarma, 1,600 dispositivos GPS y 63 patrulleros en campo. La carga cognitiva actual supera los estándares de la industria, generando cuellos de botella en el tiempo de respuesta, fatiga visual y un alto porcentaje de falsos positivos.

**La Solución:** Implementación de un Despachador Autónomo basado en Inteligencia Artificial (AI-911) alojado en infraestructura local (On-Premise de Alto Rendimiento). El sistema actuará como el "Primer Respondiente Digital", filtrando el 100% de las alertas y escalando únicamente los incidentes verificados al equipo humano.

**Impacto Financiero y Operativo (ROI):**
*   **Contención de Nómina:** Permite escalar la infraestructura de cámaras y alarmas en un 200% sin necesidad de aumentar la plantilla de 34 operadores.
*   **Optimización de Recursos (Combustible/Tiempo):** Asignación algorítmica de los 63 patrulleros basándose en proximidad GPS y tráfico en tiempo real, reduciendo costos operativos y tiempos de respuesta (SLA).
*   **Reducción de Riesgo Legal/Pérdidas:** Disminución de incidentes no detectados por fatiga humana.
*   **CAPEX vs. OPEX:** Enviar el streaming a la nube generaría costos mensuales prohibitivos. Adquirir hardware local (CAPEX) se amortiza rápido y elimina rentas.

---

# MANUAL DE INGENIERÍA Y ARQUITECTURA
**Nivel de Clasificación:** Interno / Técnico  

## 1. DIAGRAMA DE FLUJO DE EVENTOS (Event Workflow)
El sistema opera bajo un modelo de arquitectura orientada a eventos (Event-Driven Architecture).

1. **Ingesta de Señal:** El panel de intrusión transmite un evento (ej. Zona 4) vía CID/SIA al Gateway.
2. **Normalización:** El backend convierte el evento en un objeto JSON (`AlertPayload`).
3. **Correlación de Activos:** El motor identifica qué cámaras (ONVIF/RTSP) están mapeadas a esa zona.
4. **Cálculo de Proximidad:** El motor geoespacial (PostGIS) busca las 3 unidades GPS más cercanas al POI.
5. **Apertura de UI:** El backend dispara un WebSocket al frontend del operador mostrando video, datos y mapa.

## 2. DOCUMENTACIÓN DE PROTOCOLOS
*   **Ingesta de Alarmas (SIA DC-09 / Contact ID over IP):** Comunicación TCP/UDP.
*   **Video Streaming (RTSP & ONVIF):** ONVIF para control, RTSP (H.264/H.265) transcoded a WebRTC/HLS para el frontend (< 500ms latencia).
*   **Telemetría GPS (MQTT / TCP Sockets):** Publicación de tramas NMEA/Hexadecimal vía broker MQTT.
*   **Comunicación UI (WebSockets):** Conexión persistente bidireccional.

## 3. MATRIZ DE PRIORIDADES (Triage System)
*   **P1 (Crítico):** Pánico, Fuego, Médico (PA, FA, MA). SLA < 2 Seg. Toma control de UI.
*   **P2 (Alto):** Intrusión, Sabotaje de Video. SLA < 5 Seg. Notificación roja, carga video en background.
*   **P3 (Medio):** Aperturas fuera de horario. SLA < 30 Seg. Grid amarillo.
*   **P4 (Bajo):** Test periódico. Archivo en background.

## 4. DICCIONARIO DE DATOS (Entidades Core)
*   **AlertEntity:** ID, Timestamp, Account_ID, Código_SIA, Nivel_Prioridad, Estado.
*   **AccountEntity:** Cliente_ID, Nombre, Coordenadas (Lat/Lon), Contactos.
*   **CameraEntity:** Cam_ID, Account_ID, URL_RTSP, Zona_Vinculada.
*   **ResponseUnitEntity:** Patrol_ID, Estatus, Last_Lat, Last_Lon.

## 5. MANEJO DE ERRORES Y FAILOVER (Alta Disponibilidad)
*   **Video Timeout:** Falla a imagen estática, conserva alerta de datos.
*   **Caída de Gateway:** Balanceadores de carga (HAProxy/Nginx) enrutan a nodo Standby en < 100ms.
*   **GPS Stale:** Ignora unidades sin ping > 3 mins.
*   **Caché Offline:** Redis mantiene operación si PostgreSQL se reinicia temporalmente.

## 6. INFRAESTRUCTURA (Redes y Puertos)
*   **Video Inbound:** ~2 Mbps constantes por cámara en vivo.
*   **Data Inbound:** ~5-10 Mbps garantizados (Jitter < 20ms).
*   **Puertos:** SIA (TCP 12000), GPS (TCP 5000), RTSP (TCP 554), WebRTC/WSS (TCP 443).