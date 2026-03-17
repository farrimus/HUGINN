from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.token_manager import TokenManager

auth_router = APIRouter(prefix="/auth", tags=["auth"])
token_manager = None  # Will be initialized by main

def init_auth(manager: TokenManager):
    """Initialize auth endpoints with TokenManager."""
    global token_manager
    token_manager = manager

class TokenRequest(BaseModel):
    agent_id: str

@auth_router.post("/token")
async def issue_token(req: TokenRequest):
    """Issue a JWT token for a given agent_id."""
    if not req.agent_id:
        raise HTTPException(status_code=400, detail="agent_id is required")

    # Issue token (24-hour lifetime)
    access_token = token_manager.issue_token(req.agent_id, lifetime_hours=24)

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 86400  # 24 hours in seconds
    }
