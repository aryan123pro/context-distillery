from __future__ import annotations

from typing import Any, Dict, List

from motor.motor_asyncio import AsyncIOMotorDatabase

from . import storage
from .orchestrator import step


DEMO_A_MESSAGES = [
    "We need a product requirements doc for a context compression engine MVP.",
    "Define the API endpoints and what each returns.",
    "Now design the memory schema with three tiers and supersession support.",
    "Add compression triggers and a rehydration priority order.",
    "Add evaluation metrics, especially token reduction and loss analysis.",
    "Change request: make sure the system can overwrite older decisions when the user changes constraints mid-stream.",
    "Finally, produce local run instructions and a deterministic log format.",
]

DEMO_C_MESSAGES = [
    "We are building a multi-agent context compression engine. Summarize the core objective in one sentence.",
    "Add a constraint: compression must be inspectable and deterministic.",
    "Add a constraint: token usage reduction must be at least 50%.",
    "Change request: the UI is minimal web only; no CLI.",
    "Now propose how memory tiers interact and what gets injected first.",
    "Change request: Actually, allow both minimal web UI and CLI in the future; but MVP ships web only.",
    "Create a step-by-step implementation plan (backend + frontend) and list risks.",
]


async def run_demo(db: AsyncIOMotorDatabase, run_id: str, scenario: str) -> Dict[str, Any]:
    msgs: List[str] = DEMO_C_MESSAGES if scenario == "C" else DEMO_A_MESSAGES
    outputs = []
    for m in msgs:
        out = await step(db, run_id, m)
        outputs.append(out)
    return {"run_id": run_id, "scenario": scenario, "steps": outputs, "count": len(outputs)}
