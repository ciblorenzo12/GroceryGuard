from __future__ import annotations

import json
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from .guardrail_gate import redact_secrets

LOG_PATH = Path("var/guard_events.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

PRICE_PER_1M = {
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
}

def _hash_ip(ip: str) -> str:
    """Hashed IP addresses for privacy - I only kept the first 12 chars of the hash."""
    h = hashlib.sha256(ip.encode("utf-8")).hexdigest()
    return h[:12]

def _base_model_name(model: str) -> str:
    """Extracted base model name in case there was version info like gpt-4o-mini-2024-07-18."""
    if not model:
        return ""
    return model.split(":")[0]

def _estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    base = _base_model_name(model)
    rates = PRICE_PER_1M.get(base)
    if not rates:
        return None
    return (input_tokens * (rates["in"] / 1_000_000.0)) + (output_tokens * (rates["out"] / 1_000_000.0))

def write_event(
    event_type: str,
    conversation_id: str,
    ip: str,
    user_text: str,
    *,
    refused: bool,
    tool_count: int = 0,
    latency_ms: Optional[int] = None,
    note: str = "",

    # New fields (Task 6)
    model: str = "",
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    est_cost_usd: Optional[float] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
    facts_learned: Optional[int] = None,
    tool_names: Optional[Sequence[str]] = None,
    error_code: str = "",
    error_message: str = "",
) -> None:
    if input_tokens is None and prompt_tokens is not None:
        input_tokens = prompt_tokens
    if output_tokens is None and completion_tokens is not None:
        output_tokens = completion_tokens
    if est_cost_usd is None and cost_usd is not None:
        est_cost_usd = cost_usd

    row: Dict[str, Any] = {
        "ts_unix": time.time(),
        "event_type": event_type,
        "conversation_id": conversation_id,
        "ip_hash": _hash_ip(ip or "unknown"),
        "refused": refused,
        "tool_count": tool_count,
        "latency_ms": latency_ms,
        "user_preview": redact_secrets((user_text or "")[:180]),
        "note": note,
    }

    if model:
        row["model"] = model
    if tool_names:
        row["tool_names"] = list(tool_names)

    if input_tokens is not None:
        row["input_tokens"] = input_tokens
    if output_tokens is not None:
        row["output_tokens"] = output_tokens

    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    if total_tokens is not None:
        row["total_tokens"] = total_tokens

    if est_cost_usd is None and model and input_tokens is not None and output_tokens is not None:
        est_cost_usd = _estimate_cost_usd(model, input_tokens, output_tokens)
    if est_cost_usd is not None:
        row["est_cost_usd"] = round(float(est_cost_usd), 8)

    if facts_learned is not None:
        row["facts_learned"] = int(facts_learned)

    if error_code:
        row["error_code"] = error_code
    if error_message:
        row["error_message"] = redact_secrets((error_message or "")[:240])

    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")