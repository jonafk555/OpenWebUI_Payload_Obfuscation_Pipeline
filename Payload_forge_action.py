"""
title: Payload Forge Confirm Action
author: redteam-research
version: 0.1.0
required_open_webui_version: 0.3.9
description: |
  Companion Action button for payload_forge pipe.
  Use case: pipe first replies with PARSED SPEC ONLY (no artifact).
  User reviews the spec, then clicks this Action to send a confirmation
  message back into the chat that re-triggers the pipe with confirmed=true.
  This implements the human-in-the-loop "approve before generate" pattern.
"""

import json
import re
from typing import Awaitable, Callable, Optional

from pydantic import BaseModel, Field


class Action:
    class Valves(BaseModel):
        ENABLED: bool = Field(default=True, description="Master switch.")
        BUTTON_LABEL: str = Field(
            default="✅ Confirm & Generate",
            description="Label shown on the action button.",
        )
        REQUIRE_TYPED_PHRASE: str = Field(
            default="",
            description=(
                "If non-empty, the user must type this exact phrase as a "
                "follow-up message to confirm. Adds friction for high-risk "
                "engagements (e.g. 'AUTHORIZED:ENG-2026-001')."
            ),
        )

    def __init__(self) -> None:
        self.valves = self.Valves()

    @staticmethod
    async def _emit(emitter, level: str, msg: str, done: bool = False) -> None:
        if emitter is None:
            return
        await emitter({
            "type": "status",
            "data": {"description": msg, "done": done, "level": level},
        })

    async def action(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
        __event_call__: Optional[Callable[[dict], Awaitable[dict]]] = None,
    ) -> Optional[dict]:
        if not self.valves.ENABLED:
            return None

        await self._emit(__event_emitter__, "info", "Confirm action invoked")

        # Locate the most recent assistant message — should contain a spec
        # JSON block emitted by the pipe in DRY_RUN / awaiting-confirmation mode.
        messages = body.get("messages", [])
        spec_block = None
        target_msg_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") != "assistant":
                continue
            content = messages[i].get("content", "")
            if not isinstance(content, str):
                continue
            m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.S)
            if m:
                try:
                    spec_block = json.loads(m.group(1))
                    target_msg_idx = i
                    break
                except json.JSONDecodeError:
                    continue

        if spec_block is None:
            await self._emit(
                __event_emitter__, "error",
                "No parseable spec found in recent assistant messages.",
                done=True,
            )
            return None

        # Optional friction: require typed confirmation phrase via event_call.
        # __event_call__ opens a modal/input on the frontend and awaits reply.
        if self.valves.REQUIRE_TYPED_PHRASE and __event_call__ is not None:
            reply = await __event_call__({
                "type": "input",
                "data": {
                    "title": "Confirm payload generation",
                    "message": (
                        "Type the engagement authorization phrase to proceed. "
                        "This will be recorded in the audit log."
                    ),
                    "placeholder": self.valves.REQUIRE_TYPED_PHRASE,
                },
            })
            typed = (reply or {}).get("value", "").strip()
            if typed != self.valves.REQUIRE_TYPED_PHRASE:
                await self._emit(
                    __event_emitter__, "error",
                    "Authorization phrase did not match. Aborted.",
                    done=True,
                )
                return None

        # Inject a NEW user message that re-invokes the pipe with confirmed=true.
        # The pipe's parse_spec() will pick up `confirmed: true` as a key:value
        # line and skip the dry-run gate.
        confirmed_payload = {**(spec_block.get("spec") or spec_block), "confirmed": True}
        new_user_text = (
            "Re-issuing previously parsed spec with confirmation.\n\n"
            "```json\n" + json.dumps(confirmed_payload, indent=2) + "\n```\n"
            "confirmed: true"
        )
        messages.append({"role": "user", "content": new_user_text})
        body["messages"] = messages

        await self._emit(
            __event_emitter__, "info",
            f"Spec confirmed by {(__user__ or {}).get('email', 'anonymous')}. "
            "Pipe will re-run with confirmed=true.",
            done=True,
        )
        return body
