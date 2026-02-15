from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    override = os.environ.get("GROCERYGUARD_DATA_DIR")
    return Path(override) if override else (_project_root() / "data")


WATCHLIST_PATH = data_dir() / "additives_watchlist.csv"
KB_PATH = data_dir() / "groceryguard_kb.md"


def _normalize(s: str) -> str:
    """Made text lowercase and cleaned up extra spaces."""
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _split_ingredients(label_text: str) -> List[str]:
    """Parsed ingredient list from label text. I had removed parentheses and split by commas/semicolons."""
    cleaned = re.sub(r"\([^)]*\)", "", label_text)
    parts = re.split(r"[;,]", cleaned)
    items = []
    for p in parts:
        t = _normalize(p)
        t = t.strip(".: ")
        if t:
            items.append(t)
    return items


def _load_watchlist() -> List[Dict[str, str]]:
    """Loaded the additives watchlist from CSV if it existed."""
    if not WATCHLIST_PATH.exists():
        return []

    rows: List[Dict[str, str]] = []
    with WATCHLIST_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


def _load_kb() -> Dict[str, str]:
    """Read the knowledge base markdown file and parsed it into sections. Format was ## Title followed by body text."""
    if not KB_PATH.exists():
        return {}

    text = KB_PATH.read_text(encoding="utf-8")
    blocks = re.split(r"\n(?=## )", text)
    kb: Dict[str, str] = {}
    for b in blocks:
        b = b.strip()
        if not b.startswith("## "):
            continue
        lines = b.splitlines()
        title = lines[0].replace("## ", "").strip()
        body = "\n".join(lines[1:]).strip()
        if title and body:
            kb[title] = body
    return kb


def kb_lookup(query: str, top_k: int = 3) -> Dict[str, Any]:
    """Searched the knowledge base by scoring titles and content against the query."""
    kb = _load_kb()
    q = _normalize(query)

    scored = []
    for title, body in kb.items():
        t = _normalize(title)
        score = 0
        if q in t:
            score += 5
        for w in q.split():
            if w in t:
                score += 1
            if w in _normalize(body):
                score += 0.5
        if score > 0:
            scored.append((score, title, body))

    scored.sort(key=lambda x: x[0], reverse=True)
    matches = [{"title": t, "answer": b} for _, t, b in scored[:top_k]]

    return {
        "query": query,
        "matches": matches,
        "note": "No match found in local KB." if not matches else "Matched from local KB.",
    }


# ---------- Tool 2: ingredient risk lookup ----------
def ingredient_risk_lookup(ingredient: str) -> Dict[str, Any]:
    watchlist = _load_watchlist()
    needle = _normalize(ingredient)

    hits = []
    for row in watchlist:
        name = _normalize(row.get("name", ""))
        aliases = _normalize(row.get("common_aliases", ""))
        alias_list = [a.strip() for a in aliases.split(";") if a.strip()]

        if needle == name or needle in alias_list:
            hits.append(
                {
                    "matched_name": row.get("name", ""),
                    "category": row.get("category", ""),
                    "why_it_matters": row.get("why_it_matters", ""),
                    "aliases": row.get("common_aliases", ""),
                }
            )

    return {
        "ingredient": ingredient,
        "hits": hits,
        "note": "No watchlist match." if not hits else "Matched watchlist entry.",
    }


# ---------- Optional helper used by the model ----------
def label_scan(label_text: str) -> Dict[str, Any]:
    items = _split_ingredients(label_text)
    watchlist = _load_watchlist()

    # Build lookup set for fast matching
    known = set()
    meta = {}

    for row in watchlist:
        nm = _normalize(row.get("name", ""))
        if nm:
            known.add(nm)
            meta[nm] = row
        aliases = _normalize(row.get("common_aliases", ""))
        for a in [x.strip() for x in aliases.split(";") if x.strip()]:
            known.add(a)
            meta[a] = row

    flags = []
    for ing in items:
        if ing in known:
            row = meta.get(ing, {})
            flags.append(
                {
                    "ingredient": ing,
                    "category": row.get("category", ""),
                    "why_it_matters": row.get("why_it_matters", ""),
                }
            )

    return {
        "parsed_ingredients": items,
        "flags": flags,
        "note": "Flags are a heads-up, not medical advice.",
    }


# ---------- Tool specs for Responses API ----------
# Tool schema format shown in OpenAI function calling guide. :contentReference[oaicite:1]{index=1}
TOOL_SPECS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "kb_lookup",
            "description": "Search a local GroceryGuard knowledge base (KB) for quick explanations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 5},
                },
                "required": ["query", "top_k"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ingredient_risk_lookup",
            "description": "Check if an ingredient is on the local additives watchlist and return why it may be flagged.",
            "parameters": {
                "type": "object",
                "properties": {"ingredient": {"type": "string"}},
                "required": ["ingredient"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "label_scan",
            "description": "Parse a raw ingredient label string and flag any watchlist matches.",
            "parameters": {
                "type": "object",
                "properties": {"label_text": {"type": "string"}},
                "required": ["label_text"],
            },
        },
    },
]


def dispatch_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if tool_name == "kb_lookup":
        return kb_lookup(**args)
    if tool_name == "ingredient_risk_lookup":
        return ingredient_risk_lookup(**args)
    if tool_name == "label_scan":
        return label_scan(**args)
    return {"error": f"Unknown tool: {tool_name}", "args": args}


def safe_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)