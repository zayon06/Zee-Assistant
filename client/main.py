"""
Zee AI v2 — Client Entry Point
Starts the FastAPI server subprocess, then launches the HUD and voice pipeline.
"""
import os
import subprocess
import sys
import threading
import time
import re
import keyboard

from typing import Optional
from dotenv import load_dotenv

load_dotenv()


WS_URL  = f"ws://localhost:{os.getenv('ZEE_WS_PORT', '8765')}/ws"
WS_PORT =  int(os.getenv("ZEE_WS_PORT", "8765"))


# ── Server process manager ────────────────────────────────────────────────────

class ServerManager:
    def __init__(self):
        self._proc: subprocess.Popen | None = None

    def start(self):
        """Spawn the Zee server as a subprocess."""
        import sys
        if getattr(sys, 'frozen', False):
            # If running as PyInstaller bundle
            server_cmd = [sys.executable, "--run-server"]
        else:
            server_cmd = [sys.executable, "-m", "server.main"]

        self._proc = subprocess.Popen(
            server_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
        )
        # Forward server logs to console
        def _log():
            for line in self._proc.stdout:
                print(f"[Server] {line}", end="")
        threading.Thread(target=_log, daemon=True).start()
        print(f"[Client] Server PID {self._proc.pid} started.")

    def stop(self):
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            print("[Client] Server stopped.")

    def wait_ready(self, timeout: float = 15.0) -> bool:
        """Poll /health until the server responds or timeout."""
        import httpx
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                r = httpx.get(
                    f"http://localhost:{WS_PORT}/health", timeout=2.0
                )
                if r.status_code == 200:
                    print("[Client] Server is ready.")
                    return True
            except Exception:
                pass
            time.sleep(0.8)
        print("[Client] WARNING: server didn't respond in time — continuing anyway.")
        return False


# ── Voice agent ───────────────────────────────────────────────────────────────

def voice_agent(hud, ws_client, stop_event: threading.Event):
    """Background thread: Continuous Cloud STT to act as Wake Word + Command Processor."""
    from client.voice.stt      import GroqSTT
    from client.voice.tts      import EdgeTTS
    import re

    stt = GroqSTT()
    tts = EdgeTTS()
    stt.load()
    tts.load()

    hud.safe_add_system("Son online — say 'Son' or type below.")
    hud.safe_set_state("Listening")

    def on_partial(text: str):
        hud.safe_set_input_text(text)
        
    def on_volume(rms: float):
        hud.safe_animate_mic(rms)

    while not stop_event.is_set():
        try:
            current_ptt = keyboard.is_pressed('right shift')
        except Exception:
            current_ptt = False

        if not current_ptt:
            if hud._state == "Listening":
                hud.safe_set_state("Idle")
            time.sleep(0.05)
            continue

        hud.safe_set_state("Listening")

        def is_active_callback() -> bool:
            try:
                return keyboard.is_pressed('right shift')
            except Exception:
                return False

        def is_muted_callback() -> bool:
            return getattr(hud, 'is_speaking', False)

        text = stt.transcribe(
            on_partial=on_partial, 
            on_volume=on_volume, 
            is_active=is_active_callback,
            is_muted=is_muted_callback
        )
        clean_text = text.strip()

        if not clean_text:
            continue

        hud.safe_set_input_text("") # Clear live typing
        hud.safe_add_message("YOU (Right Shift)", clean_text, "you")
        _send_and_speak(clean_text, hud, ws_client, tts, None)


def _send_and_speak(text: str, hud, ws_client, tts, image_b64: Optional[str] = None):
    """Send user text over WebSocket; TTS will speak the final response."""
    hud.safe_set_state("Thinking")
    hud.safe_start_stream()
    ws_client.send({
        "type":        "chat",
        "text":        text,
        "image":       image_b64,
        "screen_mode": hud.screen_mode,
        "trust_mode":  getattr(hud, "trust_mode", False),
    })
    # TTS is triggered by on_done callback registered in main()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    from client.hud       import ZeeHUD
    from client.ws_client import ZeeWSClient
    from client.voice.tts import EdgeTTS

    server  = ServerManager()
    server.start()
    server.wait_ready()

    tts     = EdgeTTS()
    tts.load()
    stop_ev = threading.Event()
    hud     = ZeeHUD()

    def on_token(token: str):
        hud.safe_append_token(token)

    def on_action(msg: dict):
        tag     = msg.get("tag", "")
        msg_type = msg.get("type", "action")  # "action" = outgoing query, "result" = incoming data

        if msg_type == "result":
            # Show the actual result content
            content = msg.get("content", "")
            if tag == "SEARCH" and content:
                hud.safe_add_action(f"SEARCH RESULTS", content, show=True)
            elif content and content != "[image attached]":
                hud.safe_add_action(tag, content, show=True)
        else:
            # Outgoing query — hide query detail for SEARCH, show for others
            detail = msg.get("args", msg.get("content", ""))
            hud.safe_add_action(tag, detail, show=(tag != "SEARCH"))

        if tag == "LOOK":
            hud.after(0, hud.trigger_vision_flash)

    def on_done(final: str):
        hud.safe_end_stream()
        hud.safe_set_state("Speaking")
        hud.is_speaking = True
        tts.synthesize(final)
        hud.is_speaking = False
        hud.safe_set_state("Listening")

    def on_error(msg: str):
        hud.safe_add_system(f"⚠ {msg}")
        hud.safe_set_state("Idle")

    def on_connect():
        hud.safe_add_system("Connected to Zee server.")
        hud.safe_set_state("Listening")

    ws = ZeeWSClient(
        url=WS_URL,
        on_token=on_token,
        on_action=on_action,
        on_done=on_done,
        on_error=on_error,
        on_connect=on_connect,
    )
    ws.start()

    # Text input callback
    def on_text_submit(text: str, screen_mode: bool, image_b64: Optional[str] = None):
        _send_and_speak(text, hud, ws, tts, image_b64)

    hud.on_text_submit  = on_text_submit
    hud.on_voice_toggle = lambda: None  # placeholder

    # Voice thread
    voice_thread = threading.Thread(
        target=voice_agent,
        args=(hud, ws, stop_ev),
        daemon=True,
        name="voice-agent",
    )
    voice_thread.start()

    try:
        hud.mainloop()
    finally:
        stop_ev.set()
        server.stop()


if __name__ == "__main__":
    main()
