import os
import sounddevice as sd

def get_input_device_index() -> int:
    """
    Returns the best input device index based on environment variables and availability.
    Uses sounddevice instead of pyaudio.
    Priority:
    1. ZEE_INPUT_INDEX env var
    2. 'External Microphone' (name match)
    3. 'Microphone Array' or 'Microphone' (name match)
    4. Default input device
    """
    try:
        # 1. Check ENV
        env_index = os.getenv("ZEE_INPUT_INDEX")
        if env_index is not None:
            try:
                return int(env_index)
            except ValueError:
                pass

        devices = sd.query_devices()
        external_idx = -1
        internal_idx = -1
        
        for i, info in enumerate(devices):
            if info.get('max_input_channels', 0) > 0:
                name = info.get('name', '').lower()
                if "external" in name and "microphone" in name:
                    external_idx = i
                elif "array" in name or "internal" in name:
                    if internal_idx == -1: 
                        internal_idx = i
                elif "microphone" in name:
                    # Generic mic, only use if we haven't found an array/internal yet
                    if internal_idx == -1:
                        internal_idx = i

        if external_idx != -1:
            return external_idx
        if internal_idx != -1:
            return internal_idx

        # 4. Fallback to default
        try:
            return sd.default.device[0]
        except Exception:
            return 0
    except Exception:
        return 0

def get_device_name(index: int) -> str:
    try:
        info = sd.query_devices(index)
        return info.get('name', 'Unknown')
    except Exception:
        return f"Index {index}"
