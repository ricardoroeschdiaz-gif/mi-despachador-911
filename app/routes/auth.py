from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from app.database.database import get_db
from app.models.models import User, Agent
from app.schemas.schemas import UserCreate, UserResponse

SECRET_KEY = "super_secreto_ai_911_cambiar_en_produccion"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 1 semana

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token: str
    token_type: str
    agent_id: Optional[int] = None
    patrol_id: Optional[str] = None
    role: str

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    
    # Obtener el patrol_id (nombre del agente) si aplica
    patrol_id_str = None
    if user.agent_id:
        agent = db.query(Agent).filter(Agent.id == user.agent_id).first()
        if agent:
            patrol_id_str = agent.name

    return {
        "access_token": access_token,
        "token": access_token, # Para que funcione con lo que gener Gemini
        "token_type": "bearer",
        "agent_id": user.agent_id,
        "patrol_id": patrol_id_str,
        "role": user.role
    }

# ----------------------------------------------------
# RUTAS DE GESTI"N DE USUARIOS (CRUD)
# ----------------------------------------------------

@router.post("/users", response_model=UserResponse)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    # Verificar si el usuario ya existe
    existing_user = db.query(User).filter(User.username == user_in.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya est registrado.")

    valid_roles = ["admin", "dispatcher", "auditor", "agent"]
    if user_in.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Rol invǭlido. Debe ser uno de {valid_roles}")

    # Si es "agent", validar que el agent_id exista en la BD
    if user_in.role == "agent":
        if not user_in.agent_id:
            raise HTTPException(status_code=400, detail="Los usuarios con rol 'agent' deben tener un agent_id asignado.")
        
        agent_exists = db.query(Agent).filter(Agent.id == user_in.agent_id).first()
        if not agent_exists:
            raise HTTPException(status_code=400, detail="El agent_id proporcionado no existe en la base de datos de unidades.")

    new_user = User(
        username=user_in.username,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        agent_id=user_in.agent_id
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.get("/users", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@router.delete("/users/{user_id}", response_model=dict)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Prevenir que se borre a s mismo si es el ǧnico admin (Lgica de negocio)
    if user.username == "admin" and db.query(User).filter(User.role == "admin").count() == 1:
        raise HTTPException(status_code=400, detail="No se puede eliminar al ǧnico administrador del sistema.")

    db.delete(user)
    db.commit()
    return {"status": "success", "message": "Usuario eliminado correctamente"}
