#!/usr/bin/env python3
"""
Aurora Crosshair Controller - GUI for AuroraCrosshairDX overlay
Allows control of crosshair scale and selection with organized tabs
"""

import tkinter as tk
from tkinter import ttk, messagebox
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
from overlay_config import Settings, read_settings, valid_scale, write_settings

LOGGER = logging.getLogger(__name__)

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
        self.resource_path = self.overlay_home / "AuroraCrosshairDX" / "resources" / "crosshairs"
        self.overlay_exe = self.overlay_home / "AuroraCrosshairDX" / "x64" / "Release" / "AuroraCrosshairDX.exe"
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
        self.current_scale = settings.scale
        self.current_folder, _, self.current_crosshair = settings.crosshair.rpartition("/")

        # Store references to buttons for easy selection tracking
        self.crosshair_buttons = {}
        self.selected_button = None
        
        self.setup_ui()
        self.check_overlay_status()
        self.load_crosshairs()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def setup_ui(self):
        # Title
        title_frame = ttk.Frame(self.root)
        title_frame.pack(fill=tk.X, padx=10, pady=10)
        
        title = ttk.Label(title_frame, text="Aurora Crosshair Controller", font=("Arial", 14, "bold"))
        title.pack()
        
        # Status frame
        status_frame = ttk.LabelFrame(self.root, text="Status", padding=10)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_label = ttk.Label(status_frame, text="Overlay: Not running", foreground="red")
        self.status_label.pack()
        
        # Scale frame
        scale_frame = ttk.LabelFrame(self.root, text="Crosshair Scale", padding=10)
        scale_frame.pack(fill=tk.X, padx=10, pady=5)
        
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
        
        self.scale_label = ttk.Label(scale_frame, text=f"Scale: {int(self.current_scale * 100)}%", font=("Arial", 10, "bold"))
        self.scale_label.pack()
        
        # Crosshair selection frame with tabs
        crosshair_frame = ttk.LabelFrame(self.root, text="Crosshair Selection", padding=5)
        crosshair_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(crosshair_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Placeholder - will be populated by load_crosshairs()
        self.tabs = {}
        
        # Buttons frame
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        start_btn = ttk.Button(button_frame, text="Start Overlay", command=self.start_overlay)
        start_btn.pack(side=tk.LEFT, padx=5)
        
        stop_btn = ttk.Button(button_frame, text="Stop Overlay", command=self.stop_overlay)
        stop_btn.pack(side=tk.LEFT, padx=5)
        
        refresh_btn = ttk.Button(button_frame, text="Refresh Status", command=self.check_overlay_status)
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
    def load_crosshairs(self):
        """Load crosshair folders as tabs with image thumbnails for each crosshair"""
        if not self.resource_path.exists():
            messagebox.showerror("Error", f"Crosshairs folder not found at:\n{self.resource_path}")
            return
        
        # Get all folders
        folders = sorted([f for f in self.resource_path.iterdir() if f.is_dir()])
        
        if not folders:
            messagebox.showerror("Error", "No crosshair folders found")
            return
        
        # Create tab for each folder
        for folder in folders:
            folder_name = folder.name
            
            # Create frame for this tab
            tab_frame = ttk.Frame(self.notebook)
            self.notebook.add(tab_frame, text=folder_name.capitalize())
            self.tabs[folder_name] = tab_frame
            
            # Get crosshairs in this folder
            crosshairs = sorted([f.name for f in folder.glob("*.png")])
            
            if not crosshairs:
                label = ttk.Label(tab_frame, text=f"No crosshairs in {folder_name}", font=("Arial", 10))
                label.pack(padx=10, pady=10)
                continue
            
            # Create a scrollable frame for buttons with images
            canvas = tk.Canvas(tab_frame, bg="white", highlightthickness=0)
            scrollbar = ttk.Scrollbar(tab_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            def on_frame_configure(event):
                # Update scroll region to actual content size
                canvas.update_idletasks()
                canvas.configure(scrollregion=canvas.bbox("all"))
                # Make scrollable frame width match canvas width
                canvas_width = canvas.winfo_width()
                if canvas_width > 1:
                    scrollable_frame.config(width=canvas_width)
            
            scrollable_frame.bind("<Configure>", on_frame_configure)
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Enable mouse wheel scrolling for this canvas
            def on_mousewheel(event, c=canvas):
                c.yview_scroll(int(-1*(event.delta/120)), "units")
            
            canvas.bind("<MouseWheel>", on_mousewheel)
            scrollable_frame.bind("<MouseWheel>", on_mousewheel)
            
            # Create grid layout for crosshairs (10 columns)
            grid_row = 0
            grid_col = 0
            columns = 10
            
            # Configure grid columns to expand equally
            for i in range(columns):
                scrollable_frame.grid_columnconfigure(i, weight=1)
            
            # Create button for each crosshair with image preview
            for crosshair in crosshairs:
                crosshair_path = folder / crosshair
                
                # Create frame for button content
                btn_frame = tk.Frame(scrollable_frame, bg="white", relief=tk.FLAT, bd=1)
                btn_frame.grid(row=grid_row, column=grid_col, padx=3, pady=3, sticky="nsew")
                
                # Try to load and display image thumbnail
                try:
                    img = Image.open(crosshair_path)
                    # Resize to thumbnail (64x64)
                    img.thumbnail((64, 64), Image.Resampling.LANCZOS)
                    
                    # Convert to PhotoImage
                    photo = ImageTk.PhotoImage(img)
                    
                    # Store reference to prevent garbage collection
                    if not hasattr(scrollable_frame, 'images'):
                        scrollable_frame.images = []
                    scrollable_frame.images.append(photo)
                    
                    # Create button with image
                    btn = tk.Button(
                        btn_frame,
                        image=photo,
                        text=crosshair.replace(".png", ""),
                        compound="top",
                        command=lambda ch=crosshair, fn=folder_name: self.select_crosshair(ch, fn),
                        relief=tk.FLAT,
                        bg="#e0e0e0",
                        activebackground="#b0b0b0",
                        padx=8,
                        pady=8,
                        width=14,
                        wraplength=85,
                        font=("Arial", 7)
                    )
                    btn.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
                    btn.bind("<MouseWheel>", on_mousewheel)
                    btn_frame.bind("<MouseWheel>", on_mousewheel)
                    
                except Exception as e:
                    # Fallback: text only button if image fails to load
                    btn = tk.Button(
                        btn_frame,
                        text=crosshair.replace(".png", ""),
                        command=lambda ch=crosshair, fn=folder_name: self.select_crosshair(ch, fn),
                        relief=tk.FLAT,
                        bg="#e0e0e0",
                        activebackground="#b0b0b0",
                        padx=8,
                        pady=8,
                        width=14,
                        wraplength=85,
                        font=("Arial", 7)
                    )
                    btn.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
                    btn.bind("<MouseWheel>", on_mousewheel)
                    btn_frame.bind("<MouseWheel>", on_mousewheel)
                
                # Store button reference
                key = f"{folder_name}/{crosshair}"
                self.crosshair_buttons[key] = btn
                
                # Update grid position
                grid_col += 1
                if grid_col >= columns:
                    grid_col = 0
                    grid_row += 1
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Make the canvas expand to fill available width
            tab_frame.pack_propagate(False)
            
            # Force update scroll region after all items loaded
            self.root.after(100, lambda: canvas.configure(scrollregion=canvas.bbox("all")))
        
        # Reopening the controller must not reset a running overlay's settings.
        key = self._current_settings().crosshair
        if key in self.crosshair_buttons:
            self.selected_button = self.crosshair_buttons[key]
            self.selected_button.config(bg="#4CAF50", fg="white")

    def _current_settings(self):
        crosshair = "/".join(part for part in (self.current_folder, self.current_crosshair) if part)
        return Settings(self.current_scale, crosshair)

    def select_crosshair(self, crosshair, folder):
        """Handle crosshair selection"""
        # Deselect previous button
        if self.selected_button:
            self.selected_button.config(bg="#e0e0e0", fg="black")
        
        # Select new button
        key = f"{folder}/{crosshair}"
        if key in self.crosshair_buttons:
            self.selected_button = self.crosshair_buttons[key]
            self.selected_button.config(bg="#4CAF50", fg="white")
        
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
            self.status_label.config(text=message, foreground="red")
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
            messagebox.showerror("Settings not saved", "Cannot save the final settings. Check the configuration folder and try again.")
            return
        self._closed = True
        self.root.destroy()

    def check_overlay_status(self):
        """Check if overlay process is running"""
        try:
            # Check if AuroraCrosshairDX.exe is running
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] == 'AuroraCrosshairDX.exe':
                    self.overlay_running = True
                    self.status_label.config(text="Overlay: Running", foreground="green")
                    return
            
            self.overlay_running = False
            self.status_label.config(text="Overlay: Not running", foreground="red")
        except Exception as e:
            self.status_label.config(text=f"Error checking status: {e}", foreground="orange")
            
    def start_overlay(self):
        """Start the overlay process"""
        if self.overlay_running:
            messagebox.showinfo("Info", "Overlay is already running")
            return
            
        if not self.overlay_exe.exists():
            messagebox.showerror("Error", f"Overlay executable not found at:\n{self.overlay_exe}")
            return
        
        try:
            # Save current config before starting
            if not self.save_config():
                return
            
            # Start overlay in background
            subprocess.Popen(str(self.overlay_exe))
            
            # Wait a moment and check status
            time.sleep(1)
            self.check_overlay_status()
            
            if self.overlay_running:
                messagebox.showinfo("Success", "Overlay started successfully!")
            else:
                messagebox.showerror("Error", "Failed to start overlay")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start overlay: {e}")
            
    def stop_overlay(self):
        """Stop the overlay process"""
        if not self.overlay_running:
            messagebox.showinfo("Info", "Overlay is not running")
            return
        
        try:
            # Kill AuroraCrosshairDX.exe process
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] == 'AuroraCrosshairDX.exe':
                    proc.terminate()
                    proc.wait(timeout=2)
                    break
            
            time.sleep(0.5)
            self.check_overlay_status()
            messagebox.showinfo("Success", "Overlay stopped!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to stop overlay: {e}")

def main():
    root = tk.Tk()
    app = CrosshairController(root)
    root.mainloop()

if __name__ == "__main__":
    main()

