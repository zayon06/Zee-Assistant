"""
Speech-to-Text — Groq Cloud API via sounddevice (Callback Mode)
Records audio using callback to avoid 'Blocking API not supported' on Windows WDM-KS.
"""
import io
import os
import queue
import wave
import threading
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

GROQ_API_KEY      = os.getenv("XAI_API_KEY") 
STT_MODEL         = "whisper-large-v3"
SAMPLE_RATE       = 16000
CHUNK             = 1024
SILENCE_THRESHOLD = 200    # Increased to reject static/hum
MAX_SILENCE_CHUNKS = 12    # ~0.8s of silence → stop
MIN_SPEECH_CHUNKS  = 6     # require at least ~0.4s of speech before checking silence
MAX_DURATION_S     = 20.0  # hard limit


class GroqSTT:
    def __init__(self):
        self._loaded = False
        self._groq   = None
        self._queue  = queue.Queue()

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

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"[STT] Callback Status: {status}")
        self._queue.put(indata.copy())

    def transcribe(
        self,
        on_partial: Optional[Callable[[str], None]] = None,
        on_volume: Optional[Callable[[float], None]] = None,
        max_duration: float = MAX_DURATION_S,
        is_active: Optional[Callable[[], bool]] = None,
    ) -> str:
        if not self._loaded and not self.load():
            return ""

        # Clear queue for fresh recording
        with self._queue.mutex:
            self._queue.queue.clear()

        frames = self._record(on_volume, on_partial, max_duration, is_active)
        if not frames:
            return ""

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
                prompt="Son.",
                response_format="text",
                language="en"
            )
            text = str(res).strip()
            # Filter common Whisper hallucinations
            rejects = ["Thanks for watching", "Subscribe", "amara.org", "Son."]
            for r in rejects:
                if r.lower() in text.lower():
                    return ""
            print(f"[STT] → {text!r}")
            return text
        except Exception as e:
            print(f"[STT] Groq API error: {e}")
            return ""

    def _transcribe_background(self, frames: list[bytes], on_partial: Callable[[str], None]):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"".join(frames))
        try:
            res = self._groq.audio.transcriptions.create(
                file=("partial.wav", buf.getvalue()),
                model=STT_MODEL,
                prompt="Son.",
                response_format="text",
                language="en"
            )
            text = str(res).strip()
            
            rejects = ["Thanks for watching", "Subscribe", "amara.org", "Son."]
            is_hallucination = any(r.lower() in text.lower() for r in rejects)

            if text and not is_hallucination:
                print(f"[STT] Live: {text}")
                on_partial(text)
        except Exception:
            pass

    def _record(
        self,
        on_volume: Optional[Callable[[float], None]],
        on_partial: Optional[Callable[[str], None]],
        max_duration: float,
        is_active: Optional[Callable[[], bool]] = None,
    ) -> list[bytes]:
        from client.voice.audio_utils import get_input_device_index, get_device_name
        idx = get_input_device_index()
        name = get_device_name(idx)
        print(f"[STT] Recording... (Device: {name})")

        stream = None
        for s_rate in [SAMPLE_RATE, 44100, 48000]:
            if stream: break
            for channels in [1, 2]:
                try:
                    current_chunk = int(CHUNK * (s_rate / SAMPLE_RATE))
                    stream = sd.InputStream(
                        samplerate=s_rate,
                        device=idx,
                        channels=channels,
                        dtype='int16',
                        callback=self._callback,
                        blocksize=current_chunk
                    )
                    stream.start()
                    print(f"[STT] Successfully opened {s_rate}Hz {channels}-channel stream (Callback Mode).")
                    break
                except Exception:
                    continue
        
        if not stream:
            print("[STT] CRITICAL: Could not open InputStream with any rate.")
            return []

        actual_rate = stream.samplerate
        actual_chan = stream.channels
        
        audio_frames   = []
        silence_count  = 0
        speech_count   = 0
        last_partial_len = 0
        was_active     = False
        max_chunks     = int(actual_rate / CHUNK * max_duration)

        try:
            for _ in range(max_chunks):
                try:
                    raw_data = self._queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # 1. Downsample channels to Mono if needed
                if actual_chan > 1:
                    audio_mono = np.mean(raw_data, axis=1).astype(np.int16)
                else:
                    audio_mono = raw_data.flatten()

                # 2. Resample to 16kHz if needed
                if actual_rate != SAMPLE_RATE:
                    from scipy import signal
                    target_len = int(len(audio_mono) * (SAMPLE_RATE / actual_rate))
                    audio_16k = signal.resample(audio_mono, target_len).astype(np.int16)
                    audio_frames.append(audio_16k.tobytes())
                    audio_float = audio_16k.astype(np.float32)
                else:
                    audio_frames.append(audio_mono.tobytes())
                    audio_float = audio_mono.astype(np.float32)

                rms = int(np.sqrt(np.mean(audio_float ** 2)))
                if on_volume: 
                    on_volume(rms)

                # Push-to-Talk logic
                currently_active = is_active() if is_active is not None else False
                
                if currently_active:
                    was_active = True
                    silence_count = 0
                    speech_count += 1  # Force speech count to ensure it returns the buffer
                else:
                    if was_active:
                        print("[STT] Done: Push-to-Talk released.")
                        break

                # Trigger background transcription chunk every ~1.5 seconds of audio
                if on_partial and len(audio_frames) - last_partial_len > (SAMPLE_RATE / CHUNK * 1.5):
                    last_partial_len = len(audio_frames)
                    if speech_count >= MIN_SPEECH_CHUNKS:
                        threading.Thread(
                            target=self._transcribe_background,
                            args=(audio_frames.copy(), on_partial),
                            daemon=True
                        ).start()

                if rms < SILENCE_THRESHOLD:
                    silence_count += 1
                else:
                    silence_count = 0
                    speech_count += 1

                if not currently_active:
                    if speech_count >= MIN_SPEECH_CHUNKS and silence_count >= MAX_SILENCE_CHUNKS:
                        print(f"[STT] Done: Speech heard ({speech_count}) -> Silence reached ({silence_count})")
                        break
        except Exception as e:
            print(f"[STT] Recording error: {e}")
        finally:
            if stream is not None:
                stream.stop()
                stream.close()

        if speech_count >= MIN_SPEECH_CHUNKS:
            return audio_frames
        return []
