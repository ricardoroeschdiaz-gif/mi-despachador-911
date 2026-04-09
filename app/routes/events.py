from fastapi import APIRouter, Depends, HTTPException, Body, BackgroundTasks
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.schemas.schemas import DispatchResponse, EventResponse
from app.models.models import Event
from app.services.dispatch import process_and_dispatch_raw_event
from app.services.websocket_manager import manager
from typing import List
import asyncio

router = APIRouter(prefix="/events", tags=["Events"])

async def notify_clients():
    print("📡 Broadcasting refresh signal to all operators...")
    await manager.broadcast({"type": "refresh"})

@router.post("/", response_model=DispatchResponse)
def receive_event(payload: dict = Body(...), background_tasks: BackgroundTasks = BackgroundTasks(), db: Session = Depends(get_db)):
    result = process_and_dispatch_raw_event(db, payload)
    background_tasks.add_task(notify_clients)
    return result

@router.get("/", response_model=List[EventResponse])
def get_events(db: Session = Depends(get_db)):
    return db.query(Event).filter(Event.status == "active").order_by(Event.timestamp.desc()).limit(20).all()

@router.get("/history", response_model=List[EventResponse])
def get_history(db: Session = Depends(get_db)):
    return db.query(Event).filter(Event.status != "active").order_by(Event.timestamp.desc()).limit(100).all()

@router.delete("/{event_id}")
def delete_event(event_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    from app.models.models import Dispatch, Agent
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event:
        # Poner "available" al agente asignado si la alerta es cancelada
        dispatches = db.query(Dispatch).filter(Dispatch.event_id == event_id).all()
        for d in dispatches:
            agent = db.query(Agent).filter(Agent.id == d.agent_id).first()
            if agent:
                agent.status = "available"
            # d.status = "resolved" # Optional: update dispatch status too
        
        event.status = "resolved"
        db.commit()
        background_tasks.add_task(notify_clients)
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Event not found")
