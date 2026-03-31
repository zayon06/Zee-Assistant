import os
import sys

def create_startup_shortcut():
    """Generates a VBScript wrapper to launch main.py silently at boot."""
    if sys.platform != 'win32':
        print("Startup script only supports Windows.")
        return

    startup_dir = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    vbs_path = os.path.join(startup_dir, "ZeeAssistant.vbs")
    
    current_dir = os.path.abspath(os.path.dirname(__file__))
    python_exe = os.path.join(current_dir, ".venv", "Scripts", "pythonw.exe")
    main_py = os.path.join(current_dir, "main.py")

    # VBScript to run in hidden window mode (0 = Hide)
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run chr(34) & "{python_exe}" & chr(34) & " " & chr(34) & "{main_py}" & chr(34), 0
Set WshShell = Nothing
'''

    try:
        with open(vbs_path, "w") as f:
            f.write(vbs_content)
        print(f"Startup shortcut generated implicitly at: {vbs_path}")
        print("Zee will now start silently in the background at boot.")
    except Exception as e:
        print(f"Failed to create startup shortcut: {e}")

if __name__ == "__main__":
    create_startup_shortcut()
