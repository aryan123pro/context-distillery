from __future__ import annotations

import copy
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

from engine import storage
from engine.demo import run_demo
from engine.orchestrator import force_compress, step
from engine.schemas import MemoryResponse, RunCreateRequest, RunResponse, StepRequest, StepResponse


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# MongoDB connection
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI()
api_router = APIRouter(prefix="/api")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:12]}"


@api_router.get("/")
async def root():
    return {"message": "Context Distillery API"}


@api_router.post("/runs", response_model=RunResponse)
async def create_run(req: RunCreateRequest):
    run_id = new_run_id()
    config = (req.config.model_dump() if req.config else {})

    run_doc = {
        "run_id": run_id,
        "objective": req.objective,
        "scenario": req.scenario,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "step_index": 0,
        "config": {
            "stm_max_messages": config.get("stm_max_messages", 12),
            "compression_token_threshold": config.get("compression_token_threshold", 2400),
            "compression_interval_steps": config.get("compression_interval_steps", 4),
            "use_llm": config.get("use_llm", True),
            "llm_provider": config.get("llm_provider", "openai"),
            "llm_model": config.get("llm_model", "gpt-5.2"),
        },
    }

    # IMPORTANT: Mongo may add an ObjectId _id field to the inserted dict in-place.
    # We snapshot a deep copy for event payload to keep the event JSON-serializable.
    run_doc_for_event = copy.deepcopy(run_doc)

    await storage.create_run(db, run_doc)
    await storage.insert_event(
        db,
        {
            "id": f"evt_{uuid.uuid4().hex[:12]}",
            "run_id": run_id,
            "step_index": 0,
            "ts": now_iso(),
            "type": "run_created",
            "payload": {"run": run_doc_for_event},
        },
    )

    return {
        "run_id": run_id,
        "objective": req.objective,
        "created_at": run_doc["created_at"],
        "updated_at": run_doc["updated_at"],
        "step_index": 0,
        "config": run_doc["config"],
    }


@api_router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run_route(run_id: str):
    run = await storage.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    cfg = run.get("config", {})
    return {
        "run_id": run["run_id"],
        "objective": run.get("objective", ""),
        "created_at": run.get("created_at"),
        "updated_at": run.get("updated_at"),
        "step_index": run.get("step_index", 0),
        "config": cfg,
    }


@api_router.post("/runs/{run_id}/step", response_model=StepResponse)
async def run_step(run_id: str, req: StepRequest):
    try:
        out = await step(db, run_id, req.user_message)
        return out
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"step failed: {e}")


@api_router.post("/runs/{run_id}/compress")
async def compress_run(run_id: str):
    try:
        return await force_compress(db, run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"compression failed: {e}")


@api_router.get("/runs/{run_id}/memory", response_model=MemoryResponse)
async def get_memory(run_id: str):
    run = await storage.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    cfg = run.get("config", {})
    stm = await storage.list_stm_tail(db, run_id, limit=int(cfg.get("stm_max_messages", 12)))
    cwm = await storage.get_latest_cwm(db, run_id)
    ltm = await storage.get_latest_ltm(db, run_id)
    metrics = await storage.get_metrics(db, run_id)

    return {"run_id": run_id, "stm": stm, "cwm": cwm, "ltm": ltm, "metrics": metrics}


@api_router.get("/runs/{run_id}/events")
async def get_events(run_id: str):
    run = await storage.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    events = await storage.list_events(db, run_id, limit=800)
    return {"run_id": run_id, "events": events}


@api_router.get("/runs/{run_id}/snapshots/latest")
async def get_latest_snapshot(run_id: str):
    snap = storage.read_latest_snapshot(run_id)
    if not snap:
        raise HTTPException(status_code=404, detail="no snapshot")
    return snap


@api_router.post("/demo/run")
async def demo_run(req: RunCreateRequest):
    run_id = new_run_id()
    config = (req.config.model_dump() if req.config else {})

    run_doc = {
        "run_id": run_id,
        "objective": req.objective,
        "scenario": req.scenario,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "step_index": 0,
        "config": {
            "stm_max_messages": config.get("stm_max_messages", 12),
            "compression_token_threshold": config.get("compression_token_threshold", 1800),
            "compression_interval_steps": config.get("compression_interval_steps", 2),
            "use_llm": config.get("use_llm", True),
            "llm_provider": config.get("llm_provider", "openai"),
            "llm_model": config.get("llm_model", "gpt-5.2"),
        },
    }

    await storage.create_run(db, run_doc)
    result = await run_demo(db, run_id, req.scenario)
    return result


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()