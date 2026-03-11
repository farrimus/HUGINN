# log-agent/log_agent.py
import os
import time
import logging
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from parsers import parse_gamelog_line, parse_chatlog_line
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='[agent] %(message)s')
log = logging.getLogger(__name__)

SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8745")
SHIP_TOKEN = os.getenv("SHIP_TOKEN", "")
LOG_BASE = os.getenv("LOG_BASE_PATH", "")
GAMELOG_DIR = os.path.join(LOG_BASE, "Gamelogs")
CHATLOG_DIR = os.path.join(LOG_BASE, "Chatlogs")

def validate_paths():
    for path in [GAMELOG_DIR, CHATLOG_DIR]:
        if not os.path.isdir(path):
            raise FileNotFoundError(f"Log directory not found: {path}")
    log.info("Log directories found.")

def send_event(event: dict):
    headers = {"X-Ship-Token": SHIP_TOKEN} if SHIP_TOKEN else {}
    try:
        requests.post(f"{SERVER_URL}/log/ingest", json=event, headers=headers, timeout=5)
        log.info("Sent event: %s", event.get("type"))
    except Exception as e:
        log.warning("Failed to send event: %s", e)

class LogFileHandler(FileSystemEventHandler):
    def __init__(self, parser_fn):
        self._file_positions = {}
        self.parser_fn = parser_fn

    def on_modified(self, event):
        if event.is_directory:
            return
        path = event.src_path
        if path not in self._file_positions:
            # First time seeing this file: start from end, don't replay history
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(0, 2)  # seek to end
                self._file_positions[path] = f.tell()
        pos = self._file_positions[path]
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(pos)
                new_lines = f.readlines()
                self._file_positions[path] = f.tell()
            for line in new_lines:
                parsed = self.parser_fn(line)
                if parsed:
                    send_event(parsed)
        except Exception as e:
            log.warning("Error reading %s: %s", path, e)

if __name__ == "__main__":
    validate_paths()
    log.info("Watching %s and %s", GAMELOG_DIR, CHATLOG_DIR)

    observer = Observer()
    observer.schedule(LogFileHandler(parse_gamelog_line), GAMELOG_DIR, recursive=False)
    observer.schedule(LogFileHandler(parse_chatlog_line), CHATLOG_DIR, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down.")
        observer.stop()
    observer.join()
