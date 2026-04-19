# Zee AI v2 — Setup & Installation Guide

This is the fully rebuilt, streaming client-server version of Zee AI.

## Features
1. **Screen Context** (`mss` capturing, Qwen2-VL local vision engine)
2. **Web Search** (Built-in DuckDuckGo search)
3. **Voice UI** (OpenWakeWord for instant trigger, Faster-Whisper STT, Piper local TTS)
4. **App Control** (Launch local apps, adjust volume, code context reading)
5. **Streaming Backend** (FastAPI WebSocket bridging to Ollama)

## 1. Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com/) (Must have `qwen2-vl` pulled: `ollama pull qwen2-vl`)
- [Ollama](https://ollama.com/) (Must have `qwen2-vl` pulled: `ollama pull qwen2-vl`)

## 2. Quick Install (Bash)
Open your terminal (Git Bash recommended) and run:
```bash
chmod +x scripts/install.sh
./scripts/install.sh
```
*(This script creates the virtual environment, installs requirements, and downloads the Piper TTS voice model.)*

## 3. Configuration
Copy `.env.example` to `.env` and review the settings.
By default, it looks for Ollama on `localhost:11434`. 
If you use Colab/ngrok, update `OLLAMA_HOST` in `.env`.



## 5. Running Zee
Once installed, start the client. The client will automatically spin up the background FastAPI server.
```bash
.venv/Scripts/python -m client.main
```

## 6. Testing
To verify core components (no voice/UI):
```bash
source .venv/Scripts/activate
pytest tests/ -v
```
