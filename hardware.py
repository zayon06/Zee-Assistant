import os
import io
import pyaudio
import numpy as np
import base64

os.environ["OMP_NUM_THREADS"] = "1"

# Wake word variants
WAKE_VARIANTS = ["son", "sun", "sunn", "san", "sonny"]

class ZeeHardware:
    def __init__(self):
        self.vosk_model = None
        self.running = True
        self.paused = False       
        self.current_volume = 0.0 
        self.pa = pyaudio.PyAudio()
        self.mic_stream = None

    # ─── Vision ───────────────────────────────────────────────────────────────

    def init_vision(self):
        """Prepare screenshot dependencies; OCR is deprecated for Llama Vision."""
        print("[System] Vision Engine ready (Base64 Mode).")

    def capture_screen_vision(self) -> str:
        """Takes a screenshot, downscales it, and converts to Base64 for Ollama Vision."""
        try:
            import pyautogui
            from PIL import Image
            img = pyautogui.screenshot()
            
            # Save for user verification
            os.makedirs("screenshots", exist_ok=True)
            img.save("zee_last_vision.jpg")

            # Max dimension 1024 to save inference time on Llama Vision
            img.thumbnail((1024, 1024), Image.LANCZOS)
            
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=80)
            img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
            
            return img_b64
        except Exception as e:
            print(f"[Vision Error]: {e}")
            return ""

    # ─── Voice ────────────────────────────────────────────────────────────────

    def _init_vosk(self):
        try:
            from vosk import Model
            import urllib.request
            import zipfile
            
            model_path = "model"
            if not os.path.exists(model_path):
                print("[System] Downloading tiny Vosk STT model...")
                url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
                urllib.request.urlretrieve(url, "model.zip")
                with zipfile.ZipFile("model.zip", 'r') as zip_ref:
                    zip_ref.extractall(".")
                os.rename("vosk-model-small-en-us-0.15", model_path)
                if os.path.exists("model.zip"): os.remove("model.zip")
                
            self.vosk_model = Model(model_path)
            print("[System] Vosk live streaming STT engine ready.")
        except Exception as e:
            print(f"[Voice] Vosk load failed: {e}")

    def init_voice(self):
        print("[System] Initializing Vosk Engine...")
        self._init_vosk()

    def _safe_stream(self, rate=16000, chunk=4000):
        if self.mic_stream:
            try:
                self.mic_stream.stop_stream()
                self.mic_stream.close()
            except Exception:
                pass
        try:
            self.mic_stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=rate,
                input=True,
                frames_per_buffer=chunk
            )
            return True
        except Exception as e:
            print(f"[Error] Failed to open mic stream: {e}")
            return False

    def listen_for_wakeword(self) -> bool:
        if not self.vosk_model or self.paused:
            return False

        if not self._safe_stream():
            return False

        from vosk import KaldiRecognizer
        rec = KaldiRecognizer(self.vosk_model, 16000)

        silence_threshold = 800
        print("[System] Listening for 'Son'...")
        
        try:
            import json
            while self.running and not self.paused:
                data = self.mic_stream.read(4000, exception_on_overflow=False)
                
                audio_np = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_np).mean()
                self.current_volume = min(volume / 5000.0, 1.0)

                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    transcription = res.get("text", "").lower()
                    
                    if any(variant in transcription for variant in WAKE_VARIANTS):
                        print(f"[Trigger] Wake word: '{transcription}'")
                        return True
                else:
                    # Check partials occasionally to be faster
                    partial = json.loads(rec.PartialResult()).get("partial", "").lower()
                    if any(variant in partial for variant in WAKE_VARIANTS):
                        print(f"[Trigger] Wake word (partial): '{partial}'")
                        return True

        finally:
            self.current_volume = 0.0

        return False

    def take_photo(self) -> str:
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return "Failed to open webcam."
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                cv2.imwrite("zee_last_photo.jpg", frame)
                # Send photo as b64 directly if needed, or stick to OS response
                return "Photo taken successfully and saved as zee_last_photo.jpg."
            return "Failed to capture image from webcam."
        except Exception as e:
            return f"Photo capture failed: {e}"

    def record_command(self, duration: int = 5, live_text_callback=None) -> str:
        """Stream transcription and return full text when user goes silent."""
        if not self.vosk_model:
            return ""

        if not self._safe_stream():
            return ""

        from vosk import KaldiRecognizer
        import json
        rec = KaldiRecognizer(self.vosk_model, 16000)

        frames = []
        silence_limit = 20  # ~1.2 seconds of silence (20 chunks of 1000 frames)
        silence_count = 0
        min_chunks = 20
        max_duration_chunks = int((16000 / 1000) * max(duration, 15))

        final_text = ""
        current_partial = ""

        try:
            for chunk_idx in range(max_duration_chunks):
                data = self.mic_stream.read(1000, exception_on_overflow=False)
                
                audio_np = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_np).mean()
                self.current_volume = min(volume / 5000.0, 1.0)
                
                if volume < 500:
                    silence_count += 1
                else:
                    silence_count = 0

                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    text = res.get("text", "")
                    if text:
                        final_text += text + " "
                        current_partial = text
                        if live_text_callback:
                            live_text_callback(final_text)
                else:
                    part = json.loads(rec.PartialResult()).get("partial", "")
                    if part:
                        current_partial = part
                        if live_text_callback:
                            live_text_callback(final_text + part)
                
                if chunk_idx > min_chunks and silence_count >= silence_limit:
                    if not final_text.strip() and not current_partial.strip():
                        continue # wait a bit more if null
                    break
                    
            if current_partial and not final_text.endswith(current_partial + " "):
                final_text += current_partial
        finally:
            self.current_volume = 0.0

        return final_text.strip()

    def speak(self, text: str):
        print(f"[Zee]: {text}")
        try:
            import asyncio
            import edge_tts
            import pygame
            import os
            
            # Using Microsoft's offline-neural C++ backend stream (No LLM generation)
            VOICE = "en-US-GuyNeural"
            
            async def _generate_audio():
                communicate = edge_tts.Communicate(text, VOICE, rate="+10%")
                await communicate.save("zee_speech.mp3")

            asyncio.run(_generate_audio())
            
            pygame.mixer.init()
            pygame.mixer.music.load("zee_speech.mp3")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.quit()
            
            try:
                os.remove("zee_speech.mp3")
            except:
                pass
                
        except Exception as e:
            print(f"[TTS] Failed: {e}")

    def shutdown(self):
        self.running = False
        try:
            if self.mic_stream:
                self.mic_stream.stop_stream()
                self.mic_stream.close()
        except Exception:
            pass
        if self.pa:
            try:
                self.pa.terminate()
            except Exception:
                pass


hardware_service = ZeeHardware()
