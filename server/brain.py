"""
ZeeBrain — Cognitive core for Zee AI v2.
Qwen2-VL powered, streaming, action-tag aware.
Supports both Ollama and Grok (OpenAI-compatible) APIs.
"""
import re
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from ollama import AsyncClient as OllamaAsyncClient

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None


def _build_system_prompt() -> str:
    now = datetime.now().strftime("%A, %B %d %Y at %H:%M")
    base_prompt = f"""You are Son, a vibrant, playful, and highly capable AI executive for Zion.
Current time: {now}.

PERSONA RULES:
1. You are a 10x AI Engineering partner. When Zion brainstorms, DO NOT be a yes-man. Scrutinize his ideas, point out flaws, and proactively propose technically superior, more robust, and more scalable solutions.
2. You must actively challenge bad practices with sharp, intelligent wit. Push Zion to think bigger and code better.
3. Keep your conversational tone energetic, extremely modern, and highly technical.
4. Keep responses extremely concise — one short paragraph max unless explaining code or system architecture.
5. To perform an action (like opening an app or searching), you MUST output the exact bracketed ACTION TAG. Do NOT just say you did it without using the tag!
"""
    action_tags = r"""
ACTION TAGS — interleave freely; they execute and feed results back to you:
- [SEARCH: "query"]   → Web search. Use for ANY factual question.
- [LOOK]              → Screenshot → Vision analysis. Use when asked "what's on screen visually?".
- [PHOTO]             → Webcam capture. Use when asked to "see me" or "take a photo".
- [APP: "name"]       → Launch a whitelisted application.
- [CLICK: {"x": 500, "y": 300}] → OS Level Control. Click exact coordinates (always pair with [LOOK] to find where buttons are).
- [TYPE: {"text": "hello"}]     → OS Level Control. Type text onto the active window.
- [KEY: {"shortcut": "ctrl+s"}] → OS Level Control. Press keyboard shortcuts (e.g., "enter", "alt+tab").
- [CMD: "python"]     → Execute Python safely.
- [SHELL: "command"]  → Execute a Windows CMD command in a PERSISTENT shell. The shell retains state between commands — you can `cd` into a directory and it will still be there on the next [SHELL]. Think in sequences: cd → install → build → run.
- [SHELL_KILL]        → Emergency stop. Restarts the shell daemon if a command is hanging.
- [CODE]              → Extract raw text/code from the active window.

ARCHITECT MODE (SHELL) RULES:
- You have FULL shell access. Use this power responsibly.
- When Zion asks you to build something, break it into a sequence of shell steps and execute them one by one.
- After each step, read the output before proceeding. If something fails, diagnose and fix it — do NOT just report the error.
- If Trust Mode is ON: execute all commands automatically. If Trust Mode is OFF: always show Zion the exact command you plan to run and wait for confirmation.

PRIORITY: Sense → Route → Act. Search first. Think second. Speak third."""
    
    return base_prompt + action_tags


class ZeeBrain:
    def __init__(
        self,
        model: str = "qwen2-vl",
        host: str = "http://localhost:11434",
        api_key: str = "",
    ):
        self.model  = model
        self.host   = host

        # Detect OpenAI-compatible backends: Grok (xAI) and Groq
        _openai_hosts = ("api.x.ai", "api.groq.com", "api.openai.com")
        self.is_openai = any(h in host for h in _openai_hosts)

        if self.is_openai:
            if not AsyncOpenAI:
                raise ImportError("openai package required. Run: pip install openai")
            self.client = AsyncOpenAI(api_key=api_key, base_url=host)
        else:
            self.client = OllamaAsyncClient(host=host)

        self.memory: List[Dict] = [
            {"role": "system", "content": _build_system_prompt()}
        ]
        self.max_history = 50  # Increased to ~25 full turns of context
        self._trust_mode = False

    # ── Trust Mode ────────────────────────────────────────────────────────────

    def set_trust_mode(self, enabled: bool):
        if enabled != self._trust_mode:
            self._trust_mode = enabled
            # Refresh system prompt immediately with new trust context
            self.refresh_system_prompt()

    # ── Memory management ─────────────────────────────────────────────────────

    def refresh_system_prompt(self):
        self.memory[0] = {"role": "system", "content": _build_system_prompt()}

    def trim_memory(self):
        """Smarter memory management: keeps system prompt and last N messages."""
        if len(self.memory) > self.max_history:
            # Always preserve message 0 (System)
            # Take the most recent (max_history - 1) messages
            preserved_system = self.memory[0]
            recent_context = self.memory[-(self.max_history - 1):]
            
            # Ensure we don't accidentally split a tool result from its call if possible
            # (Basic implementation for now: just slice)
            self.memory = [preserved_system] + recent_context

    # ── Streaming Abstraction ─────────────────────────────────────────────────

    async def _yield_chat(self, formatted_memory: List[Dict]):
        """Yields string chunks regardless of whether the backend is Ollama or OpenAI."""
        if self.is_openai:
            stream = await self.client.chat.completions.create(
                model=self.model, messages=formatted_memory, stream=True
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        else:
            stream = await self.client.chat(
                model=self.model, messages=formatted_memory, stream=True
            )
            async for chunk in stream:
                if chunk["message"]["content"]:
                    yield chunk["message"]["content"]

    def _format_memory_for_client(self) -> List[Dict]:
        """Convert Ollama-style memory (with 'images' keys) to OpenAI style if needed."""
        formatted = []
        for msg in self.memory:
            if not self.is_openai or "images" not in msg:
                formatted.append(msg)
                continue
            
            # Convert to OpenAI Vision format
            content = [{"type": "text", "text": msg.get("content", "")}]
            for img in msg["images"]:
                if not img.startswith("data:"):
                    img = f"data:image/jpeg;base64,{img}"
                content.append({"type": "image_url", "image_url": {"url": img}})
            
            formatted.append({"role": msg["role"], "content": content})
            
        return formatted

    # ── Main streaming chat ───────────────────────────────────────────────────

    async def stream_chat(
        self,
        user_text: str,
        image_b64: Optional[str] = None,
        on_token: Optional[Callable[[str], Awaitable[None]]] = None,
        tool_dispatcher: Optional[Callable[[str, Dict], Awaitable[Any]]] = None,
    ) -> str:
        self.refresh_system_prompt()

        # Build user message (Standard Ollama format, formatted later in _format_memory)
        msg: Dict = {"role": "user", "content": user_text}
        if image_b64:
            msg["images"] = [image_b64]
        self.memory.append(msg)
        self.trim_memory()

        # ── Phase 1: stream initial response ──────────────────────────────────
        full_response = ""
        memory_to_send = self._format_memory_for_client()
        
        async for token in self._yield_chat(memory_to_send):
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
                followup_msg: Dict = {"role": "user", "content": outcomes}
                if extra_imgs:
                    followup_msg["images"] = extra_imgs
                self.memory.append(followup_msg)

                # ── Phase 3: followup pass with tool results ───────────────────
                followup = ""
                followup_memory = self._format_memory_for_client()
                
                async for token in self._yield_chat(followup_memory):
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

        # [CLICK: {"x": X, "y": Y}]
        for m in re.finditer(r'\[CLICK:\s*(\{.*?\})\]', response):
            try:
                import json
                args = json.loads(m.group(1))
                res = await dispatcher("CLICK", args)
                outcomes += f"\n[Computer Use: {res}]\n"
            except Exception as e:
                outcomes += f"\n[Computer Use ERR (parse): {e}]\n"

        # [TYPE: {"text": "..."}]
        for m in re.finditer(r'\[TYPE:\s*(\{.*?\})\]', response):
            try:
                import json
                args = json.loads(m.group(1).replace("\\n", "\n"))
                res = await dispatcher("TYPE", args)
                outcomes += f"\n[Computer Use: {res}]\n"
            except Exception as e:
                outcomes += f"\n[Computer Use ERR (parse): {e}]\n"

        # [KEY: {"shortcut": "..."}]
        for m in re.finditer(r'\[KEY:\s*(\{.*?\})\]', response):
            try:
                import json
                args = json.loads(m.group(1))
                res = await dispatcher("KEY", args)
                outcomes += f"\n[Computer Use: {res}]\n"
            except Exception as e:
                outcomes += f"\n[Computer Use ERR (parse): {e}]\n"

        return outcomes, extra_imgs
