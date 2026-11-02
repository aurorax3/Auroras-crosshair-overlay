#!/usr/bin/env python3
"""
Aurora Crosshair Controller - GUI for AuroraCrosshairDX overlay
Allows control of crosshair scale and selection with organized tabs
"""

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont
import os
import subprocess
import time
from pathlib import Path
import psutil
from PIL import Image, ImageTk
import logging
import sys

# Also support importlib-based launchers without changing their sys.path.
GUI_DIR = Path(__file__).resolve().parent
if str(GUI_DIR) not in sys.path:
    sys.path.insert(0, str(GUI_DIR))
from overlay_config import Settings, read_settings, valid_crosshair, valid_scale, write_settings

LOGGER = logging.getLogger(__name__)

# UI colors only: PNG pixels and their existing thumbnail conversion stay intact.
BACKGROUND = "#111111"
PANEL = "#1b1b1b"
TEXT = "#eeeeee"
MUTED = "#aaaaaa"
BORDER = "#555555"
PREVIEW_BACKGROUND = "#e0e0e0"
PREVIEW_SELECTED = "#ffffff"
PREVIEW_TEXT = "#111111"

class CrosshairController:
    def __init__(self, root):
        self.root = root
        self.root.title("Aurora Crosshair Controller")
        self.root.geometry("1000x700")
        self.root.resizable(False, False)
        
        # Keep the legacy config location unless explicitly overridden.
        base = os.environ.get("AURORA_OVERLAY_HOME")
        self.overlay_home = Path(base) if base else Path.home() / "Documents" / "Crosshair overlay"
        self.config_path = self.overlay_home / "overlay_config.txt"
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        project = GUI_DIR.parent
        resource_candidates = (self.overlay_home / "AuroraCrosshairDX/resources/crosshairs",
                               project / "AuroraCrosshairDX/resources/crosshairs")
        self.resource_path = next((path for path in resource_candidates if path.is_dir()), resource_candidates[0])
        self._exe_candidates = (self.overlay_home / "AuroraCrosshairDX/x64/Release/AuroraCrosshairDX.exe",
                                self.overlay_home / "x64/Release/AuroraCrosshairDX.exe",
                                project / "AuroraCrosshairDX/x64/Release/AuroraCrosshairDX.exe",
                                project / "x64/Release/AuroraCrosshairDX.exe")
        self.overlay_exe = next((path for path in self._exe_candidates if path.is_file()), self._exe_candidates[0])
        try:
            settings = read_settings(self.config_path)
        except (OSError, UnicodeError) as error:
            LOGGER.warning("Cannot read overlay configuration: %s", error)
            settings = Settings()
        self._saved_settings = settings if self.config_path.exists() else None
        self._save_after_id = None
        self._last_config_error = None
        self._closed = False
        self.overlay_running = False
        self._owned_process = None
        self._attached_process = None
        self._process_after_id = None
        self._process_action = None
        self.current_scale = settings.scale
        self.current_folder, _, self.current_crosshair = settings.crosshair.rpartition("/")

        # Store references to buttons for easy selection tracking
        self.crosshair_buttons = {}
        self.selected_button = None
        
        self.setup_ui()
        self.check_overlay_status()
        self.load_crosshairs()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def setup_theme(self):
        """Apply a static terminal-like palette without native-theme color accents."""
        family = tkfont.nametofont("TkFixedFont", root=self.root).actual("family")
        self.ui_font = (family, 10)
        self.title_font = (family, 14, "bold")
        self.preview_font = (family, 8)
        self.root.configure(background=BACKGROUND)
        self.style = ttk.Style(self.root)
        # Clam honors explicit colors on Windows as well as X11.
        self.style.theme_use("clam")
        self.style.configure(".", background=BACKGROUND, foreground=TEXT,
                             font=self.ui_font, bordercolor=BORDER,
                             lightcolor=BORDER, darkcolor=BORDER,
                             focuscolor=TEXT, troughcolor=PANEL)
        self.style.configure("TFrame", background=BACKGROUND)
        self.style.configure("TLabel", background=BACKGROUND, foreground=TEXT)
        self.style.configure("TLabelframe", background=BACKGROUND, bordercolor=BORDER,
                             relief="solid", borderwidth=1)
        self.style.configure("TLabelframe.Label", background=BACKGROUND, foreground=MUTED)
        self.style.configure("TButton", background=PANEL, foreground=TEXT,
                             padding=(12, 7), relief="solid", borderwidth=1)
        self.style.map("TButton", background=[("pressed", TEXT), ("active", "#333333")],
                       foreground=[("disabled", BORDER), ("pressed", BACKGROUND), ("active", TEXT)],
                       bordercolor=[("focus", TEXT), ("active", TEXT)])
        self.style.configure("TNotebook", background=BACKGROUND, borderwidth=0,
                             tabmargins=(0, 0, 0, 0))
        self.style.configure("TNotebook.Tab", background=PANEL, foreground=MUTED,
                             padding=(12, 7), borderwidth=1)
        self.style.map("TNotebook.Tab", background=[("selected", TEXT), ("active", "#333333")],
                       foreground=[("selected", BACKGROUND), ("active", TEXT)],
                       lightcolor=[("selected", TEXT)], darkcolor=[("selected", TEXT)],
                       focuscolor=[("selected", BACKGROUND), ("!selected", TEXT)])
        self.style.configure("Horizontal.TScale", background=TEXT, troughcolor=PANEL,
                             bordercolor=BORDER, lightcolor=TEXT, darkcolor=TEXT)
        self.style.map("Horizontal.TScale", background=[("active", "#ffffff")])
        self.style.configure("Vertical.TScrollbar", background=BORDER, troughcolor=PANEL,
                             arrowcolor=TEXT, arrowsize=12, borderwidth=0)
        self.style.map("Vertical.TScrollbar", background=[("pressed", TEXT), ("active", MUTED)],
                       arrowcolor=[("pressed", BACKGROUND), ("active", BACKGROUND)])

    def setup_ui(self):
        self.setup_theme()
        # Title
        title_frame = ttk.Frame(self.root)
        title_frame.pack(fill=tk.X, padx=16, pady=(16, 10))
        
        title = ttk.Label(title_frame, text="AURORA // CROSSHAIR", font=self.title_font)
        title.pack(side=tk.LEFT)
        ttk.Label(title_frame, text="CONTROLLER", foreground=MUTED).pack(side=tk.RIGHT)
        
        # Status frame
        status_frame = ttk.LabelFrame(self.root, text=" [ 01 / OVERLAY ] ", padding=10)
        status_frame.pack(fill=tk.X, padx=16, pady=5)
        
        self.status_label = ttk.Label(status_frame, text="Overlay: Not running", foreground=TEXT)
        self.status_label.pack(anchor=tk.W)
        
        # Scale frame
        scale_frame = ttk.LabelFrame(self.root, text=" [ 02 / SCALE ] ", padding=10)
        scale_frame.pack(fill=tk.X, padx=16, pady=5)
        
        slider_frame = ttk.Frame(scale_frame)
        slider_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(slider_frame, text="50%").pack(side=tk.LEFT)
        
        self.scale_var = tk.DoubleVar(value=self.current_scale)
        self.scale_slider = ttk.Scale(
            slider_frame,
            from_=0.5,
            to=3.0,
            orient=tk.HORIZONTAL,
            variable=self.scale_var,
            command=self.on_scale_changed
        )
        self.scale_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.scale_slider.bind("<ButtonRelease-1>", lambda event: self.save_config())
        
        ttk.Label(slider_frame, text="300%").pack(side=tk.LEFT)
        
        self.scale_label = ttk.Label(scale_frame, text=f"Scale: {int(self.current_scale * 100)}%",
                                     font=(self.ui_font[0], 10, "bold"))
        self.scale_label.pack(anchor=tk.W)
        
        # Crosshair selection frame with tabs
        crosshair_frame = ttk.LabelFrame(self.root, text=" [ 03 / CROSSHAIRS ] ", padding=8)
        crosshair_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=5)
        
        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(crosshair_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Placeholder - will be populated by load_crosshairs()
        self.tabs = {}
        
        # Buttons frame
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=11, pady=(10, 16))
        
        start_btn = ttk.Button(button_frame, text="[ START OVERLAY ]", command=self.start_overlay)
        start_btn.pack(side=tk.LEFT, padx=5)
        
        stop_btn = ttk.Button(button_frame, text="[ STOP OVERLAY ]", command=self.stop_overlay)
        stop_btn.pack(side=tk.LEFT, padx=5)
        
        refresh_btn = ttk.Button(button_frame, text="[ REFRESH STATUS ]", command=self.check_overlay_status)
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
    def load_crosshairs(self):
        """Index resource names once; decode previews only for a visited tab."""
        self._category_files = {}
        self._loaded_categories = set()
        self._category_canvases = {}
        self._thumbnail_errors = 0
        if not self.resource_path.is_dir():
            self.status_label.config(text=f"Crosshairs folder not found: {self.resource_path}", foreground=TEXT)
            return
        for folder in sorted(self.resource_path.iterdir()):
            if folder.is_dir():
                self._category_files[folder.name] = sorted(path for path in folder.rglob("*")
                                                         if path.is_file() and path.suffix.lower() == ".png")
        root_images = sorted(path for path in self.resource_path.iterdir()
                             if path.is_file() and path.suffix.lower() == ".png")
        if root_images:
            self._category_files[""] = root_images
        for category in self._category_files:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=category.upper() or "ROOT")
            self.tabs[category] = frame
        if not self.tabs:
            self.status_label.config(text="No crosshair categories found", foreground=TEXT)
            return
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        category = self.current_folder.split("/", 1)[0]
        if category not in self.tabs:
            category = "dots" if "dots" in self.tabs else next(iter(self.tabs))
        self.notebook.select(self.tabs[category])
        self._load_category(category)

    def _on_tab_changed(self, event=None):
        selected = self.notebook.select()
        for category, frame in self.tabs.items():
            if str(frame) == selected:
                self._load_category(category)
                return

    def _load_category(self, category):
        if category in self._loaded_categories:
            return
        self._loaded_categories.add(category)
        frame = self.tabs[category]
        canvas = tk.Canvas(frame, bg=BACKGROUND, highlightthickness=0)
        self._category_canvases[category] = canvas
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        content = ttk.Frame(canvas)
        content.images = []
        window = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        # Bind each callback to its own widgets; never recursively pump Tk here.
        content.bind("<Configure>", lambda event, c=canvas: c.configure(scrollregion=c.bbox("all")))
        canvas.bind("<Configure>", lambda event, c=canvas, w=window: c.itemconfigure(w, width=event.width))

        def on_mousewheel(event, c=canvas):
            units = int(-event.delta / 120) if event.delta else (1 if event.num == 5 else -1)
            c.yview_scroll(units, "units")

        for widget in (canvas, content):
            widget.bind("<MouseWheel>", on_mousewheel)
            widget.bind("<Button-4>", on_mousewheel)
            widget.bind("<Button-5>", on_mousewheel)
        for column in range(10):
            content.grid_columnconfigure(column, weight=1)
        for index, path in enumerate(self._category_files[category]):
            relative = path.relative_to(self.resource_path).as_posix()
            if valid_crosshair(relative) is None:
                LOGGER.warning("Ignoring unsupported crosshair filename: %s", relative)
                continue
            folder, _, name = relative.rpartition("/")
            photo = None
            try:
                with Image.open(path) as image:
                    image.thumbnail((64, 64), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(image, master=self.root)
                content.images.append(photo)
            except (OSError, ValueError, tk.TclError) as error:
                self._thumbnail_errors += 1
                if self._thumbnail_errors <= 5:
                    LOGGER.warning("Cannot preview %s: %s", relative, error)
                elif self._thumbnail_errors == 6:
                    LOGGER.warning("Further thumbnail errors suppressed")
            button = tk.Button(content, image=photo or "", text=name.rsplit(".", 1)[0],
                               compound="top", command=lambda ch=name, fn=folder: self.select_crosshair(ch, fn),
                               relief=tk.FLAT, bg=PREVIEW_BACKGROUND, fg=PREVIEW_TEXT,
                               activebackground="#b0b0b0", activeforeground=PREVIEW_TEXT,
                               highlightbackground=BORDER, highlightcolor=PREVIEW_TEXT,
                               padx=8, pady=8, width=85 if photo else 12,
                               wraplength=85, font=self.preview_font)
            button.grid(row=index // 10, column=index % 10, padx=3, pady=3, sticky="nsew")
            for event in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                button.bind(event, on_mousewheel)
            self.crosshair_buttons[relative] = button
            if relative == self._current_settings().crosshair:
                self.selected_button = button
                button.config(bg=PREVIEW_SELECTED, fg=PREVIEW_TEXT, relief=tk.SOLID)
        if not self._category_files[category]:
            ttk.Label(content, text=f"No crosshairs in {category}").grid()
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _current_settings(self):
        crosshair = "/".join(part for part in (self.current_folder, self.current_crosshair) if part)
        return Settings(self.current_scale, crosshair)

    def select_crosshair(self, crosshair, folder):
        """Handle a safe resource-relative crosshair selection."""
        key = "/".join(part for part in (folder, crosshair) if part)
        if valid_crosshair(key) is None:
            return
        # Deselect previous button
        if self.selected_button:
            self.selected_button.config(bg=PREVIEW_BACKGROUND, fg=PREVIEW_TEXT, relief=tk.FLAT)
        
        # Select new button
        key = "/".join(part for part in (folder, crosshair) if part)
        if key in self.crosshair_buttons:
            self.selected_button = self.crosshair_buttons[key]
            self.selected_button.config(bg=PREVIEW_SELECTED, fg=PREVIEW_TEXT, relief=tk.SOLID)
        
        self.current_crosshair = crosshair
        self.current_folder = folder
        self.save_config()
        
    def on_scale_changed(self, value):
        """Coalesce a drag to at most one config publication per 50 milliseconds."""
        scale = valid_scale(value)
        if scale is None:
            return
        self.current_scale = scale
        self.scale_label.config(text=f"Scale: {int(self.current_scale * 100)}%")
        if self._save_after_id is None:
            self._save_after_id = self.root.after(50, self._flush_pending_config)

    def _flush_pending_config(self):
        self._save_after_id = None
        self.save_config()

    def save_config(self):
        """Publish one complete change; unchanged state causes no disk operation."""
        if self._save_after_id is not None:
            self.root.after_cancel(self._save_after_id)
            self._save_after_id = None
        settings = self._current_settings()
        if settings == self._saved_settings:
            return True
        try:
            write_settings(self.config_path, settings)
        except (OSError, ValueError) as error:
            message = f"Could not save settings: {error}"
            self.status_label.config(text=message, foreground=TEXT)
            if message != self._last_config_error:
                LOGGER.warning("%s", message)
            self._last_config_error = message
            return False
        self._saved_settings = settings
        self._last_config_error = None
        return True

    def on_close(self):
        """Flush final settings and close the controller, leaving the overlay alive."""
        if not self.save_config():
            if not messagebox.askyesno("Settings not saved", "The final settings could not be saved. Close without saving?", parent=self.root):
                return
        self._closed = True
        if self._process_after_id is not None:
            self.root.after_cancel(self._process_after_id)
            self._process_after_id = None
        self.root.destroy()

    def _is_expected_executable(self, filename):
        if not filename:
            return False
        normalized = os.path.normcase(str(Path(filename).resolve()))
        return any(normalized == os.path.normcase(str(path.resolve()))
                   for path in (*self._exe_candidates, self.overlay_exe))

    @staticmethod
    def _process_alive(process):
        poll = getattr(process, "poll", None)
        if poll is not None:
            return poll() is None
        try:
            return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def _find_overlay_process(self):
        # An owned Popen retains the real process handle, avoiding PID reuse races.
        if self._owned_process is not None and self._process_alive(self._owned_process):
            return self._owned_process
        self._owned_process = None
        if self._attached_process is not None:
            try:
                if self._process_alive(self._attached_process) and self._is_expected_executable(self._attached_process.exe()):
                    return self._attached_process
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                pass
            self._attached_process = None
        # Attach only on an explicit status/start/stop action, never on an idle timer.
        for process in psutil.process_iter(["name", "exe"]):
            try:
                if ((process.info.get("name") or "").lower() == "auroracrosshairdx.exe"
                        and self._is_expected_executable(process.info.get("exe"))
                        and self._process_alive(process)):
                    self._attached_process = process
                    return process
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                continue
        return None

    def check_overlay_status(self):
        try:
            process = self._find_overlay_process()
            self.overlay_running = process is not None
            self.status_label.config(text="Overlay: Running" if process else "Overlay: Not running",
                                     foreground=TEXT)
            return process
        except (psutil.Error, OSError) as error:
            self.status_label.config(text=f"Cannot check overlay status: {error}", foreground=TEXT)
            LOGGER.warning("Cannot check overlay status: %s", error)
            return None

    def start_overlay(self):
        if self._process_action is not None:
            return
        if self.check_overlay_status() is not None:
            return
        if not self.overlay_exe.is_file():
            messagebox.showerror("Overlay not found", f"Build the overlay first. Expected executable:\n{self.overlay_exe}")
            return
        if not self.save_config():
            return
        try:
            self._owned_process = subprocess.Popen([str(self.overlay_exe)])
        except OSError as error:
            self.status_label.config(text=f"Cannot start overlay: {error}", foreground=TEXT)
            LOGGER.warning("Cannot start overlay: %s", error)
            return
        self._process_action = "starting"
        self.status_label.config(text="Overlay: Starting", foreground=TEXT)
        self._process_after_id = self.root.after(150, self._finish_start)

    def _finish_start(self):
        self._process_after_id = None
        self._process_action = None
        if self._owned_process is not None and self._process_alive(self._owned_process):
            self.overlay_running = True
            self.status_label.config(text="Overlay: Running", foreground=TEXT)
        else:
            self.overlay_running = False
            self.status_label.config(text="Overlay exited during startup", foreground=TEXT)
            LOGGER.warning("Overlay exited during startup")

    @staticmethod
    def _request_window_close(pid):
        """Request normal WM_CLOSE only for the selected overlay's own window."""
        if os.name != "nt":
            return False
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.PostMessageW.restype = wintypes.BOOL
        window = user32.FindWindowW("AuroraCrosshair", None)
        owner = wintypes.DWORD()
        if window:
            user32.GetWindowThreadProcessId(window, ctypes.byref(owner))
            if owner.value == pid:
                return bool(user32.PostMessageW(window, 0x0010, 0, 0))  # WM_CLOSE
        return False

    def stop_overlay(self):
        if self._process_action is not None:
            return
        process = self.check_overlay_status()
        if process is None:
            return
        try:
            graceful = self._request_window_close(process.pid)
            if not graceful:
                process.terminate()
        except (psutil.NoSuchProcess, ProcessLookupError):
            self.check_overlay_status()
            return
        except (psutil.Error, OSError) as error:
            self.status_label.config(text=f"Cannot stop overlay: {error}", foreground=TEXT)
            LOGGER.warning("Cannot stop overlay: %s", error)
            return
        self._process_action = "stopping"
        self._stopping_process = process
        self._stop_stage = "closing" if graceful else "terminating"
        self._stop_deadline = time.monotonic() + (2.0 if graceful else 1.0)
        self.status_label.config(text="Overlay: Stopping", foreground=TEXT)
        self._process_after_id = self.root.after(50, self._poll_stop)

    def _poll_stop(self):
        self._process_after_id = None
        process = self._stopping_process
        if not self._process_alive(process):
            self._process_action = None
            self._stopping_process = None
            self.overlay_running = False
            self._owned_process = None
            self._attached_process = None
            self.status_label.config(text="Overlay: Stopped", foreground=TEXT)
            return
        if time.monotonic() >= self._stop_deadline:
            try:
                if self._stop_stage == "closing":
                    process.terminate()
                    self._stop_stage = "terminating"
                elif self._stop_stage == "terminating":
                    process.kill()
                    self._stop_stage = "killing"
                else:
                    self._process_action = None
                    self.status_label.config(text="Overlay did not stop; check its process", foreground=TEXT)
                    LOGGER.warning("Overlay did not stop after a bounded shutdown attempt")
                    return
            except (psutil.NoSuchProcess, ProcessLookupError):
                pass
            except (psutil.Error, OSError) as error:
                self._process_action = None
                self.status_label.config(text=f"Cannot stop overlay: {error}", foreground=TEXT)
                LOGGER.warning("Cannot stop overlay: %s", error)
                return
            self._stop_deadline = time.monotonic() + 1.0
        self._process_after_id = self.root.after(50, self._poll_stop)

def main():
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    root = tk.Tk()
    try:
        app = CrosshairController(root)
    except (OSError, ValueError) as error:
        LOGGER.error("Controller initialization failed: %s", error)
        messagebox.showerror("Cannot initialize controller", str(error), parent=root)
        root.destroy()
        return 1
    root.mainloop()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

