#!/bin/bash

# Zee AI v2 — Bash Installation Script (for Git Bash / WSL)
echo "=================================="
echo "    Zee AI v2 Setup (Bash)"
echo "=================================="

# 1. Check Python
if ! command -v python &> /dev/null
then
    echo "Python not found. Please install Python 3.11+."
    exit 1
fi
python --version

# 2. Virtual Environment
if [ ! -d ".venv" ]; then
    echo "Creating Virtual Environment..."
    python -m venv .venv
fi
echo "Virtual Environment Ready."

# 3. Pip Install
echo "Installing dependencies..."
source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Dependency installation failed!"
    exit 1
fi
echo "Dependencies Installed."

# 4. Download Piper Voice Model
PIPER_DIR="$HOME/.local/share/piper-tts"
mkdir -p "$PIPER_DIR"

VOICE_NAME="en_US-ryan-medium"
ONNX_FILE="$PIPER_DIR/$VOICE_NAME.onnx"
JSON_FILE="$PIPER_DIR/$VOICE_NAME.onnx.json"

if [ ! -f "$ONNX_FILE" ]; then
    echo "Downloading Piper TTS voice model ($VOICE_NAME)..."
    curl -L "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/$VOICE_NAME.onnx?download=true" -o "$ONNX_FILE"
    curl -L "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/$VOICE_NAME.onnx.json?download=true" -o "$JSON_FILE"
    echo "Voice model downloaded."
else
    echo "Piper TTS voice model already exists."
fi

# 5. Env file
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env from .env.example."
fi

echo "=================================="
echo "Setup Complete!"
echo "Next steps:"
echo "1. Review .env"
echo "2. Ensure Ollama is running (ollama pull qwen2-vl)"
echo "3. Run: source .venv/Scripts/activate && python client/main.py"
