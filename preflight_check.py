import sys
import os
from dotenv import load_dotenv
from ollama import Client
import tools
from hardware import hardware_service

def verify():
    print("--- ZEE PREFLIGHT CHECK ---")

    # 1. Ollama Test
    load_dotenv()
    ollama_host = os.getenv("OLLAMA_HOST")
    print(f"[1] Checking Ollama Qwen 8b Model (Host: {ollama_host or 'localhost'})...")
    try:
        # Skip ngrok warning
        headers = {'ngrok-skip-browser-warning': 'true'}
        client = Client(host=ollama_host, headers=headers) if ollama_host else Client()
        res = client.chat(model='qwen3:8b-q4_K_M', messages=[{'role': 'user', 'content': 'Test'}])
        print("    [OK] Ollama Responded.")
    except Exception as e:
        print(f"    [FAIL] Ollama Error: {e}")

    # 2. Vision Test
    print("[2] Checking EasyOCR and Vision...")
    try:
        hardware_service.init_vision()
        test_txt = hardware_service.capture_screen_text()
        print(f"    [OK] Screen Read Bytes: {len(test_txt)}")
    except Exception as e:
        print(f"    [FAIL] Vision failed: {e}")

    # 3. Voice Test
    print("[3] Checking STT / Whisper...")
    try:
        hardware_service.init_voice()
        print("    [OK] Whisper and Wakeword Loaded.")
    except Exception as e:
        print(f"    [FAIL] Voice Engine Load Failed: {e}")

    # 4. Search Test
    print("[4] Checking Internet Search...")
    try:
        r = tools.search_web("Noiz Technologies", max_results=1)
        if "Noiz" in r or len(r) > 10:
            print("    [OK] DuckDuckGo Search Successful.")
        else:
            print("    [FAIL] DuckDuckGo Return Invalid.")
    except Exception as e:
         print(f"    [FAIL] Search Error: {e}")
         
    print("----------------------------")
    print("Preflight Complete. If all tests say [OK], execute main.py to start.")

if __name__ == "__main__":
    verify()
