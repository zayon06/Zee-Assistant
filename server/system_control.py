"""
System Control — Volume, mss screenshots, cross-platform utilities.
"""
import base64
import io
import platform
from typing import Optional


def capture_screenshot_b64(max_dim: int = 1280) -> str:
    """Capture primary monitor via mss, return base64 JPEG string."""
    import mss
    from PIL import Image

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82)
        return base64.b64encode(buf.getvalue()).decode()


def get_volume() -> int:
    """Return current master volume (0-100), or -1 on failure."""
    try:
        if platform.system() == "Windows":
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            iface   = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol     = cast(iface, POINTER(IAudioEndpointVolume))
            return int(vol.GetMasterVolumeLevelScalar() * 100)
    except Exception:
        pass
    return -1


def set_volume(level: int) -> str:
    """Set master volume (0-100). Returns confirmation string."""
    level = max(0, min(100, level))
    try:
        if platform.system() == "Windows":
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            iface   = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol     = cast(iface, POINTER(IAudioEndpointVolume))
            vol.SetMasterVolumeLevelScalar(level / 100.0, None)
            return f"Volume set to {level}%."
        elif platform.system() == "Linux":
            import subprocess
            subprocess.run(["amixer", "sset", "Master", f"{level}%"], capture_output=True)
            return f"Volume set to {level}%."
    except Exception as e:
        return f"Volume control failed: {e}"
    return "Volume control not supported on this platform."
