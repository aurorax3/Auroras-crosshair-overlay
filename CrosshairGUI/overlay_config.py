"""Small, validated text configuration shared with the native overlay."""
from dataclasses import dataclass
import math
import os
from pathlib import Path
import tempfile


@dataclass(frozen=True)
class Settings:
    scale: float = 1.0
    crosshair: str = "dots/osupink.png"


def valid_crosshair(value):
    """Return a normalized resource-relative name, or None for an unsafe name."""
    value = value.replace("\\", "/")
    if (not value or len(value) > 255 or value.startswith("/") or ":" in value
            or any(ord(char) < 32 for char in value)
            or any(part in ("", ".", "..") for part in value.split("/"))):
        return None
    return value


def valid_scale(value):
    try:
        scale = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(scale):
        return None
    return min(3.0, max(0.5, scale))


def parse_settings(text, previous=Settings()):
    """Invalid individual fields leave their previous valid values intact."""
    scale, crosshair = previous.scale, previous.crosshair
    for line in text.lstrip("\ufeff").splitlines():
        key, separator, value = line.partition("=")
        if not separator:
            continue
        value = value.strip()
        if key.strip() == "scale":
            candidate = valid_scale(value)
            if candidate is not None:
                scale = candidate
        elif key.strip() == "crosshair":
            candidate = valid_crosshair(value)
            if candidate is not None:
                crosshair = candidate
    return Settings(scale, crosshair)


def read_settings(path, previous=Settings()):
    try:
        return parse_settings(path.read_text(encoding="utf-8-sig"), previous)
    except FileNotFoundError:
        return previous


def write_settings(path, settings):
    """Publish complete UTF-8 settings atomically, without a synchronous disk flush."""
    if valid_scale(settings.scale) != settings.scale or valid_crosshair(settings.crosshair) != settings.crosshair:
        raise ValueError("Invalid overlay settings")
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         prefix=".overlay-config-", suffix=".tmp",
                                         dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(f"scale={settings.scale}\ncrosshair={settings.crosshair}\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
