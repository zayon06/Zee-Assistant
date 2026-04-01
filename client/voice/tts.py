"""
Text-to-Speech — Piper TTS (offline, streaming sentence-by-sentence).
Falls back to edge-tts if Piper model is not installed.
"""
import io
import os
import re
import threading
import wave
from pathlib import Path
from typing import Optional

PIPER_VOICE     = os.getenv("PIPER_VOICE", "en_US-ryan-medium")
PIPER_MODEL_DIR = Path(
    os.path.expandvars(
        os.getenv("PIPER_MODEL_DIR", str(Path.home() / ".local" / "share" / "piper-tts"))
    )
)
SAMPLE_RATE = 22050


def _split_sentences(text: str) -> list[str]:
    """Strip action tags and split into speakable sentences."""
    clean = re.sub(r"\[.*?\]", "", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", clean)
    return [p.strip() for p in parts if p.strip()]


class PiperTTS:
    def __init__(self):
        self._voice      = None
        self._loaded     = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self) -> bool:
        try:
            from piper.voice import PiperVoice
            model_path  = PIPER_MODEL_DIR / f"{PIPER_VOICE}.onnx"
            config_path = PIPER_MODEL_DIR / f"{PIPER_VOICE}.onnx.json"

            if not model_path.exists():
                print(f"[TTS] Piper model not found at {model_path}. Run install script.")
                return False

            self._voice  = PiperVoice.load(
                str(model_path), config_path=str(config_path)
            )
            self._loaded = True
            print(f"[TTS] Piper '{PIPER_VOICE}' ready.")
            return True
        except Exception as e:
            print(f"[TTS] Piper load failed: {e}")
            return False

    def speak(self, text: str):
        """Speak text asynchronously; cancels any ongoing speech first."""
        self.stop()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, args=(text,), daemon=True, name="tts"
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

    def wait(self):
        if self._thread and self._thread.is_alive():
            self._thread.join()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run(self, text: str):
        if not self._loaded and not self.load():
            self._edge_fallback(text)
            return

        import numpy as np
        import sounddevice as sd

        for sentence in _split_sentences(text):
            if self._stop_event.is_set():
                break
            try:
                buf = io.BytesIO()
                with wave.open(buf, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(SAMPLE_RATE)
                    self._voice.synthesize(sentence, wf)

                buf.seek(44)  # skip WAV header
                raw = buf.read()
                if not raw:
                    continue

                audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                sd.play(audio, samplerate=SAMPLE_RATE)
                sd.wait()
            except Exception as e:
                print(f"[TTS] Sentence error: {e}")

    def _edge_fallback(self, text: str):
        """edge-tts online fallback when Piper model is missing."""
        print("[TTS] Using edge-tts fallback…")
        try:
            import asyncio
            import edge_tts
            import pygame

            async def _gen():
                com = edge_tts.Communicate(text, "en-US-GuyNeural", rate="+10%")
                await com.save("_zee_tts.mp3")

            asyncio.run(_gen())
            pygame.mixer.init()
            pygame.mixer.music.load("_zee_tts.mp3")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.quit()
            try:
                os.remove("_zee_tts.mp3")
            except Exception:
                pass
        except Exception as e:
            print(f"[TTS] edge-tts also failed: {e}")
