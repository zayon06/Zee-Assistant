<#
.SYNOPSIS
    Automated installation script for Zee AI v2 on Windows.
#>

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "    Zee AI v2 Setup" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan

# 1. Check Python
$python_ver = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python not found. Please install Python 3.11+." -ForegroundColor Red
    exit 1
}
Write-Host "Detected: $python_ver" -ForegroundColor Green

# 2. Virtual Environment
if (-Not (Test-Path ".venv")) {
    Write-Host "Creating Virtual Environment..." -ForegroundColor Yellow
    python -m venv .venv
}
Write-Host "Virtual Environment Ready." -ForegroundColor Green

# 3. Pip Install
Write-Host "Installing dependencies... (this may take a few minutes if downloading torches)" -ForegroundColor Yellow
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Dependency installation failed!" -ForegroundColor Red
    exit 1
}
Write-Host "Dependencies Installed." -ForegroundColor Green

# 4. Download Piper Voice Model (if not exists)
$piper_dir = "$env:USERPROFILE\.local\share\piper-tts"
if (-not (Test-Path $piper_dir)) {
    New-Item -ItemType Directory -Force -Path $piper_dir | Out-Null
}

$voice_name = "en_US-ryan-medium"
$onnx_file = "$piper_dir\$voice_name.onnx"
$json_file = "$piper_dir\$voice_name.onnx.json"

if (-not (Test-Path $onnx_file)) {
    Write-Host "Downloading Piper TTS voice model ($voice_name)..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/$voice_name.onnx?download=true" -OutFile $onnx_file
    Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/$voice_name.onnx.json?download=true" -OutFile $json_file
    Write-Host "Voice model downloaded." -ForegroundColor Green
} else {
    Write-Host "Piper TTS voice model already exists." -ForegroundColor Green
}

# 5. Env file
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example." -ForegroundColor Green
}

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Review .env" -ForegroundColor Yellow
Write-Host "2. Ensure Ollama is running (ollama pull qwen2-vl)" -ForegroundColor Yellow
Write-Host "3. Run: .\.venv\Scripts\python client/main.py" -ForegroundColor Yellow
