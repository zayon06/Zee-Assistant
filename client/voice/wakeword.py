"""
Wake Word Detector — OpenWakeWord
Default model: hey_jarvis (no training required, ships with openwakeword).
Set WAKE_WORD_MODEL in .env to use a different built-in model.
Built-ins: hey_jarvis, alexa, hey_mycroft, hey_rhasspy
"""
import os
import threading
from typing import Callable

import numpy as np
import pyaudio

WAKE_MODEL = os.getenv("WAKE_WORD_MODEL", "hey_jarvis")
THRESHOLD  = float(os.getenv("WAKE_THRESHOLD", "0.5"))
CHUNK      = 1280   # ~80 ms at 16 kHz — optimal for openwakeword
RATE       = 16000


class WakeWordDetector:
    def __init__(self, on_triggered: Callable[[], None]):
        self.on_triggered = on_triggered
        self._running = False
        self._model   = None
        self._thread: threading.Thread | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        self._running = True
        self._thread  = threading.Thread(
            target=self._listen_loop, daemon=True, name="wakeword"
        )
        self._thread.start()

    def stop(self):
        self._running = False

    # ── Internal ──────────────────────────────────────────────────────────────

    def _load(self) -> bool:
        try:
            from openwakeword.model import Model
            
            # If path doesn't exist as a direct file, try relative to scripts/models
            model_path = WAKE_MODEL
            if not os.path.exists(model_path):
                alt_path = os.path.join("scripts", "models", f"{WAKE_MODEL}.onnx")
                if os.path.exists(alt_path):
                    model_path = alt_path
                else:
                    # Fallback to just the name (will try resources)
                    model_path = WAKE_MODEL

            self._model = Model(
                wakeword_models=[model_path],
                inference_framework="onnx",
            )
            print(f"[WakeWord] Loaded: {model_path} — threshold {THRESHOLD}")
            return True
        except Exception as e:
            print(f"[WakeWord] Load failed: {e}")
            return False

    def _listen_loop(self):
        if not self._load():
            return

        pa     = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )
        print("[WakeWord] Listening…")
        try:
            while self._running:
                raw   = stream.read(CHUNK, exception_on_overflow=False)
                audio = np.frombuffer(raw, dtype=np.int16)
                preds = self._model.predict(audio)
                for name, score in preds.items():
                    if score >= THRESHOLD:
                        print(f"[WakeWord] Triggered! {name}={score:.2f}")
                        self.on_triggered()
                        # Brief cooldown so we don't re-fire immediately
                        import time; time.sleep(1.0)
                        break
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
