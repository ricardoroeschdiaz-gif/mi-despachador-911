from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="agent") # "dispatcher" or "agent"
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True) # If role is agent, link to patrol

    agent = relationship("Agent")

class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    fcm_token = Column(String, nullable=True) # Token para notificaciones push
    lat = Column(Float)
    lon = Column(Float)
    status = Column(String, default="available") # available, busy, offline
    last_update = Column(DateTime, default=datetime.utcnow)

class Event(Base):
    __tablename__ = "events"

    event_id = Column(String, primary_key=True, index=True)
    event_type = Column(String)
    lat = Column(Float)
    lon = Column(Float)
    priority = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Dispatch(Base):
    __tablename__ = "dispatches"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, ForeignKey("events.event_id"))
    agent_id = Column(Integer, ForeignKey("agents.id"))
    assigned_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="assigned")

    event = relationship("Event")
    agent = relationship("Agent")