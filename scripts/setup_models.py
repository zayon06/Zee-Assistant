import os
import urllib.request
from pathlib import Path

def setup_models():
    # 1. Wake word model: hey_jarvis.onnx
    wake_dir = Path("scripts/models")
    wake_dir.mkdir(parents=True, exist_ok=True)
    # The models were moved to release assets in v0.6.0+
    wake_model_url = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/hey_jarvis_v0.1.onnx"
    wake_model_path = wake_dir / "hey_jarvis.onnx"
    
    if not wake_model_path.exists():
        print(f"[Setup] Downloading Wake Word model: {wake_model_url}")
        urllib.request.urlretrieve(wake_model_url, wake_model_path)
        print("[Setup] Wake Word model downloaded.")

    # 1.5. Essential pre-processing models for openwakeword
    for model in ["melspectrogram.onnx", "embedding_model.onnx"]:
        path = wake_dir / model
        url = f"https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/{model}
        if not path.exists():
            print(f"[Setup] Downloading {model}: {url}")
            urllib.request.urlretrieve(url, path)
            print(f"[Setup] {model} downloaded.")
    else:
        print("[Setup] Wake Word model already exists.")

    # 2. Piper TTS model: en_US-ryan-medium.onnx
    piper_dir = Path(os.path.expandvars(os.getenv("PIPER_MODEL_DIR", str(Path.home() / ".local" / "share" / "piper-tts"))))
    piper_dir.mkdir(parents=True, exist_ok=True)
    voice_name = "en_US-ryan-medium"
    
    onnx_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/{voice_name}.onnx?download=true"
    json_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/{voice_name}.onnx.json?download=true"
    
    onnx_path = piper_dir / f"{voice_name}.onnx"
    json_path = piper_dir / f"{voice_name}.onnx.json"

    if not onnx_path.exists():
        print(f"[Setup] Downloading Piper TTS model: {onnx_url}")
        urllib.request.urlretrieve(onnx_url, onnx_path)
        urllib.request.urlretrieve(json_url, json_path)
        print("[Setup] Piper TTS model downloaded.")
    else:
        print("[Setup] Piper TTS model already exists.")

if __name__ == "__main__":
    setup_models()
