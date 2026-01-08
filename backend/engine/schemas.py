from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional
from datetime import datetime, timezone
import uuid


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


Confidence = Literal["high", "medium", "low"]
ItemStatus = Literal["active", "deprecated"]
OpenLoopStatus = Literal["open", "closed"]


class MemoryItem(BaseModel):
    id: str = Field(default_factory=lambda: new_id("mem"))
    key: Optional[str] = None
    text: str
    status: ItemStatus = "active"

    # Supersession links
    supersedes: List[str] = Field(default_factory=list)
    superseded_by: Optional[str] = None

    confidence: Confidence = "medium"
    source_message_ids: List[str] = Field(default_factory=list)


class DefinitionItem(BaseModel):
    term: str
    definition: str
    status: ItemStatus = "active"
    supersedes: List[str] = Field(default_factory=list)
    superseded_by: Optional[str] = None
    confidence: Confidence = "medium"
    source_message_ids: List[str] = Field(default_factory=list)


class OpenLoopItem(BaseModel):
    id: str = Field(default_factory=lambda: new_id("loop"))
    question: str
    owner: Literal["orchestrator", "planner", "critic"] = "orchestrator"
    status: OpenLoopStatus = "open"


class CompressedWorkingMemory(BaseModel):
    facts: List[MemoryItem] = Field(default_factory=list)
    decisions: List[MemoryItem] = Field(default_factory=list)
    constraints: List[MemoryItem] = Field(default_factory=list)
    assumptions: List[MemoryItem] = Field(default_factory=list)
    definitions: List[DefinitionItem] = Field(default_factory=list)
    open_loops: List[OpenLoopItem] = Field(default_factory=list)

    dropped: List[Dict[str, Any]] = Field(default_factory=list)
    updated_at: str = Field(default_factory=now_iso)


class LongTermMemory(BaseModel):
    facts: List[MemoryItem] = Field(default_factory=list)
    definitions: List[DefinitionItem] = Field(default_factory=list)
    updated_at: str = Field(default_factory=now_iso)


class RunConfig(BaseModel):
    # Compression settings
    stm_max_messages: int = 12
    compression_token_threshold: int = 2400
    compression_interval_steps: int = 4

    # Determinism
    use_llm: bool = True

    # LLM model
    llm_provider: Literal["openai"] = "openai"
    llm_model: str = "gpt-5.2"


class RunCreateRequest(BaseModel):
    objective: str
    scenario: Literal["A", "C"] = "C"
    config: Optional[RunConfig] = None


class StepRequest(BaseModel):
    user_message: str


class StepResponse(BaseModel):
    run_id: str
    step_index: int
    user_message_id: str

    assistant_message: str

    metrics: Dict[str, Any]
    triggered_compression: bool


class RunResponse(BaseModel):
    run_id: str
    objective: str
    created_at: str
    updated_at: str
    step_index: int
    config: RunConfig


class MemoryResponse(BaseModel):
    run_id: str
    stm: List[Dict[str, Any]]
    cwm: Optional[Dict[str, Any]]
    ltm: Optional[Dict[str, Any]]
    metrics: Dict[str, Any]


class EventResponse(BaseModel):
    id: str
    run_id: str
    step_index: int
    ts: str
    type: str
    payload: Dict[str, Any]
