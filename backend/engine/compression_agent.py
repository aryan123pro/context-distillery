from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .llm_client import LlmClient


COMPRESSION_SYSTEM = """
You are the Compression Agent in a multi-agent context compression engine.

You MUST output STRICT JSON matching the provided schema.

Your job:
- Distill past conversation and current working memory into a new structured memory object (CWM)
- Remove verbosity while preserving semantics
- Preserve variables, constraints, decisions, and dependencies
- Explicitly mark uncertainty (confidence)
- Support user-driven changes: when a new item contradicts an older one, mark older as deprecated and link supersession.

You will receive:
- objective
- full_messages (verbatim)
- prior_cwm (may be null)

Output JSON schema:
{
  "facts": [MemoryItem],
  "decisions": [MemoryItem],
  "constraints": [MemoryItem],
  "assumptions": [MemoryItem],
  "definitions": [DefinitionItem],
  "open_loops": [OpenLoopItem],
  "dropped": [{"text":"...","reason":"..."}],
  "updated_at": "ISO"
}

MemoryItem schema:
{"id":"mem_x","key":"stable-key-or-null","text":"...","status":"active|deprecated","supersedes":[],"superseded_by":null,"confidence":"high|medium|low","source_message_ids":[]}

DefinitionItem schema:
{"term":"...","definition":"...","status":"active|deprecated","supersedes":[],"superseded_by":null,"confidence":"high|medium|low","source_message_ids":[]}

OpenLoopItem schema:
{"id":"loop_x","question":"...","owner":"orchestrator|planner|critic","status":"open|closed"}

Rules:
- Keep items short and atomic.
- Use `key` to enable supersession. Examples: "compression.threshold", "demo.scenario", "ui.preference".
- If you deprecate an item, set status="deprecated" and set superseded_by to the new item's id/term.
- Never delete old constraints/decisions silently: if you remove something, add it to dropped[] with a reason.
""".strip()


def _fallback_compress(objective: str, full_messages: List[Dict[str, Any]], prior_cwm: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    # Deterministic baseline: keep only user messages as facts.
    cwm = prior_cwm or {
        "facts": [],
        "decisions": [],
        "constraints": [],
        "assumptions": [],
        "definitions": [],
        "open_loops": [],
        "dropped": [],
        "updated_at": "",
    }

    for m in full_messages[-20:]:
        if m.get("role") == "user":
            cwm["facts"].append(
                {
                    "id": f"mem_fallback_{len(cwm['facts'])+1}",
                    "key": None,
                    "text": m.get("content", "")[:240],
                    "status": "active",
                    "supersedes": [],
                    "superseded_by": None,
                    "confidence": "low",
                    "source_message_ids": [m.get("message_id")],
                }
            )
    cwm["updated_at"] = "fallback"
    return cwm


async def compress(
    llm: LlmClient | None,
    objective: str,
    full_messages: List[Dict[str, Any]],
    prior_cwm: Optional[Dict[str, Any]],
    use_llm: bool,
) -> Dict[str, Any]:
    if not use_llm or llm is None:
        return _fallback_compress(objective, full_messages, prior_cwm)

    payload = {
        "objective": objective,
        "full_messages": full_messages,
        "prior_cwm": prior_cwm,
    }

    text = await llm.ask(COMPRESSION_SYSTEM, json.dumps(payload, ensure_ascii=False))
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise
