import pyaudio
try:
    p = pyaudio.PyAudio()
    count = p.get_device_count()
    print(f"--- Found {count} total audio devices ---")
    for i in range(count):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            print(f"Mic Index {i}: {info['name']}")
    p.terminate()
except Exception as e:
    print(f"Error listing devices: {e}")
