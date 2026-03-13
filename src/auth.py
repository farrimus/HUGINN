import os
from fastapi import Header, HTTPException

def require_token(x_server_token: str = Header(default="")):
    expected = os.getenv("SERVER_TOKEN", "")
    if not expected:
        return  # No token configured — open access (local-only mode)
    if x_server_token != expected:
        raise HTTPException(status_code=403, detail="Invalid token")
