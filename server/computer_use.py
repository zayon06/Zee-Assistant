"""
Computer Use Tools - PyAutoGUI OS Action Layer
Provides mouse and keyboard automation.
"""
import pyautogui

# Failsafe will stop the execution if the user drags the mouse to the corner of the screen
pyautogui.FAILSAFE = True

def tool_click(args: dict) -> str:
    """Click at literal x,y coordinates or relative."""
    try:
        x = int(args.get("x", 0))
        y = int(args.get("y", 0))
        
        # Subtle easing for human-like movement
        pyautogui.moveTo(x, y, duration=0.3, tween=pyautogui.easeInOutQuad)
        pyautogui.click()
        return f"[OK] Clicked at ({x}, {y})."
    except Exception as e:
        return f"[ERR] Click failed: {e}"


def tool_type(args: dict) -> str:
    """Type text out."""
    text = args.get("text", "")
    try:
        if not text:
            return "[ERR] No text provided to type."
        pyautogui.write(text, interval=0.01)
        return f"[OK] Typed {len(text)} characters."
    except Exception as e:
        return f"[ERR] Typing failed: {e}"


def tool_key(args: dict) -> str:
    """Execute a keyboard shortcut."""
    shortcut = args.get("shortcut", "")
    try:
        if not shortcut:
            return "[ERR] No shortcut provided."
        
        # Parse shortcuts like "ctrl+s", "enter", "alt+tab"
        keys = [k.strip().lower() for k in shortcut.split("+")]
        pyautogui.hotkey(*keys)
        return f"[OK] Pressed: {shortcut}"
    except Exception as e:
        return f"[ERR] Key shortcut failed: {e}"
