"""
Speech-to-Text — Groq Cloud API via sounddevice
Records audio until silence using sounddevice, then rapidly transcribes using Groq whisper-large-v3.
"""
import io
import os
import threading
import wave
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

GROQ_API_KEY      = os.getenv("XAI_API_KEY") # Groq keys stored here in this config
STT_MODEL         = "whisper-large-v3"
SAMPLE_RATE       = 16000
CHUNK             = 1024
SILENCE_THRESHOLD = 300    # RMS energy below this = silence
MAX_SILENCE_CHUNKS = 28    # ~1.8 s of silence → stop
MIN_SPEECH_CHUNKS  = 6     # require at least ~0.4 s of speech before checking silence
MAX_DURATION_S     = 20.0  # hard limit


class GroqSTT:
    def __init__(self):
        self._loaded = False
        self._groq   = None

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self) -> bool:
        if self._loaded:
            return True
        if not GROQ_API_KEY:
            print("[STT] Missing XAI_API_KEY in .env for Groq STT.")
            return False
            
        try:
            from groq import Groq
            self._groq = Groq(api_key=GROQ_API_KEY)
            self._loaded = True
            print(f"[STT] Groq Endpoint ready. Model: '{STT_MODEL}'.")
            return True
        except Exception as e:
            print(f"[STT] Groq Init failed: {e}")
            return False

    def transcribe(
        self,
        on_partial: Optional[Callable[[str], None]] = None,
        on_volume: Optional[Callable[[float], None]] = None,
        max_duration: float = MAX_DURATION_S,
    ) -> str:
        """
        Record audio until silence detected, then send to Groq.
        """
        if not self._loaded and not self.load():
            return ""

        frames = self._record(on_volume, max_duration)
        if not frames:
            return ""

        # Make it a virtual WAV file
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"".join(frames))

        print(f"[STT] Transcribing via Groq Cloud...")
        try:
            res = self._groq.audio.transcriptions.create(
                file=("audio.wav", buf.getvalue()),
                model=STT_MODEL,
                prompt="The user is talking to their AI assistant Son.",
                response_format="text",
                language="en"
            )
            text = str(res).strip()
            print(f"[STT] → {text!r}")
            return text
        except Exception as e:
            print(f"[STT] Groq API error: {e}")
            return ""

    # ── Internal ──────────────────────────────────────────────────────────────

    def _record(
        self,
        on_volume: Optional[Callable[[float], None]],
        max_duration: float,
    ) -> list[bytes]:
        from client.voice.audio_utils import get_input_device_index, get_device_name
        idx = get_input_device_index()
        name = get_device_name(idx)
        print(f"[STT] Recording... (Device: {name})")

        stream = None
        try:
            for s_rate in [SAMPLE_RATE, 44100, 48000]:
                try:
                    current_chunk = int(CHUNK * (s_rate / SAMPLE_RATE))
                    stream = sd.InputStream(
                        samplerate=s_rate,
                        device=idx,
                        channels=1,
                        dtype='int16',
                        blocksize=current_chunk
                    )
                    stream.start()
                    print(f"[STT] Mic opened: {s_rate}Hz")
                    break
                except Exception:
                    continue
            
            if not stream:
                print("[STT] CRITICAL: Could not open InputStream with any rate.")
                return []

            actual_rate = stream.samplerate
            read_size   = int(CHUNK * (actual_rate / SAMPLE_RATE))

            frames         = []
            silence_count  = 0
            speech_count   = 0
            max_chunks     = int(actual_rate / CHUNK * max_duration)

            for _ in range(max_chunks):
                try:
                    raw_data, _ = stream.read(read_size)
                except Exception as e:
                    print(f"[STT] Read error: {e}")
                    break

                audio_raw = raw_data.flatten()

                # Resample -> 16k
                if actual_rate != SAMPLE_RATE:
                    from scipy import signal
                    audio_16k = signal.resample(audio_raw, CHUNK).astype(np.int16)
                    frames.append(audio_16k.tobytes())
                    audio = audio_16k.astype(np.float32)
                else:
                    frames.append(audio_raw.tobytes())
                    audio = audio_raw.astype(np.float32)

                rms = int(np.sqrt(np.mean(audio ** 2)))
                if on_volume: 
                    on_volume(rms)

                if rms < SILENCE_THRESHOLD:
                    silence_count += 1
                else:
                    silence_count = 0
                    speech_count += 1

                if speech_count >= MIN_SPEECH_CHUNKS and silence_count >= MAX_SILENCE_CHUNKS:
                    break

        finally:
            if stream is not None and stream.active:
                stream.stop()
                stream.close()

        return frames
