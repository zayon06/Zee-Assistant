"""
Text-to-Speech — edge-tts via pygame
Uses high-quality Microsoft Edge cloud voices and plays via pygame mixer for maximum stability.
"""
import asyncio
import os
import tempfile
import time

import edge_tts
import pygame

VOICE_MODEL = os.getenv("EDGE_VOICE", "en-US-ChristopherNeural") # Let's use a good male voice for "Son"


class EdgeTTS:
    def __init__(self):
        self._loaded = False
        self._temp_file = os.path.join(tempfile.gettempdir(), "zee_speech.mp3")

    def load(self) -> bool:
        if self._loaded:
            return True
        try:
            # Initialize pygame mixer
            pygame.mixer.init()
            self._loaded = True
            print(f"[TTS] Edge-TTS ready. Voice: '{VOICE_MODEL}'")
            return True
        except Exception as e:
            print(f"[TTS] Pygame mixer init failed: {e}")
            return False

    def synthesize(self, text: str):
        if not text.strip():
            return
        if not self._loaded and not self.load():
            return

        print(f"[TTS] Synthesizing: {text!r}")
        try:
            # 1. Generate MP3 via edge-tts async inside a fresh thread to avoid loop conflicts
            communicate = edge_tts.Communicate(text, VOICE_MODEL)
            
            import threading
            def _generate():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(communicate.save(self._temp_file))
                loop.close()
                
            t = threading.Thread(target=_generate)
            t.start()
            t.join()

            # 2. Play via pygame
            pygame.mixer.music.load(self._temp_file)
            pygame.mixer.music.play()
            
            # Wait for playback to finish
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
                
            # Safely unload so we can overwrite next time
            pygame.mixer.music.unload()

        except Exception as e:
            print(f"[TTS] Playback error: {e}")
