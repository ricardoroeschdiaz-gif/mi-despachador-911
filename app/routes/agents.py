from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from pydantic import BaseModel
from app.database.database import get_db
from app.schemas.schemas import AgentResponse, LocationUpdate, AgentRegistration
from app.models.models import Agent
from app.services.websocket_manager import manager
import asyncio

router = APIRouter(prefix="/agents", tags=["Agents"])

class StatusUpdate(BaseModel):
    status: str

def notify_clients():
    asyncio.create_task(manager.broadcast({"type": "refresh"}))

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