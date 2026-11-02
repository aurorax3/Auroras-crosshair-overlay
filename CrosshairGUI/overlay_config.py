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
    if (not value or len(value) > 4096 or value.startswith("/") or any(char in value for char in '<>"|?*:')
            or any(ord(char) < 32 for char in value)
            or any(part in ("", ".", "..") or len(part) > 255 or part.endswith((".", " "))
                   for part in value.split("/"))):
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
    """Apply valid partial updates; reject ambiguous or malformed transactions."""
    scale, crosshair = previous.scale, previous.crosshair
    seen = set()
    for line in text.lstrip("\ufeff").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        key, separator, value = line.partition("=")
        if not separator:
            return previous
        key, value = key.strip(), value.strip()
        if key not in ("scale", "crosshair"):
            continue
        if key in seen:
            return previous
        seen.add(key)
        if key == "scale":
            candidate = valid_scale(value)
            if candidate is None:
                return previous
            scale = candidate
        else:
            candidate = valid_crosshair(value)
            if candidate is None:
                return previous
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
