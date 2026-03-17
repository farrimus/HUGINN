from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from src.token_manager import TokenManager

auth_router = APIRouter(prefix="/auth", tags=["auth"])
token_manager = None  # Will be initialized by main

def init_auth(manager: TokenManager):
    """Initialize auth endpoints with TokenManager."""
    global token_manager
    token_manager = manager

class TokenRequest(BaseModel):
    agent_id: str = Field(min_length=1, max_length=255)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

@auth_router.post("/token", response_model=TokenResponse)
async def issue_token(req: TokenRequest) -> TokenResponse:
    """Issue a JWT token for a given agent_id.

    Args:
        req: TokenRequest containing agent_id

    Returns:
        TokenResponse with access_token, token_type, expires_in
    """
    agent_id = req.agent_id.strip()

    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id cannot be empty or whitespace")

    # Issue token (24-hour lifetime)
    access_token = token_manager.issue_token(agent_id, lifetime_hours=24)

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=86400  # 24 hours in seconds
    )


security = HTTPBearer()

async def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate JWT token from Authorization header.

    Returns the token payload if valid, raises HTTPException(401) if invalid.
    """
    token = credentials.credentials
    payload = token_manager.validate_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload
