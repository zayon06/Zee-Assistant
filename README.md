# Zee AI v2 — Setup & Installation Guide

This is the fully rebuilt, streaming client-server version of Zee AI.

## Features
1. **Screen Context** (`mss` capturing, Qwen2-VL local vision engine)
2. **Web Search** (Self-hosted SearXNG directly in Docker, DDG fallback)
3. **Voice UI** (OpenWakeWord for instant trigger, Faster-Whisper STT, Piper local TTS)
4. **App Control** (Launch local apps, adjust volume, code context reading)
5. **Streaming Backend** (FastAPI WebSocket bridging to Ollama)

## 1. Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com/) (Must have `qwen2-vl` pulled: `ollama pull qwen2-vl`)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (For SearXNG local search)

## 2. Quick Install (Windows)
Open PowerShell as Administrator and run the install script:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\scripts\install.ps1
```
*(This script creates the virtual environment, installs requirements, and downloads the Piper TTS voice model.)*

## 3. Configuration
Copy `.env.example` to `.env` and review the settings.
By default, it looks for Ollama on `localhost:11434`. 
If you use Colab/ngrok, update `OLLAMA_HOST` in `.env`.

## 4. Web Search (Docker)
Ensure Docker Desktop is running, then start SearXNG:
```powershell
docker compose -f docker/docker-compose.yml up -d
```

## 5. Running Zee
Once installed, start the client. The client will automatically spin up the background FastAPI server.
```powershell
.\.venv\Scripts\activate
python client/main.py
```

## 6. Testing
To verify core components (no voice/UI):
```powershell
.\.venv\Scripts\activate
pytest tests/ -v
```
