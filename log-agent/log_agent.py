# log-agent/log_agent.py
import os
import time
import threading
import logging
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from parsers import parse_gamelog_line, parse_chatlog_line
from session_tracker import SessionTracker
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='[agent] %(message)s')
log = logging.getLogger(__name__)

SERVER_URL   = os.getenv("SERVER_URL", "http://localhost:8745")
SERVER_TOKEN = os.getenv("SERVER_TOKEN", "")
LOG_BASE     = os.getenv("LOG_BASE_PATH", "")
GAMELOG_DIR  = os.path.join(LOG_BASE, "Gamelogs")
CHATLOG_DIR  = os.path.join(LOG_BASE, "Chatlogs")


def validate_paths():
    for path in [GAMELOG_DIR, CHATLOG_DIR]:
        if not os.path.isdir(path):
            raise FileNotFoundError(f"Log directory not found: {path}")
    log.info("Log directories found.")


def send_event(event: dict):
    headers = {"X-Server-Token": SERVER_TOKEN} if SERVER_TOKEN else {}
    try:
        requests.post(f"{SERVER_URL}/log/ingest", json=event, headers=headers, timeout=5)
        log.info(">> %s", event)
    except Exception as e:
        log.warning("Failed to send event: %s", e)


def channel_from_path(path: str) -> str:
    """
    Extract the channel name from a chatlog filename.
    Format: CHANNELNAME_numbers_numbers_numbers
    e.g. Local_12345_67890_11111 -> Local
         Corp_12345_67890_11111  -> Corp
    Returns the full basename (without extension) if no underscore found.
    """
    name = os.path.splitext(os.path.basename(path))[0]
    return name.split("_")[0]


def _sniff_encoding(path: str) -> str:
    """
    Read the first 4 bytes of a file to detect encoding from BOM.
    EVE Frontier chatlogs are UTF-16 LE; gamelogs are UTF-8.
    Falls back to UTF-8 if no BOM is found.
    """
    try:
        with open(path, "rb") as f:
            bom = f.read(4)
    except OSError:
        return "utf-8"
    if bom.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if bom.startswith(b"\xfe\xff"):
        return "utf-16-be"
    return "utf-8"  # covers plain UTF-8 and UTF-8 with BOM (ef bb bf)


def _decode_raw(raw: bytes, encoding: str, strip_bom: bool) -> str:
    """
    Decode a raw byte chunk. If strip_bom is True (first read of file),
    remove the leading BOM bytes before decoding.
    """
    if strip_bom:
        if encoding == "utf-16-le" and raw.startswith(b"\xff\xfe"):
            raw = raw[2:]
        elif encoding == "utf-16-be" and raw.startswith(b"\xfe\xff"):
            raw = raw[2:]
        elif raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
    return raw.decode(encoding, errors="ignore")


class LogFileHandler(FileSystemEventHandler):
    def __init__(self, parser_fn, tracker: SessionTracker, inject_channel: bool = False,
                 agent_start: float = None):
        self._file_positions: dict[str, int] = {}
        self._file_encodings: dict[str, str] = {}
        self._pending: dict[str, str] = {}
        self._pending_bytes: dict[str, bytes] = {}
        self.parser_fn      = parser_fn
        self.tracker        = tracker
        self.inject_channel = inject_channel  # True for chatlog handler
        self._agent_start   = agent_start if agent_start is not None else time.time()

    def on_created(self, event):
        if event.is_directory:
            return
        # New session file — read from the start so we don't miss opening
        # lines (e.g. initial "Channel changed to Local : SYSTEM" entry).
        self._file_positions[event.src_path] = 0
        log.info("New log file: %s", os.path.basename(event.src_path))

    def on_modified(self, event):
        if event.is_directory:
            return
        path = event.src_path

        # First encounter: detect encoding and decide start position.
        if path not in self._file_positions:
            self._file_encodings[path] = _sniff_encoding(path)
            mtime = os.path.getmtime(path)
            if mtime > self._agent_start:
                # File created after agent started — read from position 0.
                self._file_positions[path] = 0
                log.info("New-file (mtime check): reading %s from start", os.path.basename(path))
            else:
                # File existed before agent started — seek to end, no replay.
                with open(path, "rb") as f:
                    f.seek(0, 2)
                    self._file_positions[path] = f.tell()

        pos = self._file_positions[path]

        try:
            with open(path, "rb") as f:
                # Fix 4: truncation detection — file was recreated at same path
                size = os.path.getsize(path)
                if size < pos:
                    log.info("Truncation detected on %s — resetting", os.path.basename(path))
                    pos = 0
                    self._file_positions[path] = 0
                    self._pending.pop(path, None)
                    self._pending_bytes.pop(path, None)

                f.seek(pos)
                raw = f.read()
                self._file_positions[path] = f.tell()

            if not raw:
                return

            # Detect encoding from the actual bytes on the first read (pos == 0).
            # This must happen here — on_created sets pos=0 but the file may be
            # empty at that point, so we cannot sniff encoding there reliably.
            if path not in self._file_encodings:
                if pos == 0:
                    if raw.startswith(b"\xff\xfe"):
                        self._file_encodings[path] = "utf-16-le"
                    elif raw.startswith(b"\xfe\xff"):
                        self._file_encodings[path] = "utf-16-be"
                    else:
                        self._file_encodings[path] = "utf-8"
                else:
                    self._file_encodings[path] = "utf-8"

            enc = self._file_encodings[path]

            # Fix 2: odd-byte alignment for UTF-16 — a read may return an odd
            # number of bytes, causing every subsequent char to be misaligned.
            if enc in ("utf-16-le", "utf-16-be"):
                raw = self._pending_bytes.pop(path, b"") + raw
                if len(raw) % 2 != 0:
                    self._pending_bytes[path] = raw[-1:]
                    raw = raw[:-1]

            # Fix 1: partial line buffer — hold any unterminated trailing
            # fragment and prepend it on the next read.
            text  = self._pending.pop(path, "") + _decode_raw(raw, enc, strip_bom=(pos == 0))
            lines = text.splitlines(keepends=True)
            if lines and not lines[-1].endswith("\n"):
                self._pending[path] = lines.pop()

            channel = channel_from_path(path) if self.inject_channel else None
            for line in lines:
                parsed = self.parser_fn(line)
                if parsed:
                    if channel:
                        parsed["channel"] = channel
                    for out_event in self.tracker.process(parsed):
                        send_event(out_event)
        except Exception as e:
            log.warning("Error reading %s: %s", path, e)


