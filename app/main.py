import logging
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from app.database.database import engine, Base, SessionLocal
from app.routes import events, agents, dashboard, auth
from app.models.models import Agent, User
from app.routes.auth import get_password_hash
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Security Dispatch API MVP")

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(agents.router)
app.include_router(dashboard.router)

@app.on_event("startup")
def seed_data():
    db = SessionLocal()
    # Sembrar Agentes
    if db.query(Agent).count() == 0:
        logger.info("Seeding test agents...")
        test_agents = [
            Agent(name="M1 - Zona 10", lat=14.6038, lon=-90.5132, status="available", last_update=datetime.utcnow()),
            Agent(name="M2 - Zona 1", lat=14.6349, lon=-90.5155, status="available", last_update=datetime.utcnow()),
            Agent(name="M3 - Zona 14", lat=14.5800, lon=-90.5200, status="available", last_update=datetime.utcnow()),
            Agent(name="M4 - Lejos", lat=14.7000, lon=-90.6000, status="available", last_update=datetime.utcnow()),
            Agent(name="M5 - Offline", lat=14.6200, lon=-90.5300, status="offline", last_update=datetime.utcnow()),
        ]
        db.add_all(test_agents)
        db.commit()

    # Sembrar Usuarios de prueba
    if db.query(User).count() == 0:
        logger.info("Seeding test users...")
        test_users = [
            User(username="admin", hashed_password=get_password_hash("admin123"), role="dispatcher"),
            User(username="patrulla_01", hashed_password=get_password_hash("1234"), role="agent", agent_id=1),
            User(username="roeschito", hashed_password=get_password_hash("roesch123"), role="agent", agent_id=2)
        ]
        db.add_all(test_users)
        db.commit()
    db.close()

@app.get("/")
def root():
    return {"message": "Security Dispatch API is running. Go to /docs to test endpoints."}

@app.get("/tracker", response_class=HTMLResponse)
def get_tracker():
    return "Tracker HTML placeholder"
