# BUILD.md: Zee Technical Documentation

This file serves as the core technical documentation and build logic blueprint for **Project "Zee"**, the local AI executive assistant.

## 1. System Architecture

Zee is designed using a multi-threaded, Sense-Route-Act architecture. Because Python's Global Interpreter Lock (GIL) handles UI sequentially, hardware threading is explicitly separated to avoid blocking the GUI.

### Component Map
*   **`main.py`** (The Orchestrator)
    *   **Thread 0 (Main)**: Runs `ctk.CTk.mainloop()` ensuring Native GUI scaling and transparency works under Windows.
    *   **Thread 1 (Agent Loop)**: Runs the Sense-Route-Act loop asynchronously.
    *   **Thread 2 (Tray Loop)**: `pystray` system tray hooked daemon thread.
*   **`graphics_engine.py`** 
    *   Extends `customtkinter.CTk`. 
    *   `ws_ex_layered` APIs are bypassed by relying on CTK's internal `-transparentcolor` win32 API wrapper, rendering pure black pixels as transparent alpha channels.
*   **`brain.py`** 
    *   Handles Prompt Engineering constraints limit memory window to 10-turns to aggressively prevent RAM bloating and context-window breakdown typical of 8b local models.
    *   Provides Tag Parsing Regex to intercept actions sequentially.

## 2. RAM Constraint Engineering (< 2GB Target)

1.  **Audio Processing (`faster-whisper`)**:
    *   Uses `tiny.en` loaded using `device="cpu"` and `compute_type="int8"`. 
    *   This quantization structure limits the PyTorch footprint to under 150MB active VRAM.
2.  **Vision Engine (`easyocr`)**:
    *   Initialized with `gpu=False` specifically. While slower on CPU (~2.5 seconds per capture), it ensures the VRAM budget is entirely reserved for Ollama inference.
3.  **Language Model (`qwen3:8b-q4_K_M`)**:
    *   The `q4` wrapper ensures 4-bit precision, costing only roughly `~1.1 GB RAM` actively.
    *   With standard OS overhead, total process sum sits nicely at `~1.6 - 1.8 GB RAM`.

## 3. Data Flow & Security Constraints

Since Zee relies extensively on local processing, all data streams are inherently secure and offline.

*   **Offline Mode**: Completely functional without Wi-Fi unless the `[SEARCH]` protocol is routed.
*   **RCE Risk**: The `[CMD:"python"]` router relies on Python's `exec()`. There are **no sandboxes** active on this module because the system assumes maximum trust for Zee to alter OS-level sound and applications.

## 4. Pipeline for Executable Compilation

If you desire to compile Zee into a standalone `Zee.exe` to distribute internally at Noiz Technologies without exposing source files, execute the following build instructions:

### Build Requirements
```bash
pip install pyinstaller
```

### PyInstaller Script (`build.bat`)
Create a `build.bat` with the underlying logic:
```bat
pyinstaller --noconfirm --onedir --windowed --add-data "C:/Users/RMC/OneDrive/Desktop/Zee-Ai-buddy/.venv/Lib/site-packages/customtkinter;customtkinter/" --hidden-import "openwakeword" --hidden-import "faster_whisper" --hidden-import "easyocr" --icon "assets/favicon.ico"  "main.py"
```

*Note: Extracting `faster-whisper` hidden binaries and `.onnx` models into PyInstaller distributions requires significant `.spec` file modifications due to C++ compilation paths.*
