from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel
import os

from src.log_buffer import log_buffer
from src.auth import require_token

load_dotenv()

app = FastAPI(title="Ship AI Companion")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/health")
async def health():
    return {"status": "ok"}

class LogEvent(BaseModel):
    type: str
    system: str | None = None
    data: dict | None = None

@app.post("/log/ingest", dependencies=[Depends(require_token)])
async def ingest_log(event: LogEvent):
    log_buffer.add(event.model_dump())
    return {"accepted": True}
