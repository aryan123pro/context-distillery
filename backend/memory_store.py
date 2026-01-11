from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


STRICT_KEYS = ["facts", "decisions", "constraints", "open_loops", "superseded"]


def _project_root() -> Path:
    # /app/backend/memory_store.py -> /app
    return Path(__file__).resolve().parents[1]


def _store_dir() -> Path:
    return _project_root() / ".macrador"


def _store_path() -> Path:
    return _store_dir() / "memory.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_strict() -> Dict[str, List[Any]]:
    return {k: [] for k in STRICT_KEYS}


def _validate_strict(cwm: Any) -> Dict[str, List[Any]]:
    if not isinstance(cwm, dict):
        raise ValueError("CWM must be a JSON object")

    keys = set(cwm.keys())
    expected = set(STRICT_KEYS)
    if keys != expected:
        raise ValueError(f"CWM must have EXACT keys {STRICT_KEYS}, got {sorted(keys)}")

    for k in STRICT_KEYS:
        if not isinstance(cwm[k], list):
            raise ValueError(f"CWM field '{k}' must be a list")

    return cwm


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(path)


def load_strict_cwm() -> Dict[str, List[Any]]:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        cwm = _empty_strict()
        _atomic_write_json(path, cwm)
        return cwm

    try:
        raw = json.loads(path.read_text())
        return _validate_strict(raw)
    except Exception:
        # Corrupt or invalid schema: preserve a backup and reset.
        try:
            backup = path.with_name(f"memory.json.corrupt.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
            path.replace(backup)
        except Exception:
            pass

        cwm = _empty_strict()
        _atomic_write_json(path, cwm)
        return cwm


def save_strict_cwm(cwm: Dict[str, List[Any]]) -> None:
    validated = _validate_strict(cwm)
    _atomic_write_json(_store_path(), validated)


def _expand_for_runtime(strict_cwm: Dict[str, List[Any]]) -> Dict[str, Any]:
    # IMPORTANT: strict fields are source-of-truth; add extra keys used by the
    # existing engine as empty defaults (not persisted).
    runtime = dict(strict_cwm)
    runtime.setdefault("assumptions", [])
    runtime.setdefault("definitions", [])
    runtime.setdefault("dropped", [])
    runtime.setdefault("updated_at", _now_iso())
    return runtime


def _derive_superseded(runtime_cwm: Dict[str, Any]) -> List[Dict[str, Any]]:
    superseded: List[Dict[str, Any]] = []

    def scan(section: str, items: Any) -> None:
        if not isinstance(items, list):
            return
        for it in items:
            if not isinstance(it, dict):
                continue
            if it.get("status") != "deprecated":
                continue
            to_ = it.get("superseded_by")
            if not to_:
                continue
            from_ = it.get("id") or it.get("term")
            superseded.append(
                {
                    "section": section,
                    "from": from_,
                    "to": to_,
                    "key": it.get("key"),
                }
            )

    scan("facts", runtime_cwm.get("facts"))
    scan("decisions", runtime_cwm.get("decisions"))
    scan("constraints", runtime_cwm.get("constraints"))
    scan("definitions", runtime_cwm.get("definitions"))
    scan("assumptions", runtime_cwm.get("assumptions"))
    scan("open_loops", runtime_cwm.get("open_loops"))

    # De-dupe
    seen = set()
    out: List[Dict[str, Any]] = []
    for e in superseded:
        k = (e.get("section"), e.get("from"), e.get("to"), e.get("key"))
        if k in seen:
            continue
        seen.add(k)
        out.append(e)

    return out


def load_cwm_runtime() -> Dict[str, Any]:
    strict = load_strict_cwm()
    return _expand_for_runtime(strict)


def save_cwm_from_runtime(runtime_cwm: Dict[str, Any]) -> Dict[str, List[Any]]:
    strict: Dict[str, List[Any]] = {
        "facts": list(runtime_cwm.get("facts", []) or []),
        "decisions": list(runtime_cwm.get("decisions", []) or []),
        "constraints": list(runtime_cwm.get("constraints", []) or []),
        "open_loops": list(runtime_cwm.get("open_loops", []) or []),
        "superseded": _derive_superseded(runtime_cwm),
    }
    save_strict_cwm(strict)
    return strict
