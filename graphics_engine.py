import customtkinter as ctk
import math
import threading
import tkinter as tk

ctk.set_appearance_mode("dark")

# ─── Noiz Tech Palette ────────────────────────────────────────────────────────
TEAL      = "#00E5CC"
TEAL_DIM  = "#004D45"
GREEN     = "#00FF6A"
MAGENTA   = "#FF2CF6"
DARK_BG   = "#0A0D12"
TEXT_PRI  = "#E8F4FF"

class ZeeHUD(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Transparent borderless Pill overlay
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        
        self.win_w = 320
        self.win_h = 70
        x = (screen_w // 2) - (self.win_w // 2)
        y = screen_h - self.win_h - 48  
        
        self.geometry(f"{self.win_w}x{self.win_h}+{x}+{y}")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=DARK_BG)
        
        # Windows API transparent color logic
        try:
            self.wm_attributes("-transparentcolor", DARK_BG)
        except Exception:
            pass

        self._current_state = "Idle"
        self.screen_mode = False
        self.on_text_submit = None
        self._time_offset = 0.0
        
        # Pill Frame
        self.pill = ctk.CTkFrame(self, fg_color="#121822", corner_radius=22, border_width=1, border_color=TEAL_DIM)
        self.pill.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Dot Indicator
        self.status_dot = ctk.CTkLabel(self.pill, text="●", text_color=TEAL_DIM, font=("Segoe UI", 16))
        self.status_dot.pack(side="left", padx=(15, 5))
        
        # Live Subtitle
        self.subtitle_var = tk.StringVar(value="Zee is listening...")
        self.subtitle_lbl = ctk.CTkLabel(
            self.pill, 
            textvariable=self.subtitle_var, 
            font=("Segoe UI", 11, "bold"),
            text_color=TEXT_PRI,
            anchor="w",
            width=200
        )
        self.subtitle_lbl.pack(side="left", fill="x", expand=True)

        # Micro Wave Canvas
        self.canvas = ctk.CTkCanvas(self.pill, width=40, height=20, bg="#121822", highlightthickness=0)
        self.canvas.pack(side="right", padx=(5, 15))
        
        # Text Entry Re-added For Typing Commands
        input_frame = ctk.CTkFrame(self, fg_color="transparent", height=20)
        input_frame.pack(side="bottom", fill="x", padx=40, pady=(0, 2))
        
        self.input_box = ctk.CTkEntry(
            input_frame,
            placeholder_text="cmd...",
            fg_color="#0A0D12",
            text_color=TEXT_PRI,
            border_width=0,
            font=("Courier", 10),
            height=20,
            corner_radius=10
        )
        self.input_box.pack(fill="x", expand=True)
        self.input_box.bind("<Return>", self._on_enter)
        
        self._animate()

    def _on_enter(self, event):
        text = self.input_box.get().strip()
        if not text:
            return
        self.input_box.delete(0, "end")
        self.safe_add_message("You", text, "you")
        if self.on_text_submit:
            threading.Thread(
                target=self.on_text_submit,
                args=(text, self.screen_mode),
                daemon=True
            ).start()

    def set_state(self, state: str):
        self._current_state = state
        colors = {
            "Idle":      TEAL_DIM,
            "Listening": GREEN,
            "Thinking":  TEAL,
            "Speaking":  MAGENTA,
        }
        color = colors.get(state, TEAL_DIM)
        self.pill.configure(border_color=color)
        self.status_dot.configure(text_color=color)

    def add_message(self, speaker: str, text: str, role: str = "zee"):
        clean_text = text.replace("[Action Results Handled]", "").replace("[LOOK]", "").strip()
        if not clean_text: return
        
        # Truncate string gracefully for the pill UI
        max_lens = 38
        if len(clean_text) > max_lens:
            clean_text = clean_text[:max_lens] + "..."
            
        color = TEAL if role == "zee" else GREEN
        if speaker == "System": color = TEAL_DIM
            
        self.subtitle_lbl.configure(text_color=color)
        self.subtitle_var.set(f"{speaker}: {clean_text}")

    def add_system_msg(self, text: str):
        self.add_message("System", text, "system")

    # Thread-safe API
    def safe_set_state(self, state: str):
        self.after(0, self.set_state, state)

    def safe_add_message(self, speaker: str, text: str, role: str = "zee"):
        self.after(0, self.add_message, speaker, text, role)

    def safe_add_system_msg(self, text: str):
        self.after(0, self.add_system_msg, text)

    def safe_trigger_vision_flash(self):
        self.after(0, self.trigger_vision_flash)

    def safe_set_subtitle_live(self, text: str):
        max_lens = 38
        if len(text) > max_lens: text = text[-max_lens:]
        self.after(0, lambda: self.subtitle_var.set(text))
        self.after(0, lambda: self.subtitle_lbl.configure(text_color=TEXT_PRI))

    def _animate(self):
        try:
            from hardware import hardware_service
            vol = hardware_service.current_volume
        except Exception:
            vol = 0.0

        self.canvas.delete("all")
        self._time_offset += 0.2 + (vol * 0.5)
        
        cx = 20
        cy = 10
        num_points = 20
        spacing = 40 / num_points
        
        state_colors = {
            "Idle":      TEAL_DIM,
            "Listening": GREEN,
            "Thinking":  TEAL,
            "Speaking":  MAGENTA,
        }
        base_color = state_colors.get(self._current_state, TEAL_DIM)

        pts = []
        for i in range(num_points + 1):
            x = i * spacing
            x_norm = (x - cx) / cx 
            envelope = math.exp(-(x_norm ** 2) * 4)
            wave1 = math.sin(i * 0.4 + self._time_offset)
            amplitude = 2 + (vol * 8)
            if self._current_state == "Thinking": amplitude = 4 + math.sin(self._time_offset * 3) * 2
            y = cy + (wave1) * envelope * amplitude
            pts.append((x, y))

        for i in range(len(pts)-1):
            x1, y1 = pts[i]
            x2, y2 = pts[i+1]
            thickness = 1 + int(vol * 2)
            self.canvas.create_line(x1, y1, x2, y2, fill=base_color, width=thickness, capstyle=tk.ROUND, smooth=True)

        speed = 40 if self._current_state != "Idle" else 60
        self.after(speed, self._animate)

    def trigger_vision_flash(self):
        flash = ctk.CTkToplevel(self)
        flash.attributes("-fullscreen", True)
        flash.attributes("-topmost", True)
        flash.configure(fg_color="white")
        flash.attributes("-alpha", 0.85)

        def fade(alpha):
            if alpha <= 0:
                flash.destroy()
                return
            flash.attributes("-alpha", alpha)
            self.after(30, fade, round(alpha - 0.05, 2))

        fade(0.85)
