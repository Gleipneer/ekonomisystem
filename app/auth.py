from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import database, models
from .schemas import AppUserCreate, AppUserRead, Token

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRequest(BaseModel):
    username: str
    password: str


def get_db() -> Session:
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/register", response_model=AppUserRead, status_code=status.HTTP_201_CREATED)
def register(body: AppUserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.AppUser).filter_by(username=body.username).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Användarnamn finns redan.")
    user = models.AppUser(
        username=body.username,
        password_hash=pwd_context.hash(body.password),
        household_id=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/token", response_model=Token)
def issue_token(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(models.AppUser).filter_by(username=body.username).first()
    if user is None or not pwd_context.verify(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Fel användarnamn eller lösenord.")
    token = str(uuid4())
    session = models.AuthSession(
        user_id=user.id,
        session_token=token,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(session)
    db.commit()
    response.set_cookie("he_session", token, httponly=True, samesite="lax")
    return Token(access_token=token, token_type="bearer")
