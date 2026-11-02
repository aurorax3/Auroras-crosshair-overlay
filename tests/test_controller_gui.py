"""Functional controller checks; run under Xvfb on Linux or a Windows desktop."""
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

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
        try:
            exists = self.root.winfo_exists()
        except tk.TclError:
            exists = False
        if exists:
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

    def test_root_level_crosshair_selection_updates_button_and_config(self):
        path = self.resources / "root.png"
        Image.new("RGBA", (8, 8), (255, 255, 255, 255)).save(path)
        app = self.make_app()
        app.notebook.select(app.tabs[""])
        self.pump()
        button = app.crosshair_buttons["root.png"]
        button.invoke()
        self.assertIs(app.selected_button, button)
        self.assertEqual(read_settings(app.config_path).crosshair, "root.png")

    def test_close_flushes_pending_settings_and_leaves_overlay_child_alive(self):
        app = self.make_app()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            app._owned_process = child
            app.on_scale_changed("2.5")
            app._process_after_id = self.root.after(10000, lambda: self.fail("Cancelled callback ran"))
            app.on_close()
            self.assertTrue(app._closed)
            self.assertIsNone(app._save_after_id)
            self.assertIsNone(app._process_after_id)
            self.assertEqual(read_settings(app.config_path).scale, 2.5)
            self.assertIsNone(child.poll())
        finally:
            child.terminate()
            child.wait(timeout=2)

    def test_start_and_stop_are_nonblocking_and_leave_no_idle_timer(self):
        app = self.make_app()
        process = Mock()
        process.pid = 1234
        process.poll.return_value = None
        app.overlay_exe = Path(sys.executable)
        with patch.object(gui.subprocess, "Popen", return_value=process), patch.object(gui.psutil, "process_iter", return_value=[]):
            before = time.monotonic()
            app.start_overlay()
            self.assertLess(time.monotonic() - before, 0.1)
            self.assertEqual(app._process_action, "starting")
            self.pump(0.2)
            self.assertTrue(app.overlay_running)
            self.assertIsNone(app._process_after_id)
            process.terminate.side_effect = lambda: setattr(process.poll, "return_value", 0)
            with patch.object(app, "_request_window_close", return_value=False):
                app.stop_overlay()
                self.pump()
            process.terminate.assert_called_once()
            self.assertFalse(app.overlay_running)
            self.assertIsNone(app._process_after_id)
            self.assertIsNone(app._process_action)

    def test_same_name_wrong_path_is_never_terminated(self):
        app = self.make_app()
        wrong = Mock()
        wrong.info = {"name": "AuroraCrosshairDX.exe", "exe": str(self.home / "unrelated/AuroraCrosshairDX.exe")}
        with patch.object(gui.psutil, "process_iter", return_value=[wrong]):
            app.stop_overlay()
        wrong.terminate.assert_not_called()
        wrong.kill.assert_not_called()
        self.assertFalse(app.overlay_running)

    def test_attached_process_requires_full_path_and_live_identity(self):
        app = self.make_app()
        attached = Mock(spec=gui.psutil.Process)
        attached.info = {"name": "AURORACROSSHAIRDX.EXE", "exe": str(app.overlay_exe)}
        attached.is_running.return_value = True
        attached.status.return_value = gui.psutil.STATUS_RUNNING
        attached.exe.return_value = str(app.overlay_exe)
        with patch.object(gui.psutil, "process_iter", return_value=[attached]):
            self.assertIs(app.check_overlay_status(), attached)
        attached.exe.return_value = str(self.home / "unrelated.exe")
        with patch.object(gui.psutil, "process_iter", return_value=[]):
            self.assertIsNone(app.check_overlay_status())
        attached.terminate.assert_not_called()

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
