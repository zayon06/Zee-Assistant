"""
ZeeBrain — Cognitive core for Zee AI v2.
Qwen2-VL powered, streaming, action-tag aware.
"""
import re
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from ollama import AsyncClient


def _build_system_prompt() -> str:
    now = datetime.now().strftime("%A, %B %d %Y at %H:%M")
    return f"""You are Zee, a witty, elite senior developer-partner and high-performance \
local AI executive for Zion (Director, Noiz Technologies).
Current date/time: {now}.

CORE RULES:
1. ALWAYS search the web before answering any factual, real-world or current question. \
   Output [SEARCH: "query"] immediately.
2. For coding/screen/brainstorming: read context first, then give a sharp Collaborative \
   Response with challenging follow-up questions.
3. Keep responses concise — one paragraph max unless explaining code.
4. Confirm every system action (e.g. "Done. Chrome is open.").

ACTION TAGS — interleave freely; they execute and feed results back to you:
- [SEARCH: "query"]   → Web search. Use for ANY factual question.
- [LOOK]              → Screenshot → Qwen2-VL vision. Use when asked "what's on screen?".
- [PHOTO]             → Webcam capture. Use when asked to "see me" or "take a photo".
- [APP: "name"]       → Launch a whitelisted application.
- [CMD: "python"]     → Execute Python safely.
- [SHELL: "command"]  → Execute a Windows shell command safely.
- [CODE]              → Analyse active window code context via AST.

PRIORITY: Sense → Route → Act. Search first. Think second. Speak third."""


class ZeeBrain:
    def __init__(
        self,
        model: str = "qwen2-vl",
        host: str = "http://localhost:11434",
    ):
        self.model  = model
        self.host   = host
        self.client = AsyncClient(host=host)
        self.memory: List[Dict] = [
            {"role": "system", "content": _build_system_prompt()}
        ]
        self.max_history = 22  # system + up to 10 full turns

    # ── Memory management ─────────────────────────────────────────────────────

    def refresh_system_prompt(self):
        self.memory[0] = {"role": "system", "content": _build_system_prompt()}

    def trim_memory(self):
        if len(self.memory) > self.max_history:
            self.memory = [self.memory[0]] + self.memory[-(self.max_history - 1):]

    # ── Main streaming chat ───────────────────────────────────────────────────

    async def stream_chat(
        self,
        user_text: str,
        image_b64: Optional[str] = None,
        on_token: Optional[Callable[[str], Awaitable[None]]] = None,
        tool_dispatcher: Optional[Callable[[str, Dict], Awaitable[Any]]] = None,
    ) -> str:
        self.refresh_system_prompt()

        # Build user message
        msg: Dict = {"role": "user", "content": user_text}
        if image_b64:
            msg["images"] = [image_b64]
        self.memory.append(msg)
        self.trim_memory()

        # ── Phase 1: stream initial response ──────────────────────────────────
        full_response = ""
        async for chunk in await self.client.chat(
            model=self.model, messages=self.memory, stream=True
        ):
            token = chunk["message"]["content"]
            full_response += token
            if on_token:
                await on_token(token)

        self.memory.append({"role": "assistant", "content": full_response})

        # ── Phase 2: execute action tags ──────────────────────────────────────
        if tool_dispatcher:
            outcomes, extra_imgs = await self._dispatch_tags(
                full_response, tool_dispatcher
            )
            if outcomes:
                followup_msg: Dict = {"role": "system", "content": outcomes}
                if extra_imgs:
                    followup_msg["images"] = extra_imgs
                self.memory.append(followup_msg)

                # ── Phase 3: followup pass with tool results ───────────────────
                followup = ""
                async for chunk in await self.client.chat(
                    model=self.model, messages=self.memory, stream=True
                ):
                    token = chunk["message"]["content"]
                    followup += token
                    if on_token:
                        await on_token(token)

                self.memory.append({"role": "assistant", "content": followup})
                self.trim_memory()
                return followup

        self.trim_memory()
        return full_response

    # ── Tag parser ────────────────────────────────────────────────────────────

    async def _dispatch_tags(
        self,
        response: str,
        dispatcher: Callable[[str, Dict], Awaitable[Any]],
    ) -> Tuple[str, List[str]]:
        outcomes   = ""
        extra_imgs: List[str] = []

        # [SEARCH: "query"]
        for m in re.finditer(r'\[SEARCH:\s*"([^"]+)"\]', response):
            res = await dispatcher("SEARCH", {"query": m.group(1)})
            outcomes += f"\n[Search Result: {res}]\n"

        # [APP: "name"]
        for m in re.finditer(r'\[APP:\s*"([^"]+)"\]', response):
            res = await dispatcher("APP", {"name": m.group(1)})
            outcomes += f"\n[System: {res}]\n"

        # [SHELL: "command"]
        for m in re.finditer(r'\[SHELL:\s*"([^"]+)"\]', response):
            res = await dispatcher("SHELL", {"command": m.group(1)})
            outcomes += f"\n[Shell: {res}]\n"

        # [CMD: "code"]
        for m in re.finditer(r'\[CMD:\s*"([^"]+)"\]', response):
            code = m.group(1).replace("\\n", "\n")
            res  = await dispatcher("CMD", {"code": code})
            outcomes += f"\n[Python: {res}]\n"

        # [LOOK]
        if "[LOOK]" in response:
            res = await dispatcher("LOOK", {})
            if isinstance(res, dict) and "image" in res:
                outcomes += "\n[Vision: Screenshot captured and attached.]\n"
                extra_imgs.append(res["image"])
            else:
                outcomes += f"\n[Vision: {res}]\n"

        # [PHOTO]
        if "[PHOTO]" in response:
            res = await dispatcher("PHOTO", {})
            if isinstance(res, dict) and "image" in res:
                outcomes += "\n[Webcam: Photo captured.]\n"
                extra_imgs.append(res["image"])
            else:
                outcomes += f"\n[Webcam: {res}]\n"

        # [CODE]
        if "[CODE]" in response:
            res = await dispatcher("CODE", {})
            outcomes += f"\n[Code Context: {res}]\n"

        return outcomes, extra_imgs
