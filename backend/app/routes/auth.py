from fastapi import APIRouter, Depends, HTTPException, status
from datetime import timedelta, datetime
import logging
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from app.database import get_db
from app.schemas import UserRegister, UserLogin, TokenResponse, GoogleLoginRequest
from app.auth.password import hash_password, verify_password
from app.auth.jwt import create_access_token
from app.config import settings
from app.auth.google_oauth import generate_unique_username

logger = logging.getLogger(__name__)

router = APIRouter()

TOKEN_EXPIRES_SECONDS = 604800  # 7 days, per spec


def _issue_token(user: dict) -> TokenResponse:
    token = create_access_token(
        data={"sub": str(user["_id"])},
        expires_delta=timedelta(seconds=TOKEN_EXPIRES_SECONDS),
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=str(user["_id"]),
        expires_in=TOKEN_EXPIRES_SECONDS,
    )


@router.post("/register", response_model=TokenResponse)
def register(payload: UserRegister, db = Depends(get_db)):
    if db.users.find_one({"username": payload.username}):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Username already taken")
    if db.users.find_one({"email": payload.email}):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")

    now = datetime.utcnow()
    user_doc = {
        "username": payload.username,
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "google_id": None,
        "created_at": now,
        "updated_at": now,
    }
    result = db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    return _issue_token(user_doc)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db = Depends(get_db)):
    user = db.users.find_one({"email": payload.email})
    if user is None or user["password_hash"] is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    return _issue_token(user)


@router.post("/google", response_model=TokenResponse)
def google_login(payload: GoogleLoginRequest, db = Depends(get_db)):
    if not settings.google_client_id:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Google login is not configured")

    try:
        idinfo = google_id_token.verify_oauth2_token(
            payload.id_token, google_requests.Request(), settings.google_client_id,
        )
    except ValueError as e:
        logger.warning("Google token verification failed: %s", str(e))
        detail = f"Invalid Google token: {e}" if settings.debug else "Invalid Google token"
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail)

    google_id = idinfo["sub"]
    email = idinfo["email"]

    user = db.users.find_one({"google_id": google_id})
    if user is None:
        user = db.users.find_one({"email": email})
        if user is not None:
            db.users.update_one({"_id": user["_id"]}, {"$set": {"google_id": google_id, "updated_at": datetime.utcnow()}})
            user["google_id"] = google_id
        else:
            now = datetime.utcnow()
            user_doc = {
                "username": generate_unique_username(email.split("@")[0], db),
                "email": email,
                "password_hash": None,
                "google_id": google_id,
                "created_at": now,
                "updated_at": now,
            }
            result = db.users.insert_one(user_doc)
            user_doc["_id"] = result.inserted_id
            user = user_doc

    return _issue_token(user)
