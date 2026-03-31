import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import sys
import threading
import os

class AppController:
    def __init__(self):
        self.icon = None
        self.running = True
        self._setup_logging()

    def _setup_logging(self):
        """Redirect stdout/stderr to zee.log for hidden mode."""
        # Simple setup for redirecting stream if app runs in hidden mode
        # In a real deployed app, logging module handle this better.
        if "ZEE_HIDDEN" in os.environ:
            sys.stdout = open("zee.log", "a")
            sys.stderr = open("zee.log", "a")

    def _create_image(self):
        """Generate a basic Noiz Tech teal logo dynamically for the tray."""
        image = Image.new('RGB', (64, 64), (0, 0, 0))
        dc = ImageDraw.Draw(image)
        # Draw a teal circle outline for the Noiz Tech identity
        dc.ellipse((10, 10, 54, 54), outline='#00FFFF', width=4)
        dc.text((22, 24), "Z", fill='#00FFFF', stroke_width=1)
        return image

    def start_tray(self):
        """Blocking tray icon thread."""
        image = self._create_image()
        
        menu = (
             item('Settings', self.open_settings),
             item('Show Log', self.show_log),
             item('Quit', self.stop)
        )
        
        self.icon = pystray.Icon("Zee", image, "Zee by Noiz Tech", menu)
        
        # Starts on its own thread
        tray_thread = threading.Thread(target=self.icon.run, daemon=True)
        tray_thread.start()

    def open_settings(self, icon, item):
        import tools
        tools.launch_app("notepad.exe") # Placeholder for actual settings UI

    def show_log(self, icon, item):
        import tools
        tools.launch_app("zee.log")
        
    def stop(self, icon, item):
        print("[System] Shutting down...")
        self.running = False
        if self.icon:
            self.icon.stop()
        sys.exit(0)

app_state = AppController()
