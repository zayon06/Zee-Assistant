import os

def disable_startup():
    startup_folder = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
    vbs_path = os.path.join(startup_folder, "ZeeAssistant.vbs")
    
    if os.path.exists(vbs_path):
        try:
            os.remove(vbs_path)
            print(f"Removed: {vbs_path}")
            print("Zee will no longer start at boot.")
        except Exception as e:
            print(f"Error removing file: {e}")
    else:
        print("Startup shortcut not found. Zee is already disabled or wasn't set up.")

if __name__ == "__main__":
    disable_startup()
