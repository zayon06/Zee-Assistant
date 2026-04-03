"""
Zee AI v2 — Client Entry Point
Starts the FastAPI server subprocess, then launches the HUD and voice pipeline.
"""
import os
import subprocess
import sys
import threading
import time

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
        python = sys.executable
        self._proc = subprocess.Popen(
            [python, "-m", "server.main"],
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
    """Background thread: wake word → STT → send to server."""
    from client.voice.wakeword import WakeWordDetector
    from client.voice.stt      import GroqSTT
    from client.voice.tts      import EdgeTTS

    stt = GroqSTT()
    tts = EdgeTTS()
    stt.load()
    tts.load()

    triggered = threading.Event()

    def on_wake():
        if hud.voice_paused:
            return
        triggered.set()

    detector = WakeWordDetector(on_triggered=on_wake)
    detector.start()

    hud.safe_add_system("Son online — say 'Hey Son' or type below.")
    hud.safe_set_state("Listening")

    def on_partial(text: str):
        hud.safe_add_system(f"Hearing: {text}")
        
    def on_volume(rms: float):
        hud.safe_animate_mic(rms)

    while not stop_event.is_set():
        if triggered.wait(timeout=0.5):
            triggered.clear()
            if hud.voice_paused:
                continue

            hud.safe_set_state("Listening")
            hud.safe_add_system("Listening…")

            text = stt.transcribe(on_partial=on_partial, on_volume=on_volume)

            if text.strip():
                hud.safe_add_message("YOU", text, "you")
                _send_and_speak(text, hud, ws_client, tts)
            else:
                hud.safe_set_state("Listening")

    detector.stop()


def _send_and_speak(text: str, hud, ws_client, tts):
    """Send user text over WebSocket; TTS will speak the final response."""
    hud.safe_set_state("Thinking")
    hud.safe_start_stream()
    ws_client.send({
        "type":        "chat",
        "text":        text,
        "screen_mode": hud.screen_mode,
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
        tag    = msg.get("tag", "")
        detail = msg.get("args", msg.get("content", ""))
        hud.safe_add_action(tag, str(detail))
        if tag == "LOOK":
            hud.after(0, hud.trigger_vision_flash)

    def on_done(final: str):
        hud.safe_end_stream()
        hud.safe_set_state("Speaking")
        tts.synthesize(final)
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
    def on_text_submit(text: str, screen_mode: bool):
        hud.safe_set_state("Thinking")
        hud.safe_start_stream()
        ws.send({"type": "chat", "text": text, "screen_mode": screen_mode})

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
