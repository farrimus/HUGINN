from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from pydantic import BaseModel
import os
import json
import asyncio

from src.log_buffer import log_buffer
from src.auth import require_token
from src.claude_client import claude
from src.context_builder import build_context_block
from src.world_api import world_api

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
    if event.type == "system_change" and event.system:
        asyncio.create_task(world_api.get_system(event.system))
    return {"accepted": True}

class ChatRequest(BaseModel):
    message: str
    history: list = []

@app.post("/chat", dependencies=[Depends(require_token)])
async def chat(req: ChatRequest):
    system_data = await world_api.get_system(log_buffer.current_system) if log_buffer.current_system else None
    context = build_context_block(
        system_data=system_data,
        log_events=log_buffer.get_recent(10),
        current_system=log_buffer.current_system,
    )

    def event_stream():
        try:
            for chunk in claude.stream(req.message, req.history, context):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Stream error: %s", e)
            yield f"data: {json.dumps({'error': 'Stream interrupted. Ship systems error.'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
