$ErrorActionPreference = "Stop"

Write-Host "Setting up Zee Virtual Environment..."
python -m venv .venv

Write-Host "Installing FFmpeg (if not installed)..."
try {
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
} catch {
    Write-Host "FFmpeg may already be installed or winget failed. Continuing..."
}

Write-Host "Activating Virtual Environment and installing requirements..."
& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "Pulling Qwen3 8b via Ollama..."
try {
    ollama pull qwen3:8b-q4_K_M
} catch {
    Write-Host "Ollama pull failed. Please ensure Ollama is installed and running."
}

Write-Host "Setup Complete!"
