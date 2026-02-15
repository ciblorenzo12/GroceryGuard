from __future__ import annotations
import re
from typing import Tuple

# I use these patterns to scan messages and catch API keys, environment variables, and other secrets
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_]{10,}"),  # OpenAI-style keys (min 10 chars, allow underscore)
    re.compile(r"sk_live_[A-Za-z0-9_]+", re.I),  # OpenAI live keys
    re.compile(r"sk-proj-[A-Za-z0-9]{16,}"),  # OpenAI project keys
    re.compile(r"sk-[A-Za-z0-9]{6,}"),  # Shorter sk- keys (for test cases)
    re.compile(r"OPENAI_API_KEY\s*=\s*\S+", re.I),  # Env variable assignments
    re.compile(r"API_KEY\d*=sk-[A-Za-z0-9]+", re.I),  # API_KEY1=sk-abc123 style
    re.compile(r"api[_-]?key\s*[:=]\s*['\"]?\S+", re.I),  # Generic API key patterns
    re.compile(r"([A-Z0-9]{4}-){3}[A-Z0-9]{4}", re.I),  # Generic XXXX-XXXX-XXXX-XXXX keys (no word boundary)
    re.compile(r"[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}", re.I),  # Fallback for XXXX-XXXX-XXXX-XXXX
]

def redact_secrets(text: str) -> str:
    """I scan the text for any secrets and replace them with [REDACTED] so they never hit the logs"""
    out = text or ""
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out

def policy_check(user_text: str) -> Tuple[bool, str]:
    """
    I check if a user's message violates basic safety policies on the server side.
    I reject messages that try to share secrets, ask for self-harm instructions, or request weapon/explosive info.
    If something fails the check, I return False plus a friendly explanation why I can't help.
    """
    t = (user_text or "").strip()
    low = t.lower()

    # Secrets
    for p in _SECRET_PATTERNS:
        if p.search(t):
            return False, (
                "I can’t help with sharing or handling keys/secrets. "
                "Please remove them from your message and try again."
            )

    # Self-harm / suicide instructions
    if any(x in low for x in ["how to kill myself", "suicide method", "kill myself"]):
        return False, (
            "I can’t help with that. If you’re in immediate danger or feel unsafe, "
            "call local emergency services or a trusted person right now."
        )

    # Weapons/explosives how-to
    if any(x in low for x in ["make a bomb", "build a bomb", "homemade explosive"]):
        return False, "I can’t help with instructions for weapons or explosives."

    # If we get here, the message is safe to proceed with
    return True, ""