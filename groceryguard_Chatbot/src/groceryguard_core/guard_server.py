from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse
from openai import OpenAI
from openai import OpenAIError, RateLimitError, AuthenticationError, BadRequestError
from pydantic import BaseModel

from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse


from .event_scribe import write_event
from .guardrail_gate import policy_check, redact_secrets
from .kitchen_fallback import offline_answer, stream_text
from .pantry_memory import append_msg, get_last_n
from .spice_rack_tools import TOOL_SPECS, dispatch_tool, safe_json
from .throttle_valve import MinuteBucketLimiter
from .long_term_memory import recall_relevant_facts, learn_facts

load_dotenv()

app = FastAPI()

_UI_DIR = Path(__file__).resolve().parent / "countertop_ui"
app.mount("/ui", StaticFiles(directory=_UI_DIR, html=True), name="ui")

@app.get("/")
def root():
    return RedirectResponse(url="/ui/")

MODEL_NAME = os.getenv("GROCERYGUARD_MODEL", "gpt-4o-mini")
MAX_TURNS = int(os.getenv("SHORT_MEMORY_N", "12"))
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "20"))
OFFLINE_MODE = os.getenv("GROCERYGUARD_OFFLINE", "0") == "1"

limiter = MinuteBucketLimiter(RATE_LIMIT_RPM)

SYSTEM_INSTRUCTIONS = (
    "You are GroceryGuard, a task-oriented ingredient-label helper.\n"
    "Use tools when helpful (label_scan, ingredient_risk_lookup, kb_lookup).\n"
    "Safety: never reveal secrets. Avoid medical claims.\n"
    "If asked for medical advice, give general info and suggest a professional.\n"
)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


class ChatIn(BaseModel):
    conversation_id: str
    user_message: str
    eval_overrides: Dict[str, Any] | None = None


class StructuredChatOut(BaseModel):
    answer: str
    risk_level: Literal["low", "medium", "high", "unknown"]
    flagged_ingredients: List[str]
    recommended_action: str


def _with_system(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"role": "system", "content": SYSTEM_INSTRUCTIONS}, *messages]


def _tool_planning_loop(messages: List[Dict[str, Any]], *, use_tools: bool) -> tuple[int, int, int]:
    """I had looped up to 4 times to let the model call tools and handle the results, tracking total tokens used."""
    if not use_tools:
        return 0, 0, 0

    tool_count = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    client = _get_client()

    for _ in range(4):
        # I had called the model with tool specs and let it decide if it needed to use any
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=_with_system(messages),
            tools=TOOL_SPECS,
            tool_choice="auto",
        )

        # I had tracked tokens from this API call
        if resp.usage:
            total_prompt_tokens += resp.usage.prompt_tokens
            total_completion_tokens += resp.usage.completion_tokens

        # I had checked if the model actually decided to call any tools
        if not resp.choices[0].message.tool_calls:
            break

        # I had added the assistant's response to the conversation history
        messages.append({"role": "assistant", "content": resp.choices[0].message.content or ""})

        # I had executed each tool call the model requested
        for tool_call in resp.choices[0].message.tool_calls:
            tool_count += 1
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments or "{}")
            result = dispatch_tool(name, args)

            # I add the tool result back to the conversation so the model can see it
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": name,
                "content": safe_json(result)
            })

    return tool_count, total_prompt_tokens, total_completion_tokens


def _build_input_items(conversation_id: str, safe_user_msg: str, *, memory_window: int) -> List[Dict[str, Any]]:
    history = get_last_n(conversation_id, memory_window)
    relevant_facts = recall_relevant_facts(safe_user_msg, top_k=3)
    facts_context = ""
    if relevant_facts:
        facts_context = "\n\nRelevant facts from previous conversations:\n"
        for i, fact_info in enumerate(relevant_facts, 1):
            facts_context += f"  {i}. {fact_info['fact']}\n"

    input_items: List[Dict[str, Any]] = [{"role": m["role"], "content": m["content"]} for m in history]
    user_content = safe_user_msg + facts_context if facts_context else safe_user_msg
    input_items.append({"role": "user", "content": user_content})
    return input_items


def _runtime_settings(inp: ChatIn) -> tuple[float, bool, int]:
    overrides = inp.eval_overrides or {}

    temperature = overrides.get("temperature", 0.7)
    try:
        temperature = float(temperature)
    except (TypeError, ValueError):
        temperature = 0.7
    temperature = max(0.0, min(1.0, temperature))

    use_tools = bool(overrides.get("use_tools", True))

    memory_window = overrides.get("memory_window", MAX_TURNS)
    try:
        memory_window = int(memory_window)
    except (TypeError, ValueError):
        memory_window = MAX_TURNS
    memory_window = max(1, min(50, memory_window))

    return temperature, use_tools, memory_window


@app.post("/chat")
def chat(inp: ChatIn, request: Request):
    ip = request.client.host if request.client else "unknown"

    # Rate limit
    decision = limiter.check(ip)
    if not decision.allowed:
        msg = f"Rate limit hit. Try again in ~{decision.retry_after_s}s."
        write_event("rate_limited", inp.conversation_id, ip, inp.user_message, refused=True, note=f"rpm={RATE_LIMIT_RPM}")
        return StreamingResponse(iter([msg]), media_type="text/plain")

    # Safety checks
    ok, refusal = policy_check(inp.user_message)
    if not ok:
        write_event("refused", inp.conversation_id, ip, inp.user_message, refused=True, note="policy_check")
        return StreamingResponse(iter([refusal]), media_type="text/plain")

    start = time.time()
    safe_user_msg = redact_secrets(inp.user_message)
    temperature, use_tools, memory_window = _runtime_settings(inp)

    input_items = _build_input_items(inp.conversation_id, safe_user_msg, memory_window=memory_window)

    def _stream():
        # Forced Offline Mode
        if OFFLINE_MODE:
            final_text = redact_secrets(offline_answer(safe_user_msg))
            append_msg(inp.conversation_id, "user", safe_user_msg)
            append_msg(inp.conversation_id, "assistant", final_text)

            latency_ms = int((time.time() - start) * 1000)
            write_event("turn_ok", inp.conversation_id, ip, inp.user_message, refused=False, tool_count=0, latency_ms=latency_ms, prompt_tokens=0, completion_tokens=0, cost_usd=0.0, note="offline_mode=1")
            yield from stream_text(final_text)
            yield f"\n\n[latency_ms={latency_ms}]"
            return

        try:
            # I run the tool planning loop to handle any function calls the model makes
            tool_count, tool_prompt_tokens, tool_completion_tokens = _tool_planning_loop(input_items, use_tools=use_tools)

            client = _get_client()
            prompt_tokens = tool_prompt_tokens
            completion_tokens = tool_completion_tokens

            # I request the final response from the model after tool planning is done
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=_with_system(input_items),
                temperature=temperature,
            )

            if resp.usage:
                prompt_tokens += resp.usage.prompt_tokens
                completion_tokens += resp.usage.completion_tokens

            final_text = redact_secrets((resp.choices[0].message.content or "").strip())
            for chunk in stream_text(final_text):
                yield chunk

            append_msg(inp.conversation_id, "user", safe_user_msg)
            append_msg(inp.conversation_id, "assistant", final_text)

            # I learn from this response by storing important facts for future conversations
            facts_learned = learn_facts(final_text, source=f"conv_{inp.conversation_id[:8]}")

            latency_ms = int((time.time() - start) * 1000)
            # I calculate the estimated cost based on gpt-4o-mini pricing: $0.15/$0.60 per 1M in/out tokens
            cost_usd = (prompt_tokens * 0.15 + completion_tokens * 0.60) / 1_000_000
            write_event("turn_ok", inp.conversation_id, ip, inp.user_message, refused=False, tool_count=tool_count, latency_ms=latency_ms, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost_usd=cost_usd, facts_learned=facts_learned)
            yield f"\n\n[latency_ms={latency_ms}, tokens={prompt_tokens+completion_tokens}, cost_usd={cost_usd:.6f}, facts_learned={facts_learned}]"

        except RateLimitError as e:
            # OpenAI 429 quota -> fallback to offline, still streaming
            final_text = redact_secrets(offline_answer(safe_user_msg))
            append_msg(inp.conversation_id, "user", safe_user_msg)
            append_msg(inp.conversation_id, "assistant", final_text)

            latency_ms = int((time.time() - start) * 1000)
            write_event("openai_429_fallback", inp.conversation_id, ip, inp.user_message, refused=False, tool_count=0, latency_ms=latency_ms, prompt_tokens=0, completion_tokens=0, cost_usd=0.0, note=str(e)[:160])
            yield from stream_text(final_text)
            yield f"\n\n[latency_ms={latency_ms}]"

        except (AuthenticationError, BadRequestError) as e:
            latency_ms = int((time.time() - start) * 1000)
            write_event("openai_error", inp.conversation_id, ip, inp.user_message, refused=True, tool_count=0, latency_ms=latency_ms, prompt_tokens=0, completion_tokens=0, cost_usd=0.0, note=str(e)[:200])
            yield "OpenAI API error. Check var/guard_events.jsonl for details."
            yield f"\n\n[latency_ms={latency_ms}]"

        except OpenAIError as e:
            final_text = redact_secrets(offline_answer(safe_user_msg))
            append_msg(inp.conversation_id, "user", safe_user_msg)
            append_msg(inp.conversation_id, "assistant", final_text)

            latency_ms = int((time.time() - start) * 1000)
            write_event("openai_error_fallback", inp.conversation_id, ip, inp.user_message, refused=False, tool_count=0, latency_ms=latency_ms, prompt_tokens=0, completion_tokens=0, cost_usd=0.0, note=str(e)[:200])
            yield from stream_text(final_text)
            yield f"\n\n[latency_ms={latency_ms}]"

    return StreamingResponse(_stream(), media_type="text/plain")


