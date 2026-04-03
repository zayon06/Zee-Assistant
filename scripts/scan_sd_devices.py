import sounddevice as sd
print("--- SD INPUT DEVICES ---")
devices = sd.query_devices()
for i, d in enumerate(devices):
    if d['max_input_channels'] > 0:
        print(f"Index {i}: {d['name']}")
