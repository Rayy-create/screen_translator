import os
import re
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import mss
    import pytesseract
    from PIL import Image, ImageOps, ImageFilter
    from deep_translator import GoogleTranslator
except ImportError as e:
    missing = str(e).split("'")[1] if "'" in str(e) else str(e)
    raise SystemExit(
        f"Library '{missing}' belum terinstall.\n"
        f"Jalankan dulu di Command Prompt:\n"
        f"pip install mss pytesseract pillow deep-translator"
    )

# ============================================================
# JIKA Tesseract TIDAK terdeteksi otomatis, isi path-nya di sini:
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# ============================================================
if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# --- Palet warna tema gelap ---
BG_DARK = "#1e1e2e"
BG_PANEL = "#262638"
ACCENT = "#89b4fa"
ACCENT_GREEN = "#a6e3a1"
TEXT_LIGHT = "#cdd6f4"
TEXT_MUTED = "#8a8fa8"
DANGER = "#f38ba8"

# Nama tampilan -> (kode Google Translate, kode bahasa Tesseract)
LANG_MAP = {
    "Inggris (English)":            ("en",    "eng"),
    "Indonesia":                    ("id",    "ind"),
    "Jepang (Japanese)":            ("ja",    "jpn"),
    "Korea":                        ("ko",    "kor"),
    "Mandarin Sederhana":           ("zh-CN", "chi_sim"),
    "Mandarin Tradisional":         ("zh-TW", "chi_tra"),
    "Arab":                         ("ar",    "ara"),
    "Prancis (French)":             ("fr",    "fra"),
    "Jerman (German)":              ("de",    "deu"),
    "Spanyol (Spanish)":            ("es",    "spa"),
    "Rusia (Russian)":              ("ru",    "rus"),
    "Thailand":                     ("th",    "tha"),
    "Vietnam":                      ("vi",    "vie"),
}
SOURCE_OPTIONS = ["Deteksi Otomatis (huruf Latin saja)"] + list(LANG_MAP.keys())
TARGET_OPTIONS = list(LANG_MAP.keys())


def preprocess_image(img: Image.Image, scale: int = 2) -> Image.Image:
    """Perbesar & pertajam gambar supaya OCR lebih akurat."""
    gray = img.convert("L")
    w, h = gray.size
    gray = gray.resize((w * scale, h * scale), Image.LANCZOS)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = gray.filter(ImageFilter.SHARPEN)
    return gray


def clean_ocr_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


