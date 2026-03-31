import threading
import time
import os
import requests
from dotenv import load_dotenv

from graphics_engine import ZeeHUD
from hardware import hardware_service
from brain import ZeeBrain

class AppState:
    running = True

app_state = AppState()

def process_input(text: str, hud: ZeeHUD, brain: ZeeBrain, screen_mode: bool = False):
    """Shared pipeline for both voice and text input — always runs on a background thread."""
    if not text.strip():
        return

    hud.safe_set_state("Thinking")

    try:
        # If Screen Mode is on, capture immediately
        direct_image = None
        if screen_mode:
            hud.safe_add_system_msg("Capturing screen for Context...")
            direct_image = hardware_service.capture_screen_vision()
            hud.safe_trigger_vision_flash()

        response = brain.chat(text, trigger_look=hardware_service.capture_screen_vision, direct_image=direct_image)

        # Output logic
        hud.safe_add_message("Zee", response, "zee")

        if "[LOOK]" in response:
            hud.safe_trigger_vision_flash()

        hud.safe_set_state("Speaking")
        hardware_service.speak(response)

    except Exception as e:
        hud.safe_add_system_msg(f"Error: {e}")
        print(f"[Error] process_input: {e}")
    finally:
        hud.safe_set_state("Listening")


def voice_agent_loop(hud: ZeeHUD, brain: ZeeBrain):
    """Background daemon: listens for 'Hey Zee' then routes speech through brain."""
    hardware_service.init_vision()
    hardware_service.init_voice()

    hud.safe_add_system_msg("Zee Online — Say 'Zee', 'Son' or type below")
    hud.safe_set_state("Listening")

    # The callback logic updates the Subtitle immediately
    def update_live_text(partial):
        hud.safe_set_subtitle_live(f"You: {partial}")

    while app_state.running:
        try:
            triggered = hardware_service.listen_for_wakeword()

            if triggered:
                hud.safe_add_system_msg("Listening...")
                hud.safe_set_subtitle_live("You: ...")
                
                audio_text = hardware_service.record_command(duration=5, live_text_callback=update_live_text)

                if audio_text.strip():
                    process_input(audio_text, hud, brain, screen_mode=hud.screen_mode)
                else:
                    hud.safe_set_state("Listening")

        except Exception as e:
            print(f"[Error] Voice loop: {e}")
            
        time.sleep(1.5)  # Let audio driver breathe between stream re-opens to prevent Segfault


def keepalive_daemon(host: str):
    """Pings the Ngrok/Colab tunnel every 3 minutes to simulate traffic and prevent timeouts."""
    while app_state.running:
        try:
            if host:
                requests.get(f"{host}", headers={'ngrok-skip-browser-warning': 'true'}, timeout=5)
        except:
            pass
        time.sleep(180)

def main():
    load_dotenv()
    ollama_host = os.getenv("OLLAMA_HOST")

    # Start the anti-idle network ping
    threading.Thread(target=keepalive_daemon, args=(ollama_host,), daemon=True).start()

    # Use the Llama 3.2 Vision Model for the multimodal capabilities
    brain = ZeeBrain(model_name="llama3.2-vision:11b-instruct-q4_K_M", host=ollama_host)
    hud = ZeeHUD()

    def on_text(text: str, screen_mode: bool = False):
        process_input(text, hud, brain, screen_mode=screen_mode)

    hud.on_text_submit = on_text

    voice_thread = threading.Thread(
        target=voice_agent_loop, args=(hud, brain), daemon=True
    )
    voice_thread.start()

    hud.mainloop()

    hardware_service.shutdown()
    app_state.running = False


if __name__ == "__main__":
    main()
