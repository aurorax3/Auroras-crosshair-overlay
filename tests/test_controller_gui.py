"""Functional controller checks; run under Xvfb on Linux or a Windows desktop."""
import os
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from PIL import Image

GUI_DIR = Path(__file__).resolve().parents[1] / "CrosshairGUI"
sys.path.insert(0, str(GUI_DIR))
import gui
from overlay_config import Settings, read_settings, write_settings


class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            root = tk.Tk()
            root.destroy()
        except tk.TclError as error:
            raise unittest.SkipTest(f"A display is required: {error}")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.home = Path(self.temporary.name)
        self.base = self.home / "Documents/Crosshair overlay"
        self.resources = self.base / "AuroraCrosshairDX/resources/crosshairs"
        for relative in ("dots/osupink.png", "dots/other.png", "crosses/nested/reticle.png", "circles/ring.png"):
            path = self.resources / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGBA", (8, 8), (255, 128, 64, 200)).save(path)
        self.home_patch = patch.object(Path, "home", return_value=self.home)
        self.home_patch.start()
        self.env_patch = patch.dict(os.environ)
        self.env_patch.start()
        os.environ.pop("AURORA_OVERLAY_HOME", None)
        self.root = tk.Tk()
        self.errors = []
        self.root.report_callback_exception = lambda *error: self.errors.append(error)
        self.app = None

    def tearDown(self):
        if self.root.winfo_exists():
            for after in self.root.tk.call("after", "info"):
                self.root.after_cancel(after)
            self.root.destroy()
        self.env_patch.stop()
        self.home_patch.stop()
        self.temporary.cleanup()
        self.assertEqual(self.errors, [])

    def make_app(self):
        self.app = gui.CrosshairController(self.root)
        self.root.update()
        return self.app

    def pump(self, seconds=0.1):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.005)

    def test_categories_load_once_and_nested_paths_are_selectable(self):
        with patch.object(gui.Image, "open", wraps=Image.open) as decode:
            app = self.make_app()
            self.assertEqual(set(app.tabs), {"dots", "crosses", "circles"})
            self.assertEqual(app._loaded_categories, {"dots"})
            self.assertEqual(decode.call_count, 2)
            self.assertNotIn("crosses/nested/reticle.png", app.crosshair_buttons)
            app.notebook.select(app.tabs["crosses"])
            self.pump()
            key = "crosses/nested/reticle.png"
            self.assertIn(key, app.crosshair_buttons)
            self.assertEqual(decode.call_count, 3)
            app.crosshair_buttons[key].invoke()
            self.assertEqual(read_settings(app.config_path).crosshair, key)
            app.notebook.select(app.tabs["dots"])
            self.pump()
            app.notebook.select(app.tabs["crosses"])
            self.pump()
            self.assertEqual(decode.call_count, 3)
            for canvas in app._category_canvases.values():
                actual = tuple(map(int, canvas.cget("scrollregion").split()))
                self.assertEqual(actual, canvas.bbox("all"))

    def test_saved_nested_selection_opens_matching_category(self):
        initial = Settings(1.25, "crosses/nested/reticle.png")
        write_settings(self.base / "overlay_config.txt", initial)
        app = self.make_app()
        self.assertEqual(app._loaded_categories, {"crosses"})
        self.assertIs(app.selected_button, app.crosshair_buttons[initial.crosshair])
        self.assertEqual(app._current_settings(), initial)

    def test_bad_thumbnail_remains_selectable_without_breaking_other_assets(self):
        (self.resources / "dots/broken.png").write_bytes(b"not a PNG")
        with self.assertLogs(gui.LOGGER, level="WARNING") as log:
            app = self.make_app()
        self.assertEqual(len(log.output), 1)
        app.crosshair_buttons["dots/broken.png"].invoke()
        self.assertEqual(read_settings(app.config_path).crosshair, "dots/broken.png")
        self.assertTrue(app.crosshair_buttons["dots/osupink.png"].cget("image"))

    def test_reopen_preserves_config_without_rewrite(self):
        config = self.base / "overlay_config.txt"
        initial = Settings(1.75, "dots/other.png")
        write_settings(config, initial)
        with patch.object(gui, "write_settings", wraps=write_settings) as write:
            app = self.make_app()
            self.assertEqual(app.current_scale, 1.75)
            self.assertEqual(app._current_settings(), initial)
            self.assertEqual(app.scale_var.get(), 1.75)
            write.assert_not_called()
            self.assertEqual(read_settings(config), initial)

    def test_slider_coalesces_and_unchanged_config_is_not_written(self):
        app = self.make_app()
        with patch.object(gui, "write_settings", wraps=write_settings) as write:
            for index in range(100):
                app.on_scale_changed(str(0.5 + index / 50))
            self.assertEqual(write.call_count, 0)
            self.pump()
            self.assertEqual(write.call_count, 1)
            self.assertEqual(read_settings(app.config_path).scale, 2.48)
            app.save_config()
            self.assertEqual(write.call_count, 1)

    def test_selection_flushes_pending_scale(self):
        app = self.make_app()
        app.on_scale_changed("2.25")
        app.select_crosshair("other.png", "dots")
        self.assertIsNone(app._save_after_id)
        self.assertEqual(read_settings(app.config_path), Settings(2.25, "dots/other.png"))


if __name__ == "__main__":
    unittest.main()
