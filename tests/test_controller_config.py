import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

GUI_DIR = Path(__file__).resolve().parents[1] / "CrosshairGUI"
sys.path.insert(0, str(GUI_DIR))
from overlay_config import Settings, parse_settings, read_settings, valid_crosshair, write_settings


class SettingsTests(unittest.TestCase):
    def test_valid_unicode_nested_config_and_clamping(self):
        self.assertEqual(parse_settings("\ufeffscale=9\ncrosshair=crosses/1px outline/é.png\n"),
                         Settings(3.0, "crosses/1px outline/é.png"))
        self.assertEqual(parse_settings("scale=0.1"), Settings(0.5))
        self.assertEqual(valid_crosshair(r"crosses\nested\a.png"), "crosses/nested/a.png")

    def test_invalid_transactions_preserve_last_good(self):
        old = Settings(1.5, "dots/a.png")
        for scale in ("nan", "inf", "-inf", "nonsense", ""):
            self.assertEqual(parse_settings(f"scale={scale}\ncrosshair=../evil.png", old), old)
        for path in ("../x.png", "/x.png", "C:/x.png", "a//b.png", "a/./b.png", "a/../b.png", "a\x00b", "a?.png", "folder./a.png", "folder /a.png", ""):
            self.assertIsNone(valid_crosshair(path), path)
        self.assertEqual(parse_settings("scale=2\ncrosshair=../x.png", old), old)
        self.assertEqual(parse_settings("scale=nan\nscale=2\nscale=invalid", old), old)

    def test_partial_updates_comments_unknown_keys_and_duplicates(self):
        old = Settings(1.5, "dots/a.png")
        self.assertEqual(parse_settings("# comment\r\nscale=2\r\nunknown=value", old), Settings(2, old.crosshair))
        self.assertEqual(parse_settings("crosshair=crosses/b.png", old), Settings(old.scale, "crosses/b.png"))
        self.assertEqual(parse_settings("scale=2\nscale=2", old), old)
        self.assertEqual(parse_settings("scale=2\ngarbage", old), old)
        self.assertEqual(parse_settings("; comment\n", old), old)

    def test_atomic_round_trip_and_missing_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overlay_config.txt"
            self.assertEqual(read_settings(path), Settings())
            settings = Settings(1.75, "crosses/nested/é.png")
            write_settings(path, settings)
            self.assertEqual(read_settings(path), settings)
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_failed_replace_preserves_original_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overlay_config.txt"
            original = b"scale=1.0\ncrosshair=dots/old.png\n"
            path.write_bytes(original)
            with patch("overlay_config.os.replace", side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    write_settings(path, Settings(2.0, "dots/new.png"))
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