def _read_file_text(path: str) -> list[str]:
    """
    Read an entire file, auto-detecting encoding from BOM.
    Returns a list of lines (splitlines, no keepends).
    """
    with open(path, "rb") as f:
        raw = f.read()
    enc = "utf-8"
    if raw.startswith(b"\xff\xfe"):
        enc, raw = "utf-16-le", raw[2:]
    elif raw.startswith(b"\xfe\xff"):
        enc, raw = "utf-16-be", raw[2:]
    elif raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode(enc, errors="ignore").splitlines()


def bootstrap_system(tracker: SessionTracker):
    """
    Scan the tail of the most recent Local_* chatlog file for the last known
    system. Only Local_ files contain system_change events — Corp_ and other
    channel files are irrelevant for bootstrap.
    """
    files = [
        os.path.join(CHATLOG_DIR, f)
        for f in os.listdir(CHATLOG_DIR)
        if f.startswith("Local_") and os.path.isfile(os.path.join(CHATLOG_DIR, f))
    ]
    if not files:
        log.warning("Bootstrap: no Local_* chatlog files found")
        return
    latest = max(files, key=os.path.getmtime)
    try:
        lines = _read_file_text(latest)
        for line in reversed(lines[-500:]):
            event = parse_chatlog_line(line)
            if event and event.get("type") == "system_change":
                event["channel"] = channel_from_path(latest)
                log.info("Bootstrap: last known system is %s (from %s)",
                         event["system"], os.path.basename(latest))
                for out_event in tracker.process(event):
                    send_event(out_event)
                return
    except Exception as e:
        log.warning("Bootstrap scan failed: %s", e)
    log.warning("Bootstrap: no system_change found in recent Local_* logs — system unknown until next jump")


class PeriodicBootstrap(threading.Thread):
    """
    Daemon thread that retries bootstrap_system() every `interval` seconds
    while the system is still unknown. Exits once a system is found.
    """
    def __init__(self, tracker: SessionTracker, interval: int = 30):
        super().__init__(daemon=True)
        self.tracker  = tracker
        self.interval = interval
        self._stop    = threading.Event()

    def run(self):
        while not self._stop.is_set():
            if self.tracker.current_system is not None:
                log.info("PeriodicBootstrap: system known (%s), stopping",
                         self.tracker.current_system)
                return
            bootstrap_system(self.tracker)
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()


class HeartbeatEmitter(threading.Thread):
    def __init__(self, tracker: SessionTracker, interval: int = 30):
        super().__init__(daemon=True)
        self.tracker  = tracker
        self.interval = interval
        self._stop    = threading.Event()

    def run(self):
        while not self._stop.wait(self.interval):
            for event in self.tracker.flush_stale():
                send_event(event)
            for snap in self.tracker.snapshot():
                send_event(snap)

    def stop(self):
        self._stop.set()


if __name__ == "__main__":
    validate_paths()
    log.info("Watching %s and %s", GAMELOG_DIR, CHATLOG_DIR)

    agent_start = time.time()
    tracker = SessionTracker()
    bootstrap_system(tracker)

    periodic  = PeriodicBootstrap(tracker)
    heartbeat = HeartbeatEmitter(tracker)
    periodic.start()
    heartbeat.start()

    observer = Observer()
    observer.schedule(
        LogFileHandler(parse_gamelog_line, tracker, agent_start=agent_start),
        GAMELOG_DIR, recursive=False)
    observer.schedule(
        LogFileHandler(parse_chatlog_line, tracker, inject_channel=True, agent_start=agent_start),
        CHATLOG_DIR, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down — flushing open sessions.")
        periodic.stop()
        heartbeat.stop()
        for event in tracker.flush():
            send_event(event)
        observer.stop()
    observer.join()
