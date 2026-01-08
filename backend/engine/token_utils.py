from __future__ import annotations

import math


def estimate_tokens(text: str) -> int:
    # Deterministic approximation; stable across environments.
    if not text:
        return 0
    return int(math.ceil(len(text) / 4))


def estimate_tokens_for_messages(messages: list[dict]) -> int:
    # messages: [{role, content}]
    total = 0
    for m in messages:
        total += estimate_tokens(m.get("content", ""))
    return total
