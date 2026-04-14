"""
Log upload endpoint — player submits EVE Frontier client logs for Huginn analysis.

Endpoint:
  POST /logs/upload   — multipart/form-data: files + wallet_address

Security:
  - Only files from Chatlogs/ and Gamelogs/ subdirectories are accepted
  - From Chatlogs, only Local_* files (other channels are private)
  - All events are parsed through strict format validators before any text reaches Claude
  - Raw unrecognised log lines and chat messages are never forwarded to the AI
  - wallet_address is validated as a hex address before any file I/O
"""

import logging
import os
import re
from typing import List, Optional

from anthropic import Anthropic
from fastapi import APIRouter, Form, HTTPException, Query, UploadFile, File

from src.log_analysis import (
    extract_date_tag,
    filename_accepted,
    channel_from_filename,
    parse_file,
    build_system_timeline,
    annotate_events,
    summarize_for_huginn,
)
from src.log_intel_store import merge_upload, format_for_huginn, get_last_processed_date
from src.prompt_loader import load_prompt

log = logging.getLogger(__name__)

logs_router = APIRouter()

_KNOWN_ENVS = {"utopia", "stillness"}
_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB per file


def _resolve_env(tenant: str) -> str:
    """Return a validated env name. Unknown/empty values fall back to DEPLOYMENT_ENV."""
    if tenant in _KNOWN_ENVS:
        return tenant
    return os.getenv("DEPLOYMENT_ENV", "utopia")
_client = Anthropic()

# Accepted subdirectory names (case-insensitive)
_ACCEPTED_SUBDIRS = {"chatlogs", "gamelogs"}

# Chatlog: only Local_ channel files
_CHATLOG_NAME_RE = re.compile(r'^Local_\d{8}_', re.IGNORECASE)
# Gamelog: YYYYMMDD_ prefix
_GAMELOG_NAME_RE = re.compile(r'^\d{8}_')

_SYSTEM_PROMPT = load_prompt("companion") + "\n\n" + load_prompt("logs")


def _classify_file(filename: str, relative_path: str) -> Optional[str]:
    """
    Determine whether a file is a 'chatlog', 'gamelog', or None (reject).
    Uses relative_path (webkitRelativePath) for subdirectory check when available.
    Falls back to filename pattern only if no path info.
    """
    basename = filename.split("/")[-1].split("\\")[-1]

    if relative_path:
        # Extract the immediate parent directory of the file within the relative path
        parts = relative_path.replace("\\", "/").split("/")
        # parts[-1] is the filename; parts[-2] is the parent dir (if present)
        parent_dir = parts[-2].lower() if len(parts) >= 2 else ""

        if parent_dir not in _ACCEPTED_SUBDIRS:
            return None

        if parent_dir == "chatlogs":
            return "chatlog" if _CHATLOG_NAME_RE.match(basename) else None
        if parent_dir == "gamelogs":
            return "gamelog" if _GAMELOG_NAME_RE.match(basename) else None
        return None

    # No path info (manual file selection) — rely on filename patterns
    if _CHATLOG_NAME_RE.match(basename):
        return "chatlog"
    if _GAMELOG_NAME_RE.match(basename):
        return "gamelog"
    return None


@logs_router.get("/logs/last-processed-date")
async def get_last_processed_date_endpoint(wallet: str = Query(default=""), tenant: str = Query(default="")):
    """Return the most recent file date processed for a wallet, or null if none."""
    w = wallet.strip().lower()
    if not w:
        return {"last_processed_date": None}
    env = _resolve_env(tenant)
    return {"last_processed_date": get_last_processed_date(w, env=env)}


@logs_router.post("/logs/upload")
async def upload_logs(
    files: List[UploadFile] = File(...),
    wallet_address: str = Form(""),
    relative_paths: str = Form(""),  # JSON array of webkitRelativePath strings, one per file
    tenant: str = Form(""),          # player's active tenant (utopia or stillness)
):
    import json as _json

    # Parse relative paths sent from the frontend (one per file, same order)
    try:
        rel_paths: list[str] = _json.loads(relative_paths) if relative_paths else []
    except Exception:
        rel_paths = []

    # Pad to match file count
    while len(rel_paths) < len(files):
        rel_paths.append("")

    wallet = wallet_address.strip().lower()
    env = _resolve_env(tenant)
    last_date = get_last_processed_date(wallet, env=env) if wallet else None

    chatlog_events: list[dict] = []
    gamelog_events: list[dict] = []
    files_processed = 0
    skipped_subdir = 0
    skipped_date = 0
    newest_file_date: Optional[str] = None

    for upload, rel_path in zip(files, rel_paths):
        filename = upload.filename or ""
        basename = filename.split("/")[-1].split("\\")[-1]

        # Classify by subdirectory + filename pattern
        log_type = _classify_file(basename, rel_path)
        if log_type is None:
            skipped_subdir += 1
            continue

        # Date filter — skip files already covered by a prior upload for this wallet
        if not filename_accepted(basename, last_processed_date=last_date):
            skipped_date += 1
            continue

        raw = await upload.read(_MAX_FILE_BYTES + 1)
        if len(raw) > _MAX_FILE_BYTES:
            log.warning("Skipping oversized file: %s (%d+ bytes)", filename, _MAX_FILE_BYTES)
            continue
        detected_type, events = parse_file(raw, basename)

        # If detection disagrees with classification, trust classification
        # (parse_file returns 'unknown' for header-only or very short files)
        if detected_type == "unknown" and log_type in ("chatlog", "gamelog"):
            detected_type = log_type

        if detected_type == "chatlog":
            channel = channel_from_filename(basename)
            for ev in events:
                ev["channel"] = channel
            chatlog_events.extend(events)
        elif detected_type == "gamelog":
            gamelog_events.extend(events)
        else:
            skipped_subdir += 1
            continue

        # Track newest date seen
        date_tag = extract_date_tag(basename)
        if date_tag and (newest_file_date is None or date_tag > newest_file_date):
            newest_file_date = date_tag

        files_processed += 1

    log.info(
        "Log upload: wallet=%s processed=%d skipped_date=%d skipped_subdir=%d",
        wallet[:10] if wallet else "anon", files_processed, skipped_date, skipped_subdir,
    )

    if files_processed == 0:
        if skipped_date > 0:
            raise HTTPException(
                status_code=422,
                detail=f"All {skipped_date} file(s) were already processed in a prior upload. No new data.",
            )
        raise HTTPException(
            status_code=422,
            detail=f"No usable log files found. {skipped_subdir} file(s) rejected (wrong folder or format).",
        )

    # Build timeline and annotate gamelog events with system locations
    ts_list, sys_list = build_system_timeline(chatlog_events)
    annotate_events(gamelog_events, ts_list, sys_list)

    # Persist intel and advance last_processed_date
    if wallet:
        merge_upload(wallet, gamelog_events, ts_list, sys_list, newest_file_date, env=env)

    # Build summary (structured fields only — no raw text)
    current_summary = summarize_for_huginn(gamelog_events, ts_list, sys_list, chatlog_events)

    # Historical context from prior uploads
    historical = format_for_huginn(wallet, env=env) if wallet else ""

    total_events = len(gamelog_events) + len(chatlog_events)
    systems_visited = list(dict.fromkeys(sys_list))

    user_message = (
        f"FLIGHT RECORDER DATA — {files_processed} file(s), {total_events} events"
        + (f", {skipped_date} already-processed file(s) skipped" if skipped_date else "")
        + ":\n\n"
        + (f"{historical}\n\n" if historical else "")
        + current_summary
    )

    try:
        response = _client.messages.create(
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        analysis = response.content[0].text
    except Exception as e:
        log.error("Claude API error during log analysis: %s", e)
        raise HTTPException(status_code=502, detail="Analysis service unavailable.")

    return {
        "analysis": analysis,
        "files_processed": files_processed,
        "files_skipped": skipped_date,
        "event_count": total_events,
        "systems_visited": systems_visited,
        "last_processed_date": newest_file_date,
    }
