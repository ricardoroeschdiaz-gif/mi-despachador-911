from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class EventCreate(BaseModel):
    event_id: str
    event_type: str
    lat: float
    lon: float
    priority: str
    timestamp: datetime

class EventResponse(BaseModel):
    event_id: str
    event_type: str
    lat: float
    lon: float
    priority: str
    timestamp: datetime

    class Config:
        from_attributes = True

class AgentResponse(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    status: str
    fcm_token: Optional[str] = None

    class Config:
        from_attributes = True

class AgentRegistration(BaseModel):
    fcm_token: str

class DispatchResponse(BaseModel):
    event_id: str
    dispatched: bool
    agent: Optional[AgentResponse] = None
    message: str

class LocationUpdate(BaseModel):
    lat: float
    lon: float