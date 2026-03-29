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

def notify_clients():
    asyncio.create_task(manager.broadcast({"type": "refresh"}))

@router.post("/", response_model=DispatchResponse)
def receive_event(payload: dict = Body(...), background_tasks: BackgroundTasks = BackgroundTasks(), db: Session = Depends(get_db)):
    result = process_and_dispatch_raw_event(db, payload)
    background_tasks.add_task(notify_clients)
    return result

@router.get("/", response_model=List[EventResponse])
def get_events(db: Session = Depends(get_db)):
    return db.query(Event).order_by(Event.timestamp.desc()).limit(20).all()
