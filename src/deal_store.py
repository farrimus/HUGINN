# src/deal_store.py
import os
import re
import json
import time
import logging
from dataclasses import dataclass, asdict
from typing import Optional
import datetime

log = logging.getLogger(__name__)

_SAFE_RE = re.compile(r'[^a-zA-Z0-9_-]')

DEAL_MESSAGES_DEFAULT = 20
DEAL_DURATION_HOURS_DEFAULT = 24


def _safe(s: str) -> str:
    return _SAFE_RE.sub('', s.lower())[:80]


@dataclass
class DealRecord:
    address: str
    structure_id: str
    payment_method: str      # "item" | "sui" | "info"
    messages_remaining: int
    expires_at: float        # unix timestamp
    created_at: str          # ISO8601


class DealStore:
    def __init__(self, base_dir: str = None):
        from src.config import get_data_path

        if base_dir is None:
            base_dir = get_data_path("deals", env_specific=True)
        self._base = base_dir

    def _path(self, address: str, structure_id: str) -> str:
        return os.path.join(self._base, f"{_safe(address)}-{_safe(structure_id)}.json")

    def _save(self, rec: DealRecord) -> None:
        os.makedirs(self._base, exist_ok=True)
        try:
            with open(self._path(rec.address, rec.structure_id), "w") as f:
                json.dump(asdict(rec), f)
        except Exception as e:
            log.warning("DealStore._save failed: %s", e)

    def issue(
        self,
        address: str,
        structure_id: str,
        payment_method: str,
        messages: int = DEAL_MESSAGES_DEFAULT,
        duration_hours: int = DEAL_DURATION_HOURS_DEFAULT,
    ) -> DealRecord:
        """Create or overwrite a PATRON deal for this address + structure."""
        rec = DealRecord(
            address=address.lower(),
            structure_id=structure_id,
            payment_method=payment_method,
            messages_remaining=messages,
            expires_at=time.time() + duration_hours * 3600,
            created_at=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        self._save(rec)
        return rec

    def get(self, address: str, structure_id: str) -> Optional[DealRecord]:
        path = self._path(address, structure_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            return DealRecord(**data)
        except Exception as e:
            log.warning("DealStore.get failed for %s: %s", address[:12], e)
            return None

    def consume_message(self, address: str, structure_id: str) -> bool:
        """
        Decrement messages_remaining and return True if the deal is still valid.
        Returns False if deal is missing, expired, or exhausted.
        """
        rec = self.get(address, structure_id)
        if rec is None:
            return False
        if time.time() > rec.expires_at:
            return False
        if rec.messages_remaining <= 0:
            return False
        rec.messages_remaining -= 1
        self._save(rec)
        return True


# Module-level singleton
deal_store = DealStore()
