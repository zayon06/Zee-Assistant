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
from typing import Any, Dict, Optional

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
            img.thumbnail((1920, 1080), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75)
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


# ── APP launch (dynamic directory scan) ──────────────────────────────────────

# Search roots — ordered by priority
_APP_SEARCH_ROOTS = [
    r"C:\Users\RMC\AppData\Local\Programs",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\Windows\System32",
    r"C:\Windows",
]

# In-session cache: name.lower() → full exe path
_APP_CACHE: Dict[str, str] = {}

# System commands that don't need a full path scan
_SYSTEM_CMDS: Dict[str, str] = {
    "notepad":          "notepad.exe",
    "calculator":       "calc.exe",
    "explorer":         "explorer.exe",
    "terminal":         "wt.exe",
    "windows terminal": "wt.exe",
    "cmd":              "cmd.exe",
    "task manager":     "taskmgr.exe",
    "control panel":    "control.exe",
    "paint":            "mspaint.exe",
    "wordpad":          "wordpad.exe",
}


def _find_exe_regex(pattern_str: str) -> Optional[str]:
    """Search _APP_SEARCH_ROOTS for an exe matching the regex pattern. Returns full path or None."""
    try:
        # Pre-compile the pattern for performance, making it case-insensitive
        regex = re.compile(pattern_str, re.IGNORECASE)
    except re.error:
        # Fallback to literal search if regex is invalid
        regex = re.compile(re.escape(pattern_str), re.IGNORECASE)

    for root in _APP_SEARCH_ROOTS:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip uninstaller and helper directories
            dirnames[:] = [
                d for d in dirnames
                if "uninstall" not in d.lower() and "crashreport" not in d.lower()
            ]
            for fname in filenames:
                if not fname.lower().endswith(".exe"):
                    continue
                if "uninstall" in fname.lower() or "update" in fname.lower():
                    continue

                # Test regex against either the full filename or the stem
                stem = fname.rsplit(".", 1)[0]
                if regex.search(fname) or regex.search(stem):
                    return os.path.join(dirpath, fname)
    return None


async def tool_app(args: Dict) -> str:
    name = args.get("name", "").strip()
    if not name:
        return "[ERR] No app name provided."

    def _launch():
        # 1. System commands/aliases first (literal matching)
        name_lower = name.lower()
        if name_lower in _SYSTEM_CMDS:
            target = _SYSTEM_CMDS[name_lower]
            subprocess.Popen(target, shell=True)
            return f"[OK] Launched {name}."

        # 2. Cache hit (literal matching)
        if name_lower in _APP_CACHE:
            try:
                os.startfile(_APP_CACHE[name_lower])
                return f"[OK] Launched {name} (cached)."
            except Exception:
                del _APP_CACHE[name_lower]

        # 3. Dynamic Regex scan
        path = _find_exe_regex(name)
        if path:
            _APP_CACHE[name_lower] = path
            try:
                os.startfile(path)
                return f"[OK] Launched {name} matching {path}."
            except Exception as e:
                return f"Found {path} but launch failed: {e}"

        # 4. Start Menu .lnk fallback with Regex
        try:
            regex = re.compile(name, re.IGNORECASE)
        except re.error:
            regex = re.compile(re.escape(name), re.IGNORECASE)

        for base in [
            os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        ]:
            if not os.path.isdir(base):
                continue
            for root, _, files in os.walk(base):
                for f in files:
                    if f.endswith(".lnk") and regex.search(f) and "uninstall" not in f.lower():
                        try:
                            os.startfile(os.path.join(root, f))
                            return f"[OK] Launched {name} via Start Menu shortcut ({f})."
                        except Exception:
                            pass

        return f"[ERR] App matching '{name}' not found. Try a different regex pattern."

    return await _run(_launch)



# ── SHELL (persistent CMD daemon) ────────────────────────────────────────────

async def tool_shell(args: Dict) -> str:
    from server.system_control import shell_daemon, check_safety
    command = args.get("command", "")

    # Safety gate
    blocked = check_safety(command)
    if blocked:
        return blocked

    # Boot daemon on first use
    if not shell_daemon.is_alive():
        def _start():
            shell_daemon.start()
        await _run(_start)

    def _exec():
        return shell_daemon.run(command)

    return await _run(_exec)


async def tool_shell_kill(args: Dict) -> str:
    """Kill the shell daemon (emergency stop for runaway processes)."""
    from server.system_control import shell_daemon
    try:
        shell_daemon.restart()
        return "[OK] Shell daemon restarted. Environment reset."
    except Exception as e:
        return f"Kill failed: {e}"



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

# ── COMPUTER USE (PyAutoGUI) ──────────────────────────────────────────────────
async def _wrap_computer_use(fn, args: Dict) -> str:
    return await _run(fn, args)

async def handle_click(args: Dict) -> str:
    from server.computer_use import tool_click
    return await _wrap_computer_use(tool_click, args)

async def handle_type(args: Dict) -> str:
    from server.computer_use import tool_type
    return await _wrap_computer_use(tool_type, args)

async def handle_key(args: Dict) -> str:
    from server.computer_use import tool_key
    return await _wrap_computer_use(tool_key, args)


# ── Dispatcher ────────────────────────────────────────────────────────────────
_TOOL_MAP = {
    "SEARCH":     tool_search,
    "LOOK":       tool_look,
    "PHOTO":      tool_photo,
    "APP":        tool_app,
    "SHELL":      tool_shell,
    "SHELL_KILL": tool_shell_kill,
    "CMD":        tool_cmd,
    "CODE":       tool_code,
    "CLICK":      handle_click,
    "TYPE":       handle_type,
    "KEY":        handle_key,
}


async def dispatch(tag: str, args: Dict) -> Any:
    fn = _TOOL_MAP.get(tag.upper())
    if fn:
        return await fn(args)
    return f"Unknown tool: {tag}"
