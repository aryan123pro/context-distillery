from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage


@dataclass
class LlmSettings:
    provider: str = "openai"
    model: str = "gpt-5.2"


class LlmClient:
    def __init__(self, settings: LlmSettings, session_id: str):
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise RuntimeError("EMERGENT_LLM_KEY is missing in backend/.env")

        self.chat = (
            LlmChat(
                api_key=api_key,
                session_id=session_id,
                system_message="You are a careful infrastructure agent. Output strictly valid JSON when requested.",
            )
            .with_model(settings.provider, settings.model)
        )

    async def ask(self, system_message: str, user_text: str) -> str:
        # emergentintegrations takes a system message at init; but we can steer with a
        # prefixed instruction in the user text for MVP.
        prompt = f"SYSTEM OVERRIDE:\n{system_message}\n\nUSER:\n{user_text}"
        resp = await self.chat.send_message(UserMessage(text=prompt))
        # resp is text
        return str(resp)
