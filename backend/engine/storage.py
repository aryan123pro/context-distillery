from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()



def sanitize_for_json(obj: Any) -> Any:
    # Recursively convert MongoDB ObjectId to str (and handle nested payloads).
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items() if k != "_id"}
    if isinstance(obj, list):
        return [sanitize_for_json(x) for x in obj]
    return obj


def _snap_dir(run_id: str) -> Path:
    base = Path(__file__).resolve().parent.parent / "snapshots" / run_id
    base.mkdir(parents=True, exist_ok=True)
    return base


async def create_run(db: AsyncIOMotorDatabase, run_doc: Dict[str, Any]) -> None:
    # MongoDB insert mutates dict by adding _id; avoid leaking ObjectId into other payloads.
    await db.runs.insert_one(copy.deepcopy(run_doc))


async def get_run(db: AsyncIOMotorDatabase, run_id: str) -> Optional[Dict[str, Any]]:
    return await db.runs.find_one({"run_id": run_id}, {"_id": 0})


async def update_run(db: AsyncIOMotorDatabase, run_id: str, patch: Dict[str, Any]) -> None:
    await db.runs.update_one({"run_id": run_id}, {"$set": patch})


async def append_message(db: AsyncIOMotorDatabase, run_id: str, message: Dict[str, Any]) -> None:
    await db.messages.insert_one(copy.deepcopy(message))


async def list_messages(db: AsyncIOMotorDatabase, run_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    return await (
        db.messages.find({"run_id": run_id}, {"_id": 0}).sort("ts", 1).to_list(limit)
    )


async def list_stm_tail(db: AsyncIOMotorDatabase, run_id: str, limit: int) -> List[Dict[str, Any]]:
    msgs = await (
        db.messages.find({"run_id": run_id}, {"_id": 0}).sort("ts", -1).to_list(limit)
    )
    return list(reversed(msgs))


async def insert_event(db: AsyncIOMotorDatabase, event: Dict[str, Any]) -> None:
    await db.events.insert_one(copy.deepcopy(event))


async def list_events(db: AsyncIOMotorDatabase, run_id: str, limit: int = 500) -> List[Dict[str, Any]]:
    docs = await (
        db.events.find({"run_id": run_id}, {"_id": 0}).sort("ts", 1).to_list(limit)
    )
    return sanitize_for_json(docs)


async def set_latest_cwm(db: AsyncIOMotorDatabase, run_id: str, cwm: Dict[str, Any]) -> None:
    await db.cwm.update_one(
        {"run_id": run_id},
        {"$set": {"run_id": run_id, "cwm": cwm, "updated_at": now_iso()}},
        upsert=True,
    )


async def get_latest_cwm(db: AsyncIOMotorDatabase, run_id: str) -> Optional[Dict[str, Any]]:
    doc = await db.cwm.find_one({"run_id": run_id}, {"_id": 0})
    return doc.get("cwm") if doc else None


async def set_latest_ltm(db: AsyncIOMotorDatabase, run_id: str, ltm: Dict[str, Any]) -> None:
    await db.ltm.update_one(
        {"run_id": run_id},
        {"$set": {"run_id": run_id, "ltm": ltm, "updated_at": now_iso()}},
        upsert=True,
    )


async def get_latest_ltm(db: AsyncIOMotorDatabase, run_id: str) -> Optional[Dict[str, Any]]:
    doc = await db.ltm.find_one({"run_id": run_id}, {"_id": 0})
    return doc.get("ltm") if doc else None


async def set_metrics(db: AsyncIOMotorDatabase, run_id: str, metrics: Dict[str, Any]) -> None:
    await db.metrics.update_one(
        {"run_id": run_id},
        {"$set": {"run_id": run_id, "metrics": metrics, "updated_at": now_iso()}},
        upsert=True,
    )


async def get_metrics(db: AsyncIOMotorDatabase, run_id: str) -> Dict[str, Any]:
    doc = await db.metrics.find_one({"run_id": run_id}, {"_id": 0})
    return doc.get("metrics") if doc else {}


def write_snapshot(run_id: str, snapshot: Dict[str, Any]) -> str:
    out_dir = _snap_dir(run_id)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"{ts}.json"
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    return str(path)


def read_latest_snapshot(run_id: str) -> Optional[Dict[str, Any]]:
    out_dir = _snap_dir(run_id)
    files = sorted([p for p in out_dir.glob("*.json")])
    if not files:
        return None
    return json.loads(files[-1].read_text())
