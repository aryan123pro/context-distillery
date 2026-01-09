# Context Distillery — Multi‑Agent Context Compression Engine (MVP)

This project is a minimal, inspectable “context compression layer” that simulates a larger context window by:
- keeping **STM** (verbatim recent messages)
- generating **CWM** (structured compressed working memory)
- optionally maintaining **LTM** (stable memory; MVP scaffolding)
- rehydrating only minimal relevant memory before each agent runs
- logging every agent action + measuring token reduction (approx)

> Not a chatbot UI wrapper: this is an engine + logs + memory tiers.

---

## What’s implemented (MVP)

### Agents
- **Orchestrator (controller)**: schedules retrieval → planner → critic → optional compression
- **Retrieval Agent**: selects minimal relevant memory to inject
- **Worker Planner**: produces the user-facing answer + artifacts
- **Worker Critic**: checks consistency and flags missing memory
- **Compression Agent**: writes structured CWM and supports **supersession** (deprecated/superseded links)

### Memory tiers
- **STM**: MongoDB `messages` collection (verbatim), windowed
- **CWM**: MongoDB `cwm` collection (latest structured memory) + JSON snapshots on disk
- **LTM**: MongoDB `ltm` collection (MVP scaffold)

### Determinism
- **LLM on** (best-effort deterministic): temperature=0 (prompted), strict JSON outputs, full event logs
- **Strict deterministic mode** (LLM off): rule-based retrieval/compression fallback (lower quality, fully reproducible)

### Evaluation metrics (mandatory)
- `baseline_tokens`: estimated tokens of objective + full transcript
- `injected_tokens`: estimated tokens of objective + retrieved memory + STM tail + latest user message
- `reduction_pct`: percent reduction
- loss visibility: compression includes a `dropped[]` list with reasons

---

## Run locally

### Backend
- Backend runs on `0.0.0.0:8001` under supervisor.
- MongoDB connection uses `backend/.env` (`MONGO_URL`, `DB_NAME`).

Restart backend:
```bash
sudo supervisorctl restart backend
```

### Frontend
- Frontend uses `frontend/.env` `REACT_APP_BACKEND_URL`.

Restart frontend:
```bash
sudo supervisorctl restart frontend
```

---

## Web UI
Open the app:
- https://context-distillery.preview.emergentagent.com/

What to do:
1. Click **Create run**
2. Type a message and click **Send**
3. Watch the **Event timeline** populate
4. Check **CWM** in Memory viewer
5. Try a change mid-run (supersession):
   - “Change request: compression threshold is now 1200”
   - then force compress

---

## API (all prefixed with `/api`)

- `GET /api/` — health
- `POST /api/runs` — create a run
- `GET /api/runs/{run_id}` — run metadata
- `POST /api/runs/{run_id}/step` — submit a user message, execute one orchestrated cycle
- `POST /api/runs/{run_id}/compress` — force compression
- `GET /api/runs/{run_id}/memory` — STM tail + latest CWM + metrics
- `GET /api/runs/{run_id}/events` — full event timeline (inspectable)
- `GET /api/runs/{run_id}/snapshots/latest` — latest JSON snapshot
- `POST /api/demo/run` — runs a multi-step scripted demo (scenario A or C)

---

## Demo scenarios (required)
- **Scenario A (spec build-out)**: long PRD/API/schema/metrics session
- **Scenario C (self-demo)**: long design session about the engine itself, including change requests

Use the **Run demo** button in the UI, or call:
```bash
curl -X POST "$REACT_APP_BACKEND_URL/api/demo/run" \
  -H "Content-Type: application/json" \
  -d '{"objective":"Demo objective","scenario":"C"}'
```

---

## Where snapshots live
Each compression writes a JSON snapshot:
- `backend/snapshots/{run_id}/{timestamp}.json`

---

## Key files
- `backend/server.py` — FastAPI routes
- `backend/engine/orchestrator.py` — orchestration loop + triggers + metrics
- `backend/engine/compression_agent.py` — structured CWM generation
- `backend/engine/retrieval_agent.py` — minimal memory selection
- `frontend/src/components/EngineConsole.jsx` — minimal console UI
- `plan.md` — architecture + APIs + schema plan
