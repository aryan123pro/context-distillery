from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from .llm_client import LlmClient, LlmSettings
from .token_utils import estimate_tokens
from .compression_agent import compress
from .retrieval_agent import retrieve_minimal, assemble_injected_context
from .worker_agents import run_planner, run_critic
from . import storage
from memory_store import load_cwm_runtime, save_cwm_from_runtime


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def msg_doc(run_id: str, role: str, content: str, step_index: int) -> Dict[str, Any]:
    return {
        "message_id": new_id("msg"),
        "run_id": run_id,
        "role": role,
        "content": content,
        "step_index": step_index,
        "ts": now_iso(),
    }


def event_doc(run_id: str, step_index: int, type_: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": new_id("evt"),
        "run_id": run_id,
        "step_index": step_index,
        "ts": now_iso(),
        "type": type_,
        "payload": payload,
    }


def should_compress(
    config: Dict[str, Any],
    step_index: int,
    baseline_tokens: int,
) -> bool:
    if baseline_tokens >= int(config.get("compression_token_threshold", 2400)):
        return True
    interval = int(config.get("compression_interval_steps", 4))
    if interval > 0 and step_index > 0 and step_index % interval == 0:
        return True
    return False


async def step(db: AsyncIOMotorDatabase, run_id: str, user_message: str) -> Dict[str, Any]:
    run = await storage.get_run(db, run_id)
    if not run:
        raise ValueError("run not found")

    config = run.get("config", {})
    use_llm = bool(config.get("use_llm", True))

    step_index = int(run.get("step_index", 0)) + 1

    # Store user message
    user_doc = msg_doc(run_id, "user", user_message, step_index)
    await storage.append_message(db, run_id, user_doc)

    # Load memories
    full_messages = await storage.list_messages(db, run_id, limit=500)
    stm_tail = await storage.list_stm_tail(db, run_id, limit=int(config.get("stm_max_messages", 12)))
    cwm = await storage.get_latest_cwm(db, run_id)
    ltm = await storage.get_latest_ltm(db, run_id)

    # Baseline: full transcript injected (approx), including objective.
    baseline_blob = run.get("objective", "") + "\n" + "\n".join(
        [m.get("role", "") + ":" + m.get("content", "") for m in full_messages]
    )
    baseline_tokens = estimate_tokens(baseline_blob)

    llm: Optional[LlmClient] = None
    if use_llm:
        llm = LlmClient(
            LlmSettings(provider=config.get("llm_provider", "openai"), model=config.get("llm_model", "gpt-5.2")),
            session_id=f"run:{run_id}:step:{step_index}",
        )

    # Retrieval + injection
    retrieval = await retrieve_minimal(
        llm=llm,
        objective=run.get("objective", ""),
        user_message=user_message,
        stm_tail=stm_tail,
        cwm=cwm,
        ltm=ltm,
        use_llm=use_llm,
    )
    injected_context = assemble_injected_context(retrieval, cwm=cwm, ltm=ltm)

    # Compressed prompt approximation: objective + injected memory + STM tail + latest user message.
    injected_blob = "\n".join([m.get("content", "") for m in injected_context])
    stm_blob = "\n".join([m.get("role", "") + ":" + m.get("content", "") for m in stm_tail])
    compressed_blob = run.get("objective", "") + "\n" + injected_blob + "\n" + stm_blob + "\nuser:" + user_message
    injected_tokens = estimate_tokens(compressed_blob)

    await storage.insert_event(db, event_doc(run_id, step_index, "retrieval", {"retrieval": retrieval, "injected_tokens": injected_tokens}))

    # Worker: planner + critic
    planner_out: Dict[str, Any] = {
        "assistant_message": "(LLM disabled)",
        "artifacts": {"plan_steps": [], "proposed_changes": [], "open_questions": []},
    }
    critic_out: Dict[str, Any] = {
        "verdict": "warn",
        "issues": [{"severity": "low", "text": "LLM disabled; critic limited."}],
        "missing_memory": [],
        "suggested_fixes": [],
    }

    if use_llm and llm is not None:
        planner_out = await run_planner(
            llm=llm,
            objective=run.get("objective", ""),
            injected_context=injected_context,
            stm_tail=stm_tail,
            latest_user_message=user_message,
        )
        await storage.insert_event(db, event_doc(run_id, step_index, "planner", planner_out))

        critic_out = await run_critic(
            llm=llm,
            objective=run.get("objective", ""),
            injected_context=injected_context,
            stm_tail=stm_tail,
            latest_user_message=user_message,
            planner_output=planner_out,
        )
        await storage.insert_event(db, event_doc(run_id, step_index, "critic", critic_out))

    assistant_message = planner_out.get("assistant_message", "")
    assistant_doc = msg_doc(run_id, "assistant", assistant_message, step_index)
    await storage.append_message(db, run_id, assistant_doc)

    # Decide compression
    triggered = should_compress(config, step_index, baseline_tokens)

    new_cwm = None
    snapshot_path = None
    if triggered:
        new_cwm = await compress(
            llm=llm,
            objective=run.get("objective", ""),
            full_messages=full_messages,
            prior_cwm=cwm,
            use_llm=use_llm,
        )
        # Persist ONLY strict CWM schema to disk after compression completes
        save_cwm_from_runtime(new_cwm)
        await storage.insert_event(db, event_doc(run_id, step_index, "compression", {"cwm": new_cwm}))

        snapshot = {
            "run_id": run_id,
            "step_index": step_index,
            "objective": run.get("objective", ""),
            "cwm": new_cwm,
            "retrieval": retrieval,
            "ts": now_iso(),
        }
        snapshot_path = storage.write_snapshot(run_id, snapshot)
        await storage.insert_event(db, event_doc(run_id, step_index, "snapshot", {"path": snapshot_path}))

    reduction_pct = 0.0
    if baseline_tokens > 0:
        reduction_pct = max(0.0, float(baseline_tokens - injected_tokens) / float(baseline_tokens)) * 100.0

    metrics = {
        "baseline_tokens": baseline_tokens,
        "injected_tokens": injected_tokens,
        "reduction_pct": reduction_pct,
        "last_snapshot_path": snapshot_path,
        "critic_verdict": critic_out.get("verdict"),
    }

    await storage.set_metrics(db, run_id, metrics)
    await storage.update_run(db, run_id, {"updated_at": now_iso(), "step_index": step_index})

    return {
        "run_id": run_id,
        "step_index": step_index,
        "user_message_id": user_doc["message_id"],
        "assistant_message": assistant_message,
        "triggered_compression": triggered,
        "metrics": metrics,
    }


async def force_compress(db: AsyncIOMotorDatabase, run_id: str) -> Dict[str, Any]:
    run = await storage.get_run(db, run_id)
    if not run:
        raise ValueError("run not found")

    config = run.get("config", {})
    use_llm = bool(config.get("use_llm", True))

    step_index = int(run.get("step_index", 0))
    full_messages = await storage.list_messages(db, run_id, limit=500)
    cwm = await storage.get_latest_cwm(db, run_id)

    llm: Optional[LlmClient] = None
    if use_llm:
        llm = LlmClient(
            LlmSettings(provider=config.get("llm_provider", "openai"), model=config.get("llm_model", "gpt-5.2")),
            session_id=f"run:{run_id}:compress:{step_index}",
        )

    new_cwm = await compress(llm=llm, objective=run.get("objective", ""), full_messages=full_messages, prior_cwm=cwm, use_llm=use_llm)
    # Persist ONLY strict CWM schema to disk after compression completes
    save_cwm_from_runtime(new_cwm)
    await storage.insert_event(db, event_doc(run_id, step_index, "compression", {"cwm": new_cwm, "forced": True}))

    snapshot = {
        "run_id": run_id,
        "step_index": step_index,
        "objective": run.get("objective", ""),
        "cwm": new_cwm,
        "ts": now_iso(),
        "forced": True,
    }
    snapshot_path = storage.write_snapshot(run_id, snapshot)
    await storage.insert_event(db, event_doc(run_id, step_index, "snapshot", {"path": snapshot_path}))

    return {"run_id": run_id, "step_index": step_index, "cwm": new_cwm, "snapshot_path": snapshot_path}
