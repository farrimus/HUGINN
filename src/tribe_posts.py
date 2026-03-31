# src/tribe_posts.py
"""
Tribe post board persistence.

Per-tribe shared notepad. Persisted at data/tribe/{tribe_id}/posts.json.
Rolling cap of 200 posts per tribe. SSE fan-out for live updates.
"""
import asyncio
import datetime
import fcntl
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, fields

log = logging.getLogger(__name__)

MAX_POSTS = 200
DISPLAY_POSTS = 30
MAX_MESSAGE_LEN = 280

# tribe_id -> list of SSE queues
_post_sse_clients: dict[int, list[asyncio.Queue]] = {}


def _posts_path(tribe_id: int) -> str:
    from src.config import get_data_path
    return get_data_path(f"tribe/{tribe_id}/posts.json", env_specific=False)


def _now() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class TribePost:
    id: str
    tribe_id: int
    poster_wallet: str
    poster_name: str
    message: str
    created_at: str


def _to_post(d: dict) -> TribePost:
    known = {f.name for f in fields(TribePost)}
    return TribePost(**{k: v for k, v in d.items() if k in known})


def _load_raw(f) -> list[dict]:
    f.seek(0)
    content = f.read()
    if not content.strip():
        return []
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, ValueError):
        log.warning("tribe_posts: posts file corrupt, starting fresh")
    return []


def load_posts(tribe_id: int) -> list[TribePost]:
    """Load all posts (read-only, no lock). Returns [] on missing/corrupt."""
    path = _posts_path(tribe_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            raw = _load_raw(f)
        return [_to_post(d) for d in raw]
    except Exception as e:
        log.warning("tribe_posts: failed to load posts tribe=%s: %s", tribe_id, e)
        return []


def _locked_mutate(tribe_id: int, fn):
    """Open posts.json with exclusive lock, call fn(posts) -> (posts, result), write back."""
    path = _posts_path(tribe_id)
    flags = os.O_RDWR | os.O_CREAT
    fd = os.open(path, flags, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        with os.fdopen(fd, "r+") as f:
            fd = None
            raw = _load_raw(f)
            posts = [_to_post(d) for d in raw]
            posts, result = fn(posts)
            f.seek(0)
            f.truncate()
            json.dump([asdict(p) for p in posts], f, indent=2)
        return result
    except Exception as e:
        log.warning("tribe_posts: mutation failed tribe=%s: %s", tribe_id, e)
        raise
    finally:
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            except OSError:
                pass


def create_post(tribe_id: int, poster_wallet: str, poster_name: str, message: str) -> TribePost:
    post = TribePost(
        id=str(uuid.uuid4()),
        tribe_id=tribe_id,
        poster_wallet=poster_wallet,
        poster_name=poster_name,
        message=message,
        created_at=_now(),
    )

    def _mutate(posts):
        posts.append(post)
        return posts[-MAX_POSTS:], post

    _locked_mutate(tribe_id, _mutate)
    _broadcast(tribe_id, {"type": "new_post", "post": asdict(post)})
    return post


def delete_post(tribe_id: int, post_id: str, requester_wallet: str) -> str:
    def _mutate(posts):
        for p in posts:
            if p.id == post_id:
                if p.poster_wallet != requester_wallet:
                    raise PermissionError("Only the author can delete this post")
                updated = [x for x in posts if x.id != post_id]
                return updated, post_id
        raise ValueError(f"Post not found: {post_id}")

    result = _locked_mutate(tribe_id, _mutate)
    _broadcast(tribe_id, {"type": "post_deleted", "post_id": post_id})
    return result


def subscribe(tribe_id: int) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _post_sse_clients.setdefault(tribe_id, []).append(q)
    return q


def unsubscribe(tribe_id: int, q: asyncio.Queue) -> None:
    try:
        _post_sse_clients[tribe_id].remove(q)
    except (KeyError, ValueError):
        pass


def _broadcast(tribe_id: int, event: dict) -> None:
    for q in list(_post_sse_clients.get(tribe_id, [])):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass
