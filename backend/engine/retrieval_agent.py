from __future__ import annotations

import json
from typing import Any, Dict, List

from .llm_client import LlmClient


RETRIEVAL_SYSTEM = """
You are the Retrieval Agent in a multi-agent context compression engine.

Goal: select the MINIMAL subset of memory needed for the next step.

You will receive:
- objective
- latest user message
- stm_tail (recent verbatim messages)
- cwm (structured working memory)
- ltm (long-term memory)

Output STRICT JSON with this schema:
{
  "constraints_ids": ["..."],
  "definitions_terms": ["..."],
  "decisions_ids": ["..."],
  "facts_ids": ["..."],
  "assumptions_ids": ["..."],
  "open_loop_ids": ["..."],
  "notes": "short reason"
}

Selection rules:
- Prefer ACTIVE items. Avoid deprecated unless needed for conflict resolution.
- Prioritize constraints and definitions.
- Keep list sizes small (typically 3-8 total items).
""".strip()


def _fallback_retrieve(objective: str, user_message: str, cwm: Dict[str, Any] | None) -> Dict[str, Any]:
    # Simple deterministic keyword match. Not great, but reproducible.
    user_lower = (objective + "\n" + user_message).lower()
    out = {
        "constraints_ids": [],
        "definitions_terms": [],
        "decisions_ids": [],
        "facts_ids": [],
        "assumptions_ids": [],
        "open_loop_ids": [],
        "notes": "fallback keyword retrieval",
    }
    if not cwm:
        return out

    def maybe_pick(section: str, out_key: str, id_key: str = "id"):
        items = cwm.get(section, [])
        for it in items:
            if it.get("status") == "deprecated":
                continue
            text = (it.get("text") or it.get("definition") or "").lower()
            if not text:
                continue
            if any(tok in text for tok in user_lower.split()[:20]):
                if out_key == "definitions_terms":
                    out[out_key].append(it.get("term"))
                else:
                    out[out_key].append(it.get(id_key))
                if sum(len(v) for k, v in out.items() if k.endswith("ids") or k.endswith("terms")) >= 8:
                    return

    maybe_pick("constraints", "constraints_ids")
    maybe_pick("definitions", "definitions_terms", id_key="term")
    maybe_pick("decisions", "decisions_ids")
    maybe_pick("facts", "facts_ids")
    maybe_pick("assumptions", "assumptions_ids")
    maybe_pick("open_loops", "open_loop_ids")
    return out


async def retrieve_minimal(
    llm: LlmClient | None,
    objective: str,
    user_message: str,
    stm_tail: List[Dict[str, Any]],
    cwm: Dict[str, Any] | None,
    ltm: Dict[str, Any] | None,
    use_llm: bool,
) -> Dict[str, Any]:
    if not use_llm or llm is None:
        return _fallback_retrieve(objective, user_message, cwm)

    payload = {
        "objective": objective,
        "latest_user_message": user_message,
        "stm_tail": stm_tail,
        "cwm": cwm,
        "ltm": ltm,
    }

    text = await llm.ask(RETRIEVAL_SYSTEM, json.dumps(payload, ensure_ascii=False))

    # Be resilient: attempt to extract JSON.
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def assemble_injected_context(
    retrieval: Dict[str, Any],
    cwm: Dict[str, Any] | None,
    ltm: Dict[str, Any] | None,
) -> List[Dict[str, Any]]:
    # Priority order: constraints, definitions, decisions, summaries.
    injected: List[Dict[str, Any]] = []
    if not cwm:
        return injected

    def by_ids(section: str, ids: List[str]) -> List[Dict[str, Any]]:
        items = cwm.get(section, [])
        idx = {it.get("id"): it for it in items if it.get("id")}
        return [idx[i] for i in ids if i in idx]

    def defs_by_terms(terms: List[str]) -> List[Dict[str, Any]]:
        items = cwm.get("definitions", [])
        idx = {it.get("term"): it for it in items if it.get("term")}
        return [idx[t] for t in terms if t in idx]

    constraints = by_ids("constraints", retrieval.get("constraints_ids", []))
    definitions = defs_by_terms(retrieval.get("definitions_terms", []))
    decisions = by_ids("decisions", retrieval.get("decisions_ids", []))
    facts = by_ids("facts", retrieval.get("facts_ids", []))

    # LTM (optional): inject only if requested via terms/ids not found in CWM.
    # MVP keeps it simple.

    if constraints:
        injected.append({"role": "system", "content": "CONSTRAINTS:\n" + json.dumps(constraints, ensure_ascii=False)})
    if definitions:
        injected.append({"role": "system", "content": "DEFINITIONS:\n" + json.dumps(definitions, ensure_ascii=False)})
    if decisions:
        injected.append({"role": "system", "content": "DECISIONS:\n" + json.dumps(decisions, ensure_ascii=False)})
    if facts:
        injected.append({"role": "system", "content": "FACTS:\n" + json.dumps(facts, ensure_ascii=False)})

    return injected
