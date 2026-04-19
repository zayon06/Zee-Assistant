"""
ShellDaemon — Persistent CMD shell with stateful environment.
Son can cd into directories, install packages, and build projects
without losing context between commands.
"""
import asyncio
import threading
import subprocess
import queue
import re
import os
import io
import base64
from typing import Optional, List, Dict, Any, Tuple

try:
    import pyautogui
    from PIL import Image
except ImportError:
    pyautogui = None

try:
    import cv2
except ImportError:
    cv2 = None


def capture_screenshot_b64() -> str:
    """Capture full screen and return as base64 string."""
    if not pyautogui:
        raise ImportError("pyautogui and Pillow required for screenshots.")
    
    screenshot = pyautogui.screenshot()
    # Resize for performance and to stay within token limits
    screenshot.thumbnail((1280, 720))
    
    buf = io.BytesIO()
    screenshot.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def capture_webcam_b64() -> str:
    """Capture webcam frame and return as base64 string."""
    if not cv2:
        raise ImportError("opencv-python (cv2) required for webcam capture.")
    
    cam = cv2.VideoCapture(0)
    if not cam.is_opened():
        return "Error: Could not open webcam."
    
    ret, frame = cam.read()
    cam.release()
    
    if not ret:
        return "Error: Could not read frame from webcam."
    
    # Convert BGR to RGB
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(frame_rgb)
    img.thumbnail((800, 600))
    
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

TIMEOUT_S = 20
_SENTINEL = "[__CMD_DONE__]"
_BLACKLIST = [
    r"rm\s+-rf",
    r"del\s+/[sS]",
    r"format\s+[a-zA-Z]:",
    r"shutdown",
    r"reg\s+delete",
    r"bcdedit",
    r"rd\s+/[sS]",
    r"rmdir\s+/[sS]",
]


class ShellDaemon:
    """A single, long-lived CMD process that retains environment context."""

    def __init__(self):
        self._proc: Optional[subprocess.Popen] = None
        self._out_q: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._reader_thread: Optional[threading.Thread] = None

    def start(self):
        """Boot the PowerShell process."""
        self._proc = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self._reader_thread = threading.Thread(
            target=self._read_output, daemon=True, name="shell-reader"
        )
        self._reader_thread.start()

    def _read_output(self):
        """Background thread: drain stdout into the queue."""
        for line in iter(self._proc.stdout.readline, ""):
            self._out_q.put(line)
        self._out_q.put(None)  # signal process dead

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def restart(self):
        """Force restart the shell daemon."""
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
        self._proc = None
        self.start()

    def run(self, command: str, timeout: int = TIMEOUT_S) -> str:
        """
        Synchronously run a command and return its output.
        Thread-safe via lock.
        """
        if not self.is_alive():
            self.restart()

        with self._lock:
            # Clear output queue before running
            while not self._out_q.empty():
                try:
                    self._out_q.get_nowait()
                except queue.Empty:
                    break

            # Inject command + sentinel
            # Using ; to separate commands in PowerShell, and Write-Output for the sentinel
            full_cmd = f"{command}; Write-Output '{_SENTINEL}'\n"
            try:
                self._proc.stdin.write(full_cmd)
                self._proc.stdin.flush()
            except (BrokenPipeError, AttributeError):
                self.restart()
                self._proc.stdin.write(full_cmd)
                self._proc.stdin.flush()

            lines = []
            deadline = timeout
            while deadline > 0:
                try:
                    line = self._out_q.get(timeout=1)
                    if line is None:
                        # Process died mid-command; restart for next time
                        self.restart()
                        break
                    stripped = line.rstrip("\n")
                    if _SENTINEL in stripped:
                        break
                    lines.append(stripped)
                except queue.Empty:
                    deadline -= 1

            if deadline <= 0:
                return "[WARN] Command timed out. It may still be running in the background."

            output = "\n".join(l for l in lines if l.strip())
            return output if output else "[OK] Executed. No output."


# Singleton — one shell process per server lifetime
shell_daemon = ShellDaemon()


def check_safety(command: str) -> Optional[str]:
    """Returns a block message if the command is dangerous, else None."""
    for pattern in _BLACKLIST:
        if re.search(pattern, command, re.IGNORECASE):
            return f"[BLOCK] Blocked: '{command}' matches a safety rule."
    return None
