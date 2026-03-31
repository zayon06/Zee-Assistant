# Project "Zee" 🤖
### High-Performance Local AI Executive Assistant

Zee is a modular, local-first AI "Sense-Route-Act" companion designed for Zion (Director, Noiz Technologies). Built to be an elite engineering peer and brainstorming buddy, Zee operates with a minimal footprint (<2GB RAM) while providing powerful automation and vision capabilities.

---

## 🚀 The Mission
Zee acts as a "Sense-Route-Act" loop:
- **Sense**: Hears your voice, reads your screen.
- **Route**: Intelligently parses commands using a local LLM (Qwen3 8b).
- **Act**: Searches the web, launches apps, and executes system tasks.

## ✨ Key Features
- **Witty Senior Dev Persona**: Zee isn't just an assistant; he's a brainstorm buddy who asks challenging questions.
- **Transparent HUD**: A sleek, bottom-right "Noiz Tech" teal indicator showing Zee's current state (Idle, Listening, Thinking, Speaking).
- **Vision/OCR**: Zee can "see" your screen and identify line numbers or specific bugs in real-time.
- **Local-First**: All processing (LLM, STT, OCR) happens on your machine.
- **System Integration**: Runs in the background with a system tray icon and optional startup registration.

---

## 🛠️ Stack & Dependencies
- **LLM**: Ollama (Qwen3 8b)
- **Voice**: `openWakeWord` (Trigger), `faster-whisper` (STT), `piper-tts`/`pyttsx3` (TTS)
- **Vision**: `easyocr`, `pyautogui`
- **UI**: `customtkinter`, `pystray`
- **Automation**: `duckduckgo-search`, `pyperclip`

---

## 📥 Setup & Installation

### Prerequisites
1. **Ollama**: Install [Ollama](https://ollama.com/) natively on your Windows machine.
2. **FFmpeg**: Ensure FFmpeg is installed and added to your system PATH (required for audio).

### Automated Installation
Run the following script in PowerShell to set up the virtual environment and pull the models:
```powershell
.\create_env.ps1
```

---

## 🚦 How to Use

### 1. Preflight Check
Verify your hardware and model setup:
```bash
.venv/Scripts/python.exe preflight_check.py
```

### 2. Launching Zee
Start the assistant:
```bash
.venv/Scripts/python.exe main.py
```

### 3. Startup Configuration
Register Zee to start silently at boot:
```bash
.venv/Scripts/python.exe setup_startup.py
```

---

## 🧠 Brainstorm & Code Mode
- **Brainstorm Mode**: Zee will challenge your ideas on "Drone Infrastructure" or "Quantum Computing".
- **Code Mode**: Use `[LOOK]` tags to let Zee analyze your active screen for debugging.

---

## 🧠 Cloud Brain (Google Colab)
If your local machine is resource-constrained, you can offload Zee's Brain (the LLM) to Google Colab using `ngrok`.

### 1. Colab Setup Script
Create a new [Google Colab](https://colab.research.google.com/) notebook and run this optimized script:

```python
# 1. Install the missing dependency first (Critical for Ollama on Colab)
!apt-get install -y zstd

# 2. Now install Ollama
!curl -fsSL https://ollama.com/install.sh | sh

# 3. Install ngrok
!pip install pyngrok

import os
import subprocess
import time
from pyngrok import ngrok

# 4. Start Ollama server in background (with external access allowed)
os.environ["OLLAMA_ORIGINS"] = "*"
subprocess.Popen(["nohup", "ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
time.sleep(10) # Pause to ensure server is ready

# 5. Pull the model
!ollama pull qwen3:8b-q4_K_M

# 6. Setup ngrok (Replace with your actual token and domain)
NGROK_TOKEN = "3BhMiVkseqvgFEHlvVtPI05hD94_7pYgeqbqSWzJv95mb12qU"
STATIC_DOMAIN = "PASTE_YOUR_DOMAIN_HERE" # e.g., "your-name.ngrok-free.app"

ngrok.set_auth_token(NGROK_TOKEN)
public_url = ngrok.connect(11434, pyngrok_config=None, domain=STATIC_DOMAIN).public_url

print(f"\n🚀 Zee's Brain is officially live at: {public_url}")
```

### 2. Prevent Colab Disconnect (Anti-Idle)
Google Colab will automatically disconnect your session after a period of inactivity. To prevent the Brain from spinning down, press `Ctrl+Shift+I` (or `Cmd+Option+I` on Mac) to open your browser's Developer Tools on the Colab page, go to the **Console** tab, paste the following JavaScript, and press Enter:

```javascript
function KeepClicking(){
    console.log("Keeping Colab alive...");
    let connectButton = document.querySelector("colab-connect-button");
    if (connectButton && connectButton.shadowRoot) {
        let btn = connectButton.shadowRoot.getElementById("connect");
        if (btn) btn.click();
    }
}
// Runs every 60 seconds to prevent idle timeout
setInterval(KeepClicking, 60000); 
```

### 3. Local Configuration
1. Copy the `.env.example` file to a new file named `.env`.
2. Paste the `public_url` from Colab into the `OLLAMA_HOST` variable:
   ```env
   OLLAMA_HOST=https://your-static-name.ngrok-free.app
   ```
3. Restart Zee.

---
*Built by Zion by  @ Noiz Technologies.*
