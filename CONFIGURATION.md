# Configuration and process lifetime

The Python controller and C++ overlay keep the existing text-file IPC. Both
read the same base directory:

1. `AURORA_OVERLAY_HOME` when set (a directory, not a filename).
2. Otherwise `%USERPROFILE%\Documents\Crosshair overlay`.

The file is `overlay_config.txt` inside that directory. To isolate a development
run from existing settings, set the same variable before launching both:

```powershell
$env:AURORA_OVERLAY_HOME = Join-Path $env:LOCALAPPDATA 'AuroraCrosshair-dev'
python CrosshairGUI/gui.py
```

A child overlay inherits this variable. The default remains compatible with the
previous GUI. Both processes prefer resource images under this base directory at
`AuroraCrosshairDX/resources/crosshairs`, then their checkout/executable-relative
resource layout; keep those installations consistent. Redirected Windows Documents folders are not automatically inferred;
use the override if your desired directory differs.

## Format

```ini
scale=1.5
crosshair=dots/osupink.png
```

`scale` is a finite decimal between 0.5 and 3.0; finite out-of-range values are
clamped. Invalid and non-finite values do not replace the last valid setting.
`crosshair` is a relative path beneath the crosshair resource directory. Nested
folders, spaces and UTF-8 names are supported; absolute paths and parent-directory
traversal are rejected. Unknown keys are ignored to retain text-format compatibility.
Preserve the relative directory components when adding your own PNG files.
Valid partial manual updates retain omitted keys. Invalid transactions are
rejected as a whole; the two implementations are not promised to accept every
malformed unknown-key/control-byte combination identically. The GUI always emits
the same complete validated two-key format.

The GUI restores saved settings and commits a complete UTF-8 file by replacing a
temporary file in the same directory. Slider changes are coalesced, unchanged
settings do not write again, and pending settings flush on release, start and
close. The renderer permits replacement while reading and watches directory
filename/write/size changes so an atomic rename remains visible. If watching is
unavailable, a low-rate fallback checks for changes without continuously rendering.
Manual editors can still change the file; save a complete file or use atomic
replacement to avoid exposing partial content.

## GUI and overlay lifetime

Minimizing the GUI does not pause renderer updates. Closing it flushes pending
settings and leaves the overlay running. Reopening loads saved settings instead
of resetting the crosshair. Start/stop uses bounded callbacks during the
operation; there is no permanent background status poller. Refresh Status checks
on demand. Process identity checks prevent stopping an unrelated program that
merely has the same filename.

The overlay stays click-through, always-on-top and nonactivating. Its target is
the primary monitor, matching the original behavior; display/DPI changes should
recenter it in physical pixels. It does not silently follow the foreground game.
Use windowed/borderless modes; capture-affinity flags do not enable exclusive
fullscreen support.

## Diagnostics

Review renderer debug output and controller logging for rejected config, image,
resource or process operations. Repeated dialogs or log writes during normal idle
operation are not required. A missing/corrupt replacement image retains the last usable image or the fallback
crosshair. Decoded images are limited to 64 MiB (16,777,216 pixels), each dimension
to 32,768 pixels, and a retained drawing surface to 256 MiB; oversized custom
assets fail gracefully rather than allocating without bounds. Bundled assets fit
these limits. Only the current decoded image and scaled surface are retained,
not a cache of every full-size PNG.

For a reproduction, record source revision, binary hash, Windows/driver version,
monitor/DPI/layout, config bytes, relative image filename, GUI visibility and
whether a manual file editor was used. See [PERFORMANCE.md](docs/PERFORMANCE.md)
for performance capture details; do not infer input latency from FPS.