class RegionSelector:
    """Jendela transparan untuk memilih area layar dengan cara di-drag."""

    def __init__(self, root, callback):
        self.callback = callback
        self.top = tk.Toplevel(root)
        self.top.attributes("-fullscreen", True)
        self.top.attributes("-alpha", 0.3)
        self.top.attributes("-topmost", True)
        self.top.configure(bg="gray")
        self.top.config(cursor="cross")

        self.canvas = tk.Canvas(self.top, bg="gray", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.start_x = None
        self.start_y = None
        self.rect = None

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.top.bind("<Escape>", lambda e: self.top.destroy())

        info = tk.Label(
            self.top,
            text="Drag untuk memilih area layar yang ingin diterjemahkan  |  ESC untuk batal",
            bg=ACCENT_GREEN,
            fg="black",
            font=("Segoe UI", 11, "bold"),
            padx=10, pady=6,
        )
        info.place(relx=0.5, y=20, anchor="n")

    def on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline=ACCENT_GREEN, width=3
        )

    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
        self.top.destroy()
        if x2 - x1 > 5 and y2 - y1 > 5:
            self.callback({"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1})


class ScreenTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Screen Translator Otomatis")
        self.root.geometry("460x420")
        self.root.configure(bg=BG_DARK)
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)

        self.region = None
        self.running = False
        self.worker_thread = None
        self.last_text = ""

        self._setup_style()
        self._build_control_panel()
        self._build_overlay()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- UI setup ----------
    def _setup_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure("TFrame", background=BG_DARK)
        style.configure("Panel.TFrame", background=BG_PANEL)
        style.configure("TLabel", background=BG_DARK, foreground=TEXT_LIGHT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG_DARK, foreground=TEXT_LIGHT,
                         font=("Segoe UI", 16, "bold"))
        style.configure("Muted.TLabel", background=BG_DARK, foreground=TEXT_MUTED, font=("Segoe UI", 9))
        style.configure("Status.TLabel", background=BG_DARK, font=("Segoe UI", 10, "bold"))

        style.configure("Accent.TButton", background=ACCENT, foreground="#1e1e2e",
                         font=("Segoe UI", 10, "bold"), padding=8, borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#a6c8ff"), ("disabled", "#3a3a4d")])

        style.configure("Stop.TButton", background=DANGER, foreground="#1e1e2e",
                         font=("Segoe UI", 10, "bold"), padding=8, borderwidth=0)
        style.map("Stop.TButton", background=[("active", "#f5a3bc"), ("disabled", "#3a3a4d")])

        style.configure("TCombobox", fieldbackground=BG_PANEL, background=BG_PANEL,
                         foreground=TEXT_LIGHT, arrowcolor=TEXT_LIGHT)
        style.configure("TEntry", fieldbackground=BG_PANEL, foreground=TEXT_LIGHT)

    def _build_control_panel(self):
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="🔤  Screen Translator", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Otomatis membaca & menerjemahkan teks di layar — terus-menerus.",
                  style="Muted.TLabel", wraplength=420).pack(anchor="w", pady=(2, 14))

        self.status_label = ttk.Label(frame, text="●  Area layar belum dipilih",
                                       style="Status.TLabel", foreground=DANGER)
        self.status_label.pack(anchor="w", pady=(0, 12))

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill="x", pady=(0, 16))
        ttk.Button(btn_row, text="📐 Pilih Area Layar", style="Accent.TButton",
                   command=self.select_region).pack(side="left", padx=(0, 8))
        self.start_btn = ttk.Button(btn_row, text="▶ Mulai", style="Accent.TButton",
                                     command=self.start, state="disabled")
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = ttk.Button(btn_row, text="⏹ Stop", style="Stop.TButton",
                                    command=self.stop, state="disabled")
        self.stop_btn.pack(side="left")

        opt_panel = ttk.Frame(frame, style="Panel.TFrame", padding=14)
        opt_panel.pack(fill="x")

        ttk.Label(opt_panel, text="Bahasa sumber (di layar)", background=BG_PANEL,
                  foreground=TEXT_MUTED, font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        self.src_lang = tk.StringVar(value=SOURCE_OPTIONS[0])
        src_combo = ttk.Combobox(opt_panel, textvariable=self.src_lang, values=SOURCE_OPTIONS,
                                  state="readonly", width=28)
        src_combo.grid(row=1, column=0, sticky="w", pady=(2, 10))

        ttk.Label(opt_panel, text="Terjemahkan ke", background=BG_PANEL,
                  foreground=TEXT_MUTED, font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w")
        self.dst_lang = tk.StringVar(value="Indonesia")
        dst_combo = ttk.Combobox(opt_panel, textvariable=self.dst_lang, values=TARGET_OPTIONS,
                                  state="readonly", width=28)
        dst_combo.grid(row=3, column=0, sticky="w", pady=(2, 10))

        ttk.Label(opt_panel, text="Interval pembaruan (detik)", background=BG_PANEL,
                  foreground=TEXT_MUTED, font=("Segoe UI", 9)).grid(row=4, column=0, sticky="w")
        self.interval = tk.StringVar(value="3")
        ttk.Entry(opt_panel, textvariable=self.interval, width=8).grid(row=5, column=0, sticky="w", pady=(2, 0))

        ttk.Label(frame,
                  text="Tips: pilih bahasa sumber yang sesuai teksnya, dan area seketat mungkin\n"
                       "supaya OCR lebih akurat.",
                  style="Muted.TLabel", wraplength=420, justify="left").pack(anchor="w", pady=(12, 0))

    def _build_overlay(self):
        self.overlay = tk.Toplevel(self.root)
        self.overlay.title("Hasil Terjemahan")
        self.overlay.geometry("520x180+100+100")
        self.overlay.attributes("-topmost", True)
        self.overlay.configure(bg=BG_DARK)

        header = tk.Frame(self.overlay, bg=BG_PANEL, height=32)
        header.pack(fill="x")
        tk.Label(header, text="🌐  Terjemahan Otomatis", bg=BG_PANEL, fg=ACCENT,
                 font=("Segoe UI", 10, "bold"), pady=6).pack(side="left", padx=10)
        self.overlay_status = tk.Label(header, text="Berhenti", bg=BG_PANEL, fg=TEXT_MUTED,
                                        font=("Segoe UI", 9))
        self.overlay_status.pack(side="right", padx=10)

        self.overlay_text = tk.Text(self.overlay, wrap="word", font=("Segoe UI", 14),
                                     bg=BG_DARK, fg=TEXT_LIGHT, padx=14, pady=12,
                                     borderwidth=0, highlightthickness=0)
        self.overlay_text.pack(fill="both", expand=True)
        self.overlay_text.insert("1.0", "Hasil terjemahan akan muncul di sini secara otomatis...")
        self.overlay_text.configure(state="disabled")

    # ---------- Logika ----------
    def select_region(self):
        self.root.withdraw()
        self.root.after(200, lambda: RegionSelector(self.root, self.on_region_selected))

    def on_region_selected(self, region):
        self.root.deiconify()
        self.region = region
        self.status_label.config(text=f"●  Area dipilih ({region['width']}×{region['height']}px)",
                                  foreground=ACCENT_GREEN)
        self.start_btn.config(state="normal")

    def start(self):
        if not self.region:
            messagebox.showwarning("Belum ada area", "Pilih area layar dulu.")
            return
        try:
            self.interval_val = max(1.0, float(self.interval.get()))
        except ValueError:
            self.interval_val = 3.0

        self.running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.overlay_status.config(text="● Berjalan", fg=ACCENT_GREEN)
        self.worker_thread = threading.Thread(target=self.loop_translate, daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.overlay_status.config(text="Berhenti", fg=TEXT_MUTED)

    def loop_translate(self):
        with mss.mss() as sct:
            while self.running:
                try:
                    src_choice = self.src_lang.get()
                    dst_choice = self.dst_lang.get()

                    if src_choice.startswith("Deteksi Otomatis"):
                        google_src, tess_lang = "auto", "eng"
                    else:
                        google_src, tess_lang = LANG_MAP[src_choice]

                    google_dst, _ = LANG_MAP.get(dst_choice, ("id", "ind"))

                    shot = sct.grab(self.region)
                    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                    processed = preprocess_image(img, scale=2)

                    raw_text = pytesseract.image_to_string(
                        processed, lang=tess_lang, config="--oem 3 --psm 6"
                    )
                    text = clean_ocr_text(raw_text)

                    if len(text) >= 2 and text != self.last_text:
                        self.last_text = text
                        translated = GoogleTranslator(source=google_src, target=google_dst).translate(text)
                        self.update_overlay(translated)
                except Exception as e:
                    self.update_overlay(f"[Error: {e}]")

                time.sleep(self.interval_val)

    def update_overlay(self, text):
        def _update():
            self.overlay_text.configure(state="normal")
            self.overlay_text.delete("1.0", "end")
            self.overlay_text.insert("1.0", text)
            self.overlay_text.configure(state="disabled")
        self.root.after(0, _update)

    def on_close(self):
        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenTranslatorApp(root)
    root.mainloop()
