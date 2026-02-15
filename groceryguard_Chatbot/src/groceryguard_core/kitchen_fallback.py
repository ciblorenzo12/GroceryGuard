from __future__ import annotations

import re
from typing import Dict, Any, List, Iterable

from .spice_rack_tools import label_scan, ingredient_risk_lookup, kb_lookup


def _extract_ingredients_blob(text: str) -> str | None:
    """I had looked for an ingredient list in the user's message, such as those starting with 'ingredients: ...' or 'Ingredients - ...'."""
    m = re.search(r"ingredients?\s*[:\-]\s*(.+)$", text, flags=re.I | re.S)
    if not m:
        return None
    blob = m.group(1).strip()
    return blob if blob else None


def _guess_single_ingredient(text: str) -> str | None:
    """I had tried to extract a single ingredient name from questions like "is sodium nitrite bad?" or "what about red 40?"."""
    t = text.strip()

    m = re.search(r"\b(is|about|regarding|tell me about|what about)\s+([a-z0-9 \-]+?)(\?|$)", t, flags=re.I)
    if m:
        ing = m.group(2).strip(" .,:;!?")
        if len(ing) >= 3:
            return ing

    # If that hadn't worked, I had tried to grab the last ingredient-looking chunk after a colon
    m2 = re.search(r":\s*([a-z0-9 \-]+)$", t, flags=re.I)
    if m2:
        ing = m2.group(1).strip(" .,:;!?")
        if len(ing) >= 3:
            return ing

    return None


def offline_answer(user_text: str) -> str:
    """When the live API was down or unreachable, I had used my local tools to provide the best answer I could with ingredient scanning and knowledge base lookups."""
    blob = _extract_ingredients_blob(user_text)

    if blob:
        scan = label_scan(blob)
        flags = scan.get("flags", []) or []
        parsed = scan.get("parsed_ingredients", []) or []

        lines: List[str] = []
        lines.append("I couldn’t reach the live GPT API, so I had run in Offline Mode using local tools.\n")
        lines.append("Parsed ingredients (quick split):")
        lines.append(" - " + "\n - ".join(parsed[:30]) + ("" if len(parsed) <= 30 else "\n - ..."))

        if not flags:
            lines.append("\nNo watchlist matches had been found in this label.")
            lines.append("Note: this was not medical advice—just a local watchlist check.")
            return "\n".join(lines)

        lines.append("\nWatchlist flags (heads-up):")
        for f in flags[:12]:
            ing = f.get("ingredient", "")
            why = (f.get("why_it_matters", "") or "").strip()
            cat = (f.get("category", "") or "").strip()

            detail = ingredient_risk_lookup(ing)
            hits = detail.get("hits", []) or []

            lines.append(f"- {ing}" + (f" ({cat})" if cat else ""))
            if why:
                lines.append(f"  Why: {why}")
            if hits:
                h0 = hits[0]
                if h0.get("why_it_matters"):
                    lines.append(f"  From watchlist: {h0['why_it_matters']}")

        lines.append("\nIf you had wanted, you could have told me your goal (avoid dyes, low sodium, allergy, etc.) and I would have helped filter it.")
        lines.append("Reminder: I was not a doctor—if you had a condition/allergy, confirm with a professional.")
        return "\n".join(lines)

    # Not a label. Had tried KB.
    if any(x in user_text.lower() for x in ["what is", "explain", "difference", "define"]):
        kb = kb_lookup(query=user_text, top_k=3)
        matches = kb.get("matches", []) or []
        if matches:
            top = matches[0]
            return (
                "Offline Mode (local KB):\n"
                f"{top.get('title','')}\n"
                f"{top.get('answer','')}\n\n"
                "If you had wanted, you could have pasted an ingredient label and I would have scanned it too."
            )

    # Single ingredient fallback
    ing = _guess_single_ingredient(user_text)
    if ing:
        detail = ingredient_risk_lookup(ing)
        hits = detail.get("hits", []) or []
        if hits:
            h0 = hits[0]
            return (
                "Offline Mode (local watchlist):\n"
                f"Ingredient: {ing}\n"
                f"Category: {h0.get('category','')}\n"
                f"Why it may be flagged: {h0.get('why_it_matters','')}\n\n"
                "If you paste the full label, I can scan everything at once."
            )
        return (
            "Offline Mode:\n"
            f"I checked the local watchlist and didn’t find a match for: {ing}\n\n"
            "If you paste the full label (ingredients: ...), I can scan it."
        )

    # Generic fallback
    return (
        "Offline Mode:\n"
        "I can’t reach the live GPT API right now. If you paste an ingredient label in this format:\n"
        "ingredients: item1, item2, item3\n"
        "…I can still scan it locally and flag watchlist items."
    )


def stream_text(text: str, chunk_chars: int = 90) -> Iterable[str]:
    i = 0
    while i < len(text):
        yield text[i : i + chunk_chars]
        i += chunk_chars
