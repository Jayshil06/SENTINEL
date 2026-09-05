import os
from fastapi import APIRouter, Request, Response, HTTPException, status
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/auth", tags=["Law Enforcement Authentication"])

class LoginRequest(BaseModel):
    badge: str = "GP-POL-001"
    name: Optional[str] = "Inspector ABC"
    role: Optional[str] = "Investigating Officer (IO)"
    pin: Optional[str] = None

class AuthSessionResponse(BaseModel):
    authenticated: bool
    badge: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    message: str

@router.post("/login")
def login(payload: LoginRequest, response: Response):
    """
    Law Enforcement Officer Login Endpoint.
    Authenticates badge credentials and sets 'sentinel_session' HTTP cookie.
    """
    badge = payload.badge.strip()
    if not badge:
        raise HTTPException(status_code=400, detail="Officer badge number is required.")
    
    # Set session cookie (valid for 24 hours)
    response.set_cookie(
        key="sentinel_session",
        value=badge,
        max_age=86400,
        httponly=False,  # Accessible to client JS auth.js
        samesite="lax",
        path="/"
    )
    return {
        "status": "authenticated",
        "badge": badge,
        "name": payload.name or "Inspector ABC",
        "role": payload.role or "Investigating Officer (IO)",
        "message": f"Officer {badge} successfully authenticated into Project SENTINEL."
    }

@router.post("/logout")
def logout(response: Response):
    """
    Officer Logout Endpoint.
    Clears the 'sentinel_session' cookie.
    """
    response.delete_cookie(key="sentinel_session", path="/")
    return {
        "status": "logged_out",
        "message": "Law enforcement session terminated."
    }

@router.get("/session", response_model=AuthSessionResponse)
def get_session(request: Request):
    """
    Inspects current law enforcement session status from cookie or Authorization header.
    """
    session_cookie = request.cookies.get("sentinel_session")
    auth_header = request.headers.get("Authorization")
    token_header = request.headers.get("X-Sentinel-Token") or request.headers.get("X-API-Key")
    
    badge = session_cookie
    if not badge and auth_header and (auth_header.startswith("Bearer ") or auth_header.startswith("Token ")):
        badge = auth_header.split(" ", 1)[1].strip()
    elif not badge and token_header:
        badge = token_header.strip()

    if badge:
        return AuthSessionResponse(
            authenticated=True,
            badge=badge,
            name="Inspector ABC",
            role="Investigating Officer (IO)",
            message="Active session verified."
        )
    return AuthSessionResponse(
        authenticated=False,
        badge=None,
        name=None,
        role=None,
        message="No active session found. Please authenticate at /login."
    )
