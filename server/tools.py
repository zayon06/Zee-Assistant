"""
Tool Registry — All Zee action tag handlers.
Each tool is an async function receiving a dict of args.
"""
import asyncio
import base64
import io
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

_pool = ThreadPoolExecutor(max_workers=4)


async def _run(fn, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_pool, fn, *args)


# ── SEARCH ────────────────────────────────────────────────────────────────────
async def tool_search(args: Dict) -> str:
    from server.search import search_service
    return await search_service.search(args.get("query", ""))


# ── LOOK (screenshot) ─────────────────────────────────────────────────────────
async def tool_look(args: Dict) -> Any:
    def _capture():
        import mss
        from PIL import Image

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            img.thumbnail((1280, 720), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=82)
            return base64.b64encode(buf.getvalue()).decode()

    try:
        return {"image": await _run(_capture)}
    except Exception as e:
        return f"Screenshot failed: {e}"


# ── PHOTO (webcam) ────────────────────────────────────────────────────────────
async def tool_photo(args: Dict) -> Any:
    def _capture():
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return None
        ret, frame = cap.read()
        cap.release()
        if ret:
            _, buf = cv2.imencode(".jpg", frame)
            return base64.b64encode(buf.tobytes()).decode()
        return None

    try:
        b64 = await _run(_capture)
        return {"image": b64} if b64 else "Webcam unavailable."
    except Exception as e:
        return f"Photo failed: {e}"


# ── APP launch ────────────────────────────────────────────────────────────────
APP_WHITELIST: Dict[str, str] = {
    "chrome":           "chrome.exe",
    "google chrome":    "chrome.exe",
    "edge":             "msedge.exe",
    "notepad":          "notepad.exe",
    "calculator":       "calc.exe",
    "explorer":         "explorer.exe",
    "terminal":         "wt.exe",
    "windows terminal": "wt.exe",
    "vscode":           "code",
    "vs code":          "code",
    "spotify":          "spotify.exe",
    "discord":          "discord.exe",
    "slack":            "slack.exe",
    "antigravity": (
        r"C:\Users\RMC\AppData\Local\Programs\Antigravity\Antigravity.exe"
    ),
}


async def tool_app(args: Dict) -> str:
    name = args.get("name", "").lower().strip()

    def _launch():
        import platform
        if platform.system() != "Windows":
            return "App launching only supported on Windows."
        if name in APP_WHITELIST:
            target = APP_WHITELIST[name]
            try:
                os.startfile(target)
                return f"Launched {name}."
            except Exception:
                subprocess.Popen(target, shell=True)
                return f"Launched {name}."

        # Start Menu scan fallback
        for base in [
            os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        ]:
            for root, _, files in os.walk(base):
                for f in files:
                    if (
                        f.endswith(".lnk")
                        and name in f.lower()
                        and "uninstall" not in f.lower()
                    ):
                        try:
                            os.startfile(os.path.join(root, f))
                            return f"Launched {name} via Start Menu."
                        except Exception:
                            pass
        return f"App '{name}' not found."

    return await _run(_launch)


# ── SHELL ─────────────────────────────────────────────────────────────────────
_SHELL_BLACKLIST = [
    r"rm\s+-rf", r"del\s+/[sS]", r"format\s+",
    r"shutdown", r"reg\s+delete", r"bcdedit",
]


async def tool_shell(args: Dict) -> str:
    command = args.get("command", "")
    for pattern in _SHELL_BLACKLIST:
        if re.search(pattern, command, re.IGNORECASE):
            return f"Blocked for safety: '{command}'"

    def _exec():
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=15
            )
            out = result.stdout.strip()
            err = result.stderr.strip()
            parts = []
            if out:
                parts.append(f"STDOUT:\n{out}")
            if err:
                parts.append(f"STDERR:\n{err}")
            return "\n".join(parts) or "Executed. No output."
        except subprocess.TimeoutExpired:
            return "Timed out (15 s limit)."
        except Exception as e:
            return f"Shell error: {e}"

    return await _run(_exec)


# ── CMD (Python exec) ─────────────────────────────────────────────────────────
async def tool_cmd(args: Dict) -> str:
    code = args.get("code", "")

    def _exec():
        import io as _io
        from contextlib import redirect_stderr, redirect_stdout
        out_buf, err_buf = _io.StringIO(), _io.StringIO()
        try:
            with redirect_stdout(out_buf), redirect_stderr(err_buf):
                exec(code, {"__builtins__": __builtins__})  # noqa: S102
            parts = []
            if out_buf.getvalue().strip():
                parts.append(f"Output:\n{out_buf.getvalue().strip()}")
            if err_buf.getvalue().strip():
                parts.append(f"Stderr:\n{err_buf.getvalue().strip()}")
            return "\n".join(parts) or "Executed successfully."
        except Exception as e:
            return f"Exec error: {e}"

    return await _run(_exec)


# ── CODE context ──────────────────────────────────────────────────────────────
async def tool_code(args: Dict) -> str:
    from server.code_assist import get_code_context
    return await _run(get_code_context)


# ── Dispatcher ────────────────────────────────────────────────────────────────
_TOOL_MAP = {
    "SEARCH": tool_search,
    "LOOK":   tool_look,
    "PHOTO":  tool_photo,
    "APP":    tool_app,
    "SHELL":  tool_shell,
    "CMD":    tool_cmd,
    "CODE":   tool_code,
}


async def dispatch(tag: str, args: Dict) -> Any:
    fn = _TOOL_MAP.get(tag.upper())
    if fn:
        return await fn(args)
    return f"Unknown tool: {tag}"
