from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .llm_client import LlmClient


PLANNER_SYSTEM = """
You are the Worker Planner Agent.

You are part of a multi-agent context compression engine. The user is building an MVP.

You will be given:
- objective
- injected_context (structured constraints/definitions/decisions/facts)
- stm_tail (recent verbatim messages)
- latest_user_message

Output STRICT JSON:
{
  "assistant_message": "final response to the user (helpful, specific)",
  "artifacts": {
     "plan_steps": ["..."],
     "proposed_changes": ["..."],
     "open_questions": ["..."]
  }
}

Rules:
- If the user changes their mind, respect the newest instruction and explicitly call out what was superseded.
- Keep the response concise but production-minded.
""".strip()


CRITIC_SYSTEM = """
You are the Worker Critic/Verifier Agent.

You will be given the planner output plus the same context.

Output STRICT JSON:
{
  "verdict": "pass|warn|fail",
  "issues": [{"severity":"high|medium|low","text":"..."}],
  "missing_memory": ["what should be stored as constraint/decision/definition"],
  "suggested_fixes": ["..."]
}

Rules:
- Prefer correctness and invariants.
- Flag potential loss of constraints.
""".strip()


async def run_planner(
    llm: LlmClient,
    objective: str,
    injected_context: List[Dict[str, Any]],
    stm_tail: List[Dict[str, Any]],
    latest_user_message: str,
) -> Dict[str, Any]:
    payload = {
        "objective": objective,
        "injected_context": injected_context,
        "stm_tail": stm_tail,
        "latest_user_message": latest_user_message,
    }
    text = await llm.ask(PLANNER_SYSTEM, json.dumps(payload, ensure_ascii=False))
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        return json.loads(text[start : end + 1])


async def run_critic(
    llm: LlmClient,
    objective: str,
    injected_context: List[Dict[str, Any]],
    stm_tail: List[Dict[str, Any]],
    latest_user_message: str,
    planner_output: Dict[str, Any],
) -> Dict[str, Any]:
    payload = {
        "objective": objective,
        "injected_context": injected_context,
        "stm_tail": stm_tail,
        "latest_user_message": latest_user_message,
        "planner_output": planner_output,
    }
    text = await llm.ask(CRITIC_SYSTEM, json.dumps(payload, ensure_ascii=False))
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        return json.loads(text[start : end + 1])
