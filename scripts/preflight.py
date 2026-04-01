import os
import sys
from pathlib import Path

def run_preflight():
    print("--- Zee AI v2 Preflight Check ---")
    
    # 1. Environment
    if not os.path.exists(".env"):
        print("[FAIL] .env file is missing.")
        sys.exit(1)
        
    print("[OK] .env file found.")

    # 2. Piper TTS model
    voice_name = os.getenv("PIPER_VOICE", "en_US-ryan-medium")
    piper_dir = Path(os.path.expandvars(os.getenv("PIPER_MODEL_DIR", str(Path.home() / ".local" / "share" / "piper-tts"))))
    
    if not (piper_dir / f"{voice_name}.onnx").exists():
         print(f"[FAIL] Piper TTS model '{voice_name}' not found. Run install script.")
         sys.exit(1)
         
    print("[OK] Piper TTS model found.")
    
    # 3. Import Check (spot check heavy dependencies)
    try:
        import fastapi
        import cv2
        import faster_whisper
        import openwakeword
        import mss
        import customtkinter
        print("[OK] Core dependencies can be imported.")
    except ImportError as e:
        print(f"[FAIL] Missing dependency: {e}")
        sys.exit(1)

    print("\nPreflight complete. You are clear to launch.")

if __name__ == "__main__":
    run_preflight()
