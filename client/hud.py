"""
ZeeHUD v2 — Enhanced CustomTkinter Interface
- Live token streaming (text appears character-by-character)
- Pulse-ring orb animation with state colours
- Screen / Voice mode toggles
- Click message to copy to clipboard
- System tray via pystray
- Drag, resize, minimize  (borderless window)
"""
import math
import threading
import tkinter as tk
from tkinter import filedialog
import os
import base64
from typing import Callable, Optional

import customtkinter as ctk

ctk.set_appearance_mode("dark")

# ── Colour System ─────────────────────────────────────────────────────────────
TEAL      = "#00E5CC"
TEAL_DIM  = "#003D36"
TEAL_GLOW = "#00FFE0"
GREEN     = "#00FF6A"
MAGENTA   = "#FF2CF6"
AMBER     = "#FFB020"
DARK_BG   = "#0D1017"
PANEL_BG  = "#12161F"
BORDER    = "#1E2535"
TEXT_PRI  = "#E8F4FF"
TEXT_DIM  = "#5A6880"
RED_HOVER = "#6E1020"


class ZeeHUD(ctk.CTk):
    def __init__(self):
        super().__init__()

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        self.win_w, self.win_h = 440, 730
        self.MIN_W, self.MIN_H = 320, 480
        x = sw - self.win_w - 48
        y = (sh - self.win_h) // 2

        self.geometry(f"{self.win_w}x{self.win_h}+{x}+{y}")
        self.minsize(self.MIN_W, self.MIN_H)
        self.resizable(True, True)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.94)
        self.wm_attributes("-transparentcolor", DARK_BG)
        self.configure(fg_color=DARK_BG)
        self.title("Son — Noiz Technologies")

        # State
        self._state       = "Idle"
        self.screen_mode  = False
        self.voice_paused = False
        self.trust_mode   = False   # Trust Mode: True = Son runs shell without confirmation
        self._angle       = 0.0
        self._pulse       = 68.0
        self._pulse_dir   = 1

        # Image Attachment State
        self._attached_image_b64: Optional[str] = None
        self._attached_image_name: Optional[str] = None

        # Drag / resize
        self._dx = self._dy = 0
        self._rx = self._ry = self._rw = self._rh = 0

        # Streaming
        self._stream_label: Optional[ctk.CTkLabel] = None
        self._stream_buf   = ""

        # Callbacks (set by main.py)
        self.on_text_submit:   Optional[Callable[[str, bool], None]] = None
        self.on_voice_toggle:  Optional[Callable[[], None]]           = None

        self._build_ui()
        self._animate()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Title bar
        self.title_bar = ctk.CTkFrame(
            self, fg_color="#090C12", height=46, corner_radius=0
        )
        self.title_bar.pack(fill="x", side="top")
        self.title_bar.pack_propagate(False)
        for widget in [self.title_bar]:
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>",     self._drag_move)

        brand = ctk.CTkLabel(
            self.title_bar, text="SON",
            font=("Segoe UI", 17, "bold"), text_color=TEAL
        )
        brand.pack(side="left", padx=(18, 0))
        brand.bind("<ButtonPress-1>", self._drag_start)
        brand.bind("<B1-Motion>",     self._drag_move)

        sub = ctk.CTkLabel(
            self.title_bar, text=" · NOIZ TECHNOLOGIES",
            font=("Segoe UI", 9), text_color=TEXT_DIM
        )
        sub.pack(side="left")
        sub.bind("<ButtonPress-1>", self._drag_start)
        sub.bind("<B1-Motion>",     self._drag_move)

        ctrl = ctk.CTkFrame(self.title_bar, fg_color="transparent")
        ctrl.pack(side="right", padx=(0, 8))
        ctk.CTkButton(
            ctrl, text="─", width=30, height=22,
            fg_color="transparent", hover_color="#1C2030",
            text_color=TEXT_DIM, command=self._minimize
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            ctrl, text="✕", width=30, height=22,
            fg_color="transparent", hover_color=RED_HOVER,
            text_color=TEXT_DIM, command=self.destroy
        ).pack(side="left", padx=2)

        # Orb canvas
        self.canvas = tk.Canvas(
            self, width=180, height=180, bg=DARK_BG, highlightthickness=0
        )
        self.canvas.pack(pady=(12, 2))

        # Status label
        self.status_var = tk.StringVar(value="● IDLE")
        self.status_lbl = ctk.CTkLabel(
            self, textvariable=self.status_var,
            font=("Courier New", 10, "bold"), text_color=TEXT_DIM
        )
        self.status_lbl.pack()

        # Mode toggles row
        mode_row = ctk.CTkFrame(self, fg_color="transparent")
        mode_row.pack(fill="x", padx=18, pady=(6, 0))

        self.screen_btn = ctk.CTkButton(
            mode_row, text="👁  SCREEN", width=106, height=28,
            fg_color=TEAL_DIM, hover_color="#005046",
            text_color=TEXT_DIM, corner_radius=8,
            font=("Segoe UI", 10, "bold"), command=self.toggle_screen
        )
        self.screen_btn.pack(side="left", padx=(0, 6))

        self.trust_btn = ctk.CTkButton(
            mode_row, text="⚡ TRUST OFF", width=110, height=28,
            fg_color="#3D1010", hover_color="#5A1A1A",
            text_color="#FF6060", corner_radius=8,
            font=("Segoe UI", 10, "bold"), command=self.toggle_trust
        )
        self.trust_btn.pack(side="left")

        # Chat scroll area
        self.chat_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=PANEL_BG,
            border_width=1,
            border_color=BORDER,
            corner_radius=12,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=TEAL_DIM,
        )
        self.chat_frame.pack(pady=(10, 6), padx=18, fill="both", expand=True)

        # Input bar
        input_row = ctk.CTkFrame(
            self, fg_color="#141820", corner_radius=12,
            border_width=1, border_color=BORDER, height=50
        )
        input_row.pack(fill="x", padx=18, pady=(0, 14))
        input_row.pack_propagate(False)

        self.input_box = ctk.CTkEntry(
            input_row,
            placeholder_text="Say 'Hey Son' or type here…",
            fg_color="transparent",
            text_color=TEXT_PRI,
            placeholder_text_color=TEXT_DIM,
            border_width=0,
            font=("Segoe UI", 12),
        )
        self.input_box.pack(
            side="left", fill="both", expand=True, padx=(12, 0)
        )
        self.input_box.bind("<Return>", self._on_enter)

        # Image Attach Button
        self.image_btn = ctk.CTkButton(
            input_row, text="📷", width=36, height=36,
            fg_color="transparent", hover_color="#1C2030",
            text_color=TEXT_DIM, font=("Segoe UI", 16),
            command=self._select_image
        )
        self.image_btn.pack(side="left", padx=4)

        # Image Badge (hidden by default)
        self.image_badge = ctk.CTkLabel(
            input_row, text="", font=("Segoe UI", 10, "bold"),
            text_color=AMBER, fg_color="#2A2000", corner_radius=6
        )
        # We'll pack/unpack it dynamically

        self.mic_lbl = ctk.CTkLabel(
            input_row, text="●", width=36, height=36,
            fg_color="transparent", text_color=TEAL_DIM,
            corner_radius=18, font=("Segoe UI", 16)
        )
        self.mic_lbl.pack(side="right", padx=(0, 4), pady=6)

        send_btn = ctk.CTkButton(
            input_row, text="↑", width=36, height=36,
            fg_color=TEAL_DIM, hover_color=TEAL,
            text_color=TEAL, corner_radius=10,
            font=("Segoe UI", 14, "bold"),
            command=lambda: self._on_enter(None)
        )
        send_btn.pack(side="right", padx=(0, 6), pady=6)

        # Resize handle
        handle = ctk.CTkLabel(
            self, text="⠿", text_color=TEAL_DIM,
            font=("Segoe UI", 14), cursor="sizing"
        )
        handle.place(relx=1.0, rely=1.0, anchor="se", x=-4, y=-4)
        handle.bind("<ButtonPress-1>", self._resize_start)
        handle.bind("<B1-Motion>",     self._resize_move)

    # ── Window controls ───────────────────────────────────────────────────────

    def _drag_start(self, e):
        self._dx = e.x_root - self.winfo_x()
        self._dy = e.y_root - self.winfo_y()

    def _drag_move(self, e):
        self.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _minimize(self):
        self.overrideredirect(False)
        self.iconify()
        self.bind("<Map>", self._on_restore)

    def _on_restore(self, _):
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.unbind("<Map>")

    def _resize_start(self, e):
        self._rx, self._ry = e.x_root, e.y_root
        self._rw, self._rh = self.winfo_width(), self.winfo_height()

    def _resize_move(self, e):
        nw = max(self.MIN_W, self._rw + (e.x_root - self._rx))
        nh = max(self.MIN_H, self._rh + (e.y_root - self._ry))
        self.geometry(f"{int(nw)}x{int(nh)}")

    # ── State & Messaging ─────────────────────────────────────────────────────

    def set_state(self, state: str):
        self._state = state
        MAP = {
            "Idle":      (TEXT_DIM, "● IDLE"),
            "Listening": (GREEN,    "◉ LISTENING"),
            "Thinking":  (TEAL,     "◈ THINKING"),
            "Speaking":  (MAGENTA,  "◎ SPEAKING"),
            "Streaming": (AMBER,    "▶ STREAMING"),
        }
        color, label = MAP.get(state, (TEXT_DIM, state.upper()))
        self.status_var.set(label)
        self.status_lbl.configure(text_color=color)

        if state == "Listening":
            self.mic_lbl.configure(text_color=TEAL_DIM, fg_color="transparent")
        else:
            self.mic_lbl.configure(text_color=TEXT_DIM, fg_color="transparent")

    def safe_set_input_text(self, text: str):
        self.after(0, self._set_input_text, text)

    def _set_input_text(self, text: str):
        self.input_box.delete("0", "end")
        self.input_box.insert("0", text)


    def toggle_screen(self):
        self.screen_mode = not self.screen_mode
        on = self.screen_mode
        self.screen_btn.configure(
            fg_color=TEAL if on else TEAL_DIM,
            text_color=DARK_BG if on else TEXT_DIM,
        )
        self.safe_add_system(
            f"Screen Analysis {'ON — Son sees every message' if on else 'OFF'}."
        )

    def toggle_trust(self):
        self.trust_mode = not self.trust_mode
        on = self.trust_mode
        self.trust_btn.configure(
            text="⚡ TRUST ON" if on else "⚡ TRUST OFF",
            fg_color=AMBER if on else "#3D1010",
            hover_color="#8A5A00" if on else "#5A1A1A",
            text_color=DARK_BG if on else "#FF6060",
        )
        self.safe_add_system(
            "⚡ Trust Mode ON — Son will execute shell commands automatically."
            if on else
            "🛡 Trust Mode OFF — Son will ask before running any shell command."
        )

    def add_message(self, speaker: str, text: str, role: str = "zee"):
        clean = text.strip()
        # Only skip if both speaker is a badge-only (⚙) and text is empty
        if not clean and not speaker.startswith("⚙"):
            return
        if not clean and speaker.startswith("⚙"):
            # Render a compact badge-only row with no text body
            row = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
            row.pack(fill="x", pady=(4, 0))
            COLOR = {"zee": TEAL, "you": GREEN, "system": TEXT_DIM, "action": AMBER}
            color = COLOR.get(role, TEXT_DIM)
            ctk.CTkLabel(
                row, text=speaker.upper(), font=("Segoe UI", 10, "bold"), text_color=color
            ).pack(anchor="w", padx=8)
            self.chat_frame._parent_canvas.yview_moveto(1.0)
            return

        COLOR = {"zee": TEAL, "you": GREEN, "system": TEXT_DIM, "action": AMBER}
        color = COLOR.get(role, TEXT_DIM)

        row = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        row.pack(fill="x", pady=(8, 2))

        ctk.CTkLabel(
            row, text=speaker.upper(), font=("Segoe UI", 10, "bold"), text_color=color
        ).pack(anchor="w", padx=8)

        msg_lbl = ctk.CTkLabel(
            row, text=clean, font=("Segoe UI", 13),
            text_color=TEXT_PRI, wraplength=340, justify="left", anchor="w"
        )
        msg_lbl.pack(anchor="w", padx=8, pady=(2, 0))

        # Click to copy
        msg_lbl.bind("<Button-1>", lambda _: self._copy(clean))
        msg_lbl.configure(cursor="hand2")

        # Auto-scroll
        self.chat_frame._parent_canvas.yview_moveto(1.0)
        return msg_lbl

    def add_system(self, text: str):
        self.add_message("System", text, "system")

    # ── Token streaming ───────────────────────────────────────────────────────

    def start_stream(self):
        """Create a new streaming label for the current Son response."""
        self._stream_buf   = ""
        self._stream_label = self.add_message("SON", "…", "zee")

    def append_token(self, token: str):
        """Append a token to the live streaming label."""
        if self._stream_label is None:
            self.start_stream()
        self._stream_buf += token
        # Strip action tags from display
        import re
        display = re.sub(r"\[.*?\]", "", self._stream_buf).strip() or "…"
        self._stream_label.configure(text=display)
        self.chat_frame._parent_canvas.yview_moveto(1.0)

    def end_stream(self):
        self._stream_label = None
        self._stream_buf   = ""

    # ── Thread-safe wrappers ──────────────────────────────────────────────────

    def safe_set_state(self, s):         self.after(0, self.set_state, s)
    def safe_add_message(self, sp, t, r="zee"):
        self.after(0, self.add_message, sp, t, r)
    def safe_add_system(self, t):        self.after(0, self.add_system, t)
    def safe_start_stream(self):         self.after(0, self.start_stream)
    def safe_append_token(self, tok):    self.after(0, self.append_token, tok)
    def safe_end_stream(self):           self.after(0, self.end_stream)
    
    def safe_animate_mic(self, rms: float):
        self.after(0, self.animate_mic, rms)

    def animate_mic(self, rms: float):
        if self._state != "Listening":
            return
        
        # Base state
        size = 16
        color = TEAL_DIM
        
        # Pulse based on RMS volume severity
        if rms > 2000:
            size = 32
            color = TEAL
        elif rms > 1000:
            size = 26
            color = TEAL
        elif rms > 400:
            size = 20
            color = TEAL_DIM

        self.mic_lbl.configure(
            font=("Segoe UI", size), 
            text_color=color,
            fg_color="transparent"
        )

    def safe_add_action(self, tag: str, detail, show: bool = True):
        """Format and show an action line in the chat."""
        if not show:
            # Just show the icon badge, no content
            self.after(0, self.add_message, f"⚙ {tag}", "", "action")
            return

        clean_detail = detail
        if isinstance(detail, dict):
            if len(detail) == 1:
                clean_detail = list(detail.values())[0]
            else:
                clean_detail = str(detail)

        self.after(0, self.add_message, f"⚙ {tag}", str(clean_detail), "action")

    # ── Image Attachment ──────────────────────────────────────────────────────

    def _select_image(self):
        """Open file dialog to pick an image."""
        path = filedialog.askopenfilename(
            title="Attach Image for Son",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp *.bmp")]
        )
        if not path:
            return

        try:
            with open(path, "rb") as f:
                data = f.read()
                self._attached_image_b64 = base64.b64encode(data).decode("utf-8")
                self._attached_image_name = os.path.basename(path)
                
            # Update UI badge
            name = self._attached_image_name
            if len(name) > 12:
                name = name[:10] + "…"
            self.image_badge.configure(text=f" 📎 {name} ")
            self.image_badge.pack(side="left", padx=(0, 10))
            self.image_btn.configure(text_color=AMBER)
        except Exception as e:
            self.safe_add_system(f"❌ Failed to load image: {e}")

    def _clear_image(self):
        """Reset the attachment state."""
        self._attached_image_b64 = None
        self._attached_image_name = None
        self.image_badge.pack_forget()
        self.image_btn.configure(text_color=TEXT_DIM)

    # ── Clipboard ─────────────────────────────────────────────────────────────

    def _copy(self, text: str):
        """Native Tkinter clipboard copy."""
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update() # ensure it persists
            self.safe_add_system("✓ Copied to clipboard.")
        except Exception as e:
            self.safe_add_system(f"❌ Copy failed: {e}")

    # ── Input ─────────────────────────────────────────────────────────────────

    def _on_enter(self, _event):
        text = self.input_box.get().strip()
        if not text and not self._attached_image_b64:
            return
            
        img = self._attached_image_b64
        self.input_box.delete(0, "end")
        self.add_message("YOU", text, "you")
        
        if self.on_text_submit:
            threading.Thread(
                target=self.on_text_submit,
                args=(text, self.screen_mode, img),
                daemon=True
            ).start()
        
        self._clear_image()


    # ── Vision flash ──────────────────────────────────────────────────────────

    def trigger_vision_flash(self):
        flash = ctk.CTkToplevel(self)
        flash.attributes("-fullscreen", True)
        flash.attributes("-topmost", True)
        flash.configure(fg_color="white")
        flash.attributes("-alpha", 0.75)

        def _fade(a):
            if a <= 0:
                flash.destroy()
                return
            flash.attributes("-alpha", a)
            self.after(28, _fade, round(a - 0.06, 2))

        _fade(0.75)

    # ── Animation ─────────────────────────────────────────────────────────────

    def _animate(self):
        self.canvas.delete("all")
        cx, cy = 90, 90

        COLOR_MAP = {
            "Idle":      TEXT_DIM,
            "Listening": GREEN,
            "Thinking":  TEAL,
            "Speaking":  MAGENTA,
            "Streaming": AMBER,
        }
        color = COLOR_MAP.get(self._state, TEXT_DIM)
        speed = 4 if self._state == "Idle" else 7

        self._angle = (self._angle + speed) % 360

        # Pulsing outer ring
        self._pulse  += 0.4 * self._pulse_dir
        if self._pulse > 75 or self._pulse < 62:
            self._pulse_dir *= -1
        r = self._pulse

        self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            outline=color, width=1, dash=(12, 8)
        )

        # Three rotating arcs
        for i in range(3):
            start = (self._angle + i * 120) % 360
            self.canvas.create_arc(
                cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8,
                start=start, extent=60,
                outline=color, width=3, style="arc"
            )

        # Inner gear
        self.canvas.create_oval(
            cx - 22, cy - 22, cx + 22, cy + 22,
            outline=color, width=2
        )
        for i in range(8):
            a = math.radians(i * 45 + self._angle * 0.6)
            self.canvas.create_line(
                cx + math.cos(a) * 14, cy + math.sin(a) * 14,
                cx + math.cos(a) * 26, cy + math.sin(a) * 26,
                fill=color, width=3
            )

        self.after(30, self._animate)
