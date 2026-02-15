import json
from dataclasses import dataclass, asdict
from pathlib import Path
from threading import Lock
from typing import List, Dict

BASE = Path("var/conversations")
BASE.mkdir(parents=True, exist_ok=True)
_lock = Lock()

@dataclass
class Msg:
    role: str
    content: str

def _safe_path(conversation_id: str) -> Path:
    """Converted conversation ID to a safe filename, preventing directory traversal attacks."""
    safe = "".join(ch for ch in conversation_id if ch.isalnum() or ch in "-_")[:80]
    return BASE / f"{safe}.json"

def load_convo(conversation_id: str) -> List[Msg]:
    """Loaded all messages for a conversation from disk."""
    p = _safe_path(conversation_id)
    with _lock:
        if not p.exists():
            return []
        data = json.loads(p.read_text(encoding="utf-8"))
    return [Msg(**m) for m in data.get("messages", [])]

def save_convo(conversation_id: str, messages: List[Msg]) -> None:
    """Wrote the full conversation to disk as JSON."""
    p = _safe_path(conversation_id)
    payload = {"messages": [asdict(m) for m in messages]}
    with _lock:
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")

def append_msg(conversation_id: str, role: str, content: str) -> None:
    """Added one message to the conversation and saved."""
    msgs = load_convo(conversation_id)
    msgs.append(Msg(role=role, content=content))
    save_convo(conversation_id, msgs)

def get_last_n(conversation_id: str, n: int) -> List[Dict[str, str]]:
    """Got the last N messages from a conversation."""
    msgs = load_convo(conversation_id)
    tail = msgs[-n:] if n > 0 else []
    return [{"role": m.role, "content": m.content} for m in tail]