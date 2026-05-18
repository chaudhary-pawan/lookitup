from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from backend.database.db import get_db
from backend.database.models import Organizer
from backend.api.auth import get_password_hash, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

class AuthRequest(BaseModel):
    email: str
    password: str

@router.post("/register")
async def register(req: AuthRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Organizer).where(Organizer.email == req.email))
    existing = result.scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    org = Organizer(
        email=req.email,
        hashed_password=get_password_hash(req.password)
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    
    token = create_access_token({"sub": org.id})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/login")
async def login(req: AuthRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Organizer).where(Organizer.email == req.email))
    org = result.scalars().first()
    
    if not org or not verify_password(req.password, org.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
        
    token = create_access_token({"sub": org.id})
    return {"access_token": token, "token_type": "bearer"}
