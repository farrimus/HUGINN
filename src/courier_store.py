# src/courier_store.py
"""
Courier contract persistence.

Shared single file: data/courier/contracts.json
All wallets read/write this file. Uses fcntl exclusive locking for the full
read-modify-write cycle to prevent TOCTOU race conditions (e.g., two pilots
claiming the same contract simultaneously).
"""
import datetime
import fcntl
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field, fields
from typing import Optional

log = logging.getLogger(__name__)


def _contracts_path() -> str:
    from src.config import get_data_path
    return get_data_path("courier/contracts.json", env_specific=False)


@dataclass
class CourierContract:
    id: str
    poster_wallet: str
    poster_name: str
    item_description: str
    from_location: str
    to_location: str
    reward_description: str
    status: str  # "open" | "claimed" | "in_transit" | "delivered" | "cancelled"
    claimed_by_wallet: Optional[str] = None
    claimed_by_name: Optional[str] = None
    claimed_at: Optional[str] = None
    delivered_at: Optional[str] = None
    created_at: str = ""
    expires_at: Optional[str] = None


def _now() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_raw(f) -> list[dict]:
    """Read and parse contracts from an open file handle. Returns [] on empty/corrupt."""
    f.seek(0)
    content = f.read()
    if not content.strip():
        return []
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, ValueError):
        log.warning("courier_store: contracts.json is corrupt, starting fresh")
    return []


def _to_contract(d: dict) -> CourierContract:
    known = {f.name for f in fields(CourierContract)}
    return CourierContract(**{k: v for k, v in d.items() if k in known})


def load_contracts() -> list[CourierContract]:
    """Load all contracts (read-only, no lock needed for reads)."""
    path = _contracts_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            raw = _load_raw(f)
        return [_to_contract(d) for d in raw]
    except Exception as e:
        log.warning("courier_store: failed to load contracts: %s", e)
        return []


def locked_mutate(fn) -> CourierContract | None:
    """
    Open contracts.json with an exclusive lock, call fn(contracts) -> (contracts, result),
    write back, return result. Creates the file if it doesn't exist.

    fn signature: fn(list[CourierContract]) -> tuple[list[CourierContract], Any]
    """
    path = _contracts_path()
    # Open for read+write, create if absent
    flags = os.O_RDWR | os.O_CREAT
    fd = os.open(path, flags, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        with os.fdopen(fd, "r+") as f:
            fd = None  # fdopen owns it now
            raw = _load_raw(f)
            contracts = [_to_contract(d) for d in raw]
            contracts, result = fn(contracts)
            f.seek(0)
            f.truncate()
            json.dump([asdict(c) for c in contracts], f, indent=2)
        return result
    except Exception as e:
        log.warning("courier_store: mutation failed: %s", e)
        raise
    finally:
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            except OSError:
                pass


def create_contract(
    poster_wallet: str,
    poster_name: str,
    item_description: str,
    from_location: str,
    to_location: str,
    reward_description: str,
    expires_at: Optional[str] = None,
) -> CourierContract:
    contract = CourierContract(
        id=str(uuid.uuid4()),
        poster_wallet=poster_wallet,
        poster_name=poster_name,
        item_description=item_description,
        from_location=from_location,
        to_location=to_location,
        reward_description=reward_description,
        status="open",
        created_at=_now(),
        expires_at=expires_at,
    )

    def _mutate(contracts):
        contracts.append(contract)
        return contracts, contract

    locked_mutate(_mutate)
    return contract


def claim_contract(contract_id: str, claimer_wallet: str, claimer_name: str) -> CourierContract:
    """Claim an open contract. Raises ValueError if not found or not open."""
    result = []

    def _mutate(contracts):
        for c in contracts:
            if c.id == contract_id:
                if c.status != "open":
                    raise ValueError(f"Contract is not open (status={c.status})")
                c.status = "claimed"
                c.claimed_by_wallet = claimer_wallet
                c.claimed_by_name = claimer_name
                c.claimed_at = _now()
                result.append(c)
                return contracts, c
        raise ValueError(f"Contract not found: {contract_id}")

    return locked_mutate(_mutate)


def update_status(contract_id: str, new_status: str, requester_wallet: str) -> CourierContract:
    """Update status (in_transit or delivered). Requester must be the claimer."""
    def _mutate(contracts):
        for c in contracts:
            if c.id == contract_id:
                if c.claimed_by_wallet != requester_wallet:
                    raise PermissionError("Only the claimer can update status")
                if new_status not in ("in_transit", "delivered"):
                    raise ValueError(f"Invalid status: {new_status}")
                c.status = new_status
                if new_status == "delivered":
                    c.delivered_at = _now()
                return contracts, c
        raise ValueError(f"Contract not found: {contract_id}")

    return locked_mutate(_mutate)


def cancel_contract(contract_id: str, requester_wallet: str) -> CourierContract:
    """Cancel a contract. Requester must be the poster."""
    def _mutate(contracts):
        for c in contracts:
            if c.id == contract_id:
                if c.poster_wallet != requester_wallet:
                    raise PermissionError("Only the poster can cancel")
                if c.status in ("delivered", "cancelled"):
                    raise ValueError(f"Cannot cancel contract with status={c.status}")
                c.status = "cancelled"
                return contracts, c
        raise ValueError(f"Contract not found: {contract_id}")

    return locked_mutate(_mutate)