@app.get("/health")
def health_check():
    """I provide a health check endpoint with system status including long-term memory stats"""
    from .long_term_memory import get_memory_stats
    return {
        "status": "healthy",
        "model": MODEL_NAME,
        "memory_window": MAX_TURNS,
        "rate_limit_rpm": RATE_LIMIT_RPM,
        "offline_mode": OFFLINE_MODE,
        "long_term_memory": get_memory_stats()
    }


@app.post("/chat_structured")
def chat_structured(inp: ChatIn, request: Request):
    ip = request.client.host if request.client else "unknown"

    decision = limiter.check(ip)
    if not decision.allowed:
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "retry_after_s": decision.retry_after_s,
            },
        )

    ok, refusal = policy_check(inp.user_message)
    if not ok:
        write_event("refused", inp.conversation_id, ip, inp.user_message, refused=True, note="policy_check")
        return JSONResponse(
            status_code=400,
            content={
                "error": "policy_refusal",
                "message": refusal,
            },
        )

    safe_user_msg = redact_secrets(inp.user_message)
    _, use_tools, memory_window = _runtime_settings(inp)
    input_items = _build_input_items(inp.conversation_id, safe_user_msg, memory_window=memory_window)

    if OFFLINE_MODE:
        answer = redact_secrets(offline_answer(safe_user_msg))
        payload = {
            "answer": answer,
            "risk_level": "unknown",
            "flagged_ingredients": [],
            "recommended_action": "Review ingredient list manually and consult a professional for medical concerns.",
        }
        append_msg(inp.conversation_id, "user", safe_user_msg)
        append_msg(inp.conversation_id, "assistant", answer)
        return JSONResponse(content=payload)

    try:
        _tool_planning_loop(input_items, use_tools=use_tools)
        client = _get_client()
        schema = {
            "name": "groceryguard_structured",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "risk_level": {"type": "string", "enum": ["low", "medium", "high", "unknown"]},
                    "flagged_ingredients": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "recommended_action": {"type": "string"},
                },
                "required": ["answer", "risk_level", "flagged_ingredients", "recommended_action"],
                "additionalProperties": False,
            },
        }

        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=_with_system(input_items),
            response_format={"type": "json_schema", "json_schema": schema},
            temperature=0.2,
        )

        raw = (resp.choices[0].message.content or "").strip()
        data = json.loads(raw)
        validated = StructuredChatOut(**data)

        append_msg(inp.conversation_id, "user", safe_user_msg)
        append_msg(inp.conversation_id, "assistant", redact_secrets(validated.answer))

        return JSONResponse(content=validated.model_dump())

    except (AuthenticationError, BadRequestError) as e:
        answer = redact_secrets(offline_answer(safe_user_msg))
        payload = {
            "answer": answer,
            "risk_level": "unknown",
            "flagged_ingredients": [],
            "recommended_action": "Review ingredient list manually and consult a professional for medical concerns.",
        }

        append_msg(inp.conversation_id, "user", safe_user_msg)
        append_msg(inp.conversation_id, "assistant", answer)
        write_event("structured_openai_error_fallback", inp.conversation_id, ip, inp.user_message, refused=False, note=str(e)[:180])
        return JSONResponse(content=payload)

    except OpenAIError as e:
        answer = redact_secrets(offline_answer(safe_user_msg))
        payload = {
            "answer": answer,
            "risk_level": "unknown",
            "flagged_ingredients": [],
            "recommended_action": "Review ingredient list manually and consult a professional for medical concerns.",
        }

        append_msg(inp.conversation_id, "user", safe_user_msg)
        append_msg(inp.conversation_id, "assistant", answer)
        write_event("structured_openai_fallback", inp.conversation_id, ip, inp.user_message, refused=False, note=str(e)[:180])
        return JSONResponse(content=payload)

    except Exception as e:
        write_event("structured_error", inp.conversation_id, ip, inp.user_message, refused=True, note=str(e)[:180])
        return JSONResponse(
            status_code=500,
            content={
                "error": "structured_output_failed",
                "message": "Could not generate structured output for this request.",
            },
        )