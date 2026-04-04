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

    # Wake words (soundalikes included since Whisper sometimes guesses these for 'Son')
    WAKE_WORDS = r'^(son|sun|zion|zone|sam|song|sum|some)[\s\,\.\?!]'

    while not stop_event.is_set():
        try:
            # Peek if F5 is pressed right now (in case it starts while paused)
            current_ptt = keyboard.is_pressed('f5')
        except Exception:
            current_ptt = False

        if hud.voice_paused and not current_ptt:
            time.sleep(0.1)
            continue

        hud.safe_set_state("Listening")

        ptt_used = [False]
        def is_active_callback() -> bool:
            try:
                state = keyboard.is_pressed('f5')
                if state:
                    ptt_used[0] = True
                return state
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

        # Check if the text starts with the Wake Word
        match = re.search(WAKE_WORDS, clean_text, re.IGNORECASE)
        
        # Override wake word check if F5 was used
        if ptt_used[0]:
            command = clean_text[match.end():].strip() if match else clean_text
            if command:
                hud.safe_set_input_text("") # Clear live typing
                hud.safe_add_message("YOU (F5)", clean_text, "you")
                _send_and_speak(command, hud, ws_client, tts)
            continue

        if match:
            # Wake word detected! Extract the actual command by removing the wake word
            command = clean_text[match.end():].strip()
            
            # If the user just said "Son" and paused, we still want to acknowledge.
            if not command:
                command = "Hello."

            hud.safe_set_input_text("") # Clear live typing
            hud.safe_add_message("YOU", clean_text, "you")
            _send_and_speak(command, hud, ws_client, tts)
        else:
            # It heard speech but it wasn't for Son. Ignore it.
            hud.safe_set_input_text("") # Clear partials
            hud.safe_set_state("Listening")


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
        hud.safe_add_action(tag, detail)
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
