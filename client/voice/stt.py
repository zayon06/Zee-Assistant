"""
Speech-to-Text — Faster-Whisper
Records until silence, returns full transcription.
Live partial callback supported for real-time HUD updates.
"""
import os
import threading
from typing import Callable, Optional

import numpy as np
import pyaudio

STT_MODEL         = os.getenv("WHISPER_MODEL", "base")
SAMPLE_RATE       = 16000
CHUNK             = 1024
SILENCE_THRESHOLD = 500    # RMS energy below this = silence
MAX_SILENCE_CHUNKS = 28    # ~1.8 s of silence → stop
MIN_SPEECH_CHUNKS  = 6     # require at least ~0.4 s of speech before checking silence
MAX_DURATION_S     = 20.0  # hard limit


class FasterWhisperSTT:
    def __init__(self):
        self._model      = None
        self._model_lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self) -> bool:
        with self._model_lock:
            if self._model:
                return True
            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(
                    STT_MODEL, device="cpu", compute_type="int8"
                )
                print(f"[STT] Faster-Whisper '{STT_MODEL}' ready.")
                return True
            except Exception as e:
                print(f"[STT] Load failed: {e}")
                return False

    def transcribe(
        self,
        on_partial: Optional[Callable[[str], None]] = None,
        max_duration: float = MAX_DURATION_S,
    ) -> str:
        """
        Record audio until silence detected, return transcription.
        `on_partial` is called each time a new segment is heard.
        """
        if not self._model and not self.load():
            return ""

        frames         = self._record(on_partial, max_duration)
        audio_np       = (
            np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32)
            / 32768.0
        )

        segments, _    = self._model.transcribe(
            audio_np, language="en", beam_size=5, vad_filter=True
        )
        text           = " ".join(s.text for s in segments).strip()
        print(f"[STT] → {text!r}")
        return text

    # ── Internal ──────────────────────────────────────────────────────────────

    def _record(
        self,
        on_partial: Optional[Callable[[str], None]],
        max_duration: float,
    ):
        pa     = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )

        frames         = []
        silence_count  = 0
        speech_count   = 0
        max_chunks     = int(SAMPLE_RATE / CHUNK * max_duration)
        accumulated    = ""

        print("[STT] Recording…")
        try:
            for _ in range(max_chunks):
                raw    = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(raw)

                audio  = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
                rms    = int(np.sqrt(np.mean(audio ** 2)))

                if rms < SILENCE_THRESHOLD:
                    silence_count += 1
                else:
                    silence_count  = 0
                    speech_count  += 1

                # Live partial callback — transcribe last 1-second window
                if on_partial and speech_count % 16 == 0 and len(frames) >= 16:
                    chunk_np = (
                        np.frombuffer(b"".join(frames[-16:]), dtype=np.int16)
                        .astype(np.float32) / 32768.0
                    )
                    try:
                        segs, _ = self._model.transcribe(
                            chunk_np, language="en", beam_size=1, vad_filter=False
                        )
                        partial = " ".join(s.text for s in segs).strip()
                        if partial:
                            accumulated = partial
                            on_partial(accumulated)
                    except Exception:
                        pass

                if speech_count >= MIN_SPEECH_CHUNKS and silence_count >= MAX_SILENCE_CHUNKS:
                    break
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

        return frames
