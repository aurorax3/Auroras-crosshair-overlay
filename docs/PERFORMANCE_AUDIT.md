# Performance audit and baseline

Audited revision: `18c9dd3e8c7b226ce5da1ec25eacb1a2b2ac5c97`.
Implementation branch: `perf/event-driven-overlay`. References below describe
the original revision so the findings remain reproducible after edits.

## Architecture and composition

The shipping entry point is `AuroraCrosshairDX/src/main.cpp:wWinMain` (402).
It creates a `WS_POPUP` window with `WS_EX_LAYERED`, `WS_EX_TOPMOST`,
`WS_EX_TRANSPARENT` and `WS_EX_NOACTIVATE` (441–449). It loads PNGs through
Windows Imaging Component (WIC), scales pixels on the CPU, and submits a
premultiplied BGRA bitmap through `UpdateLayeredWindow` (223–399). Windows
composes and retains this layered-window image; unchanged content does not need
an application animation loop. Composition can still have a cost, and overlays
can change a game's presentation mode. Neither a static image nor a small
surface establishes zero FPS or input-latency impact.

Despite the project name and older documentation, the active entry point never
instantiates `DXRenderer`, `Window` or `CrosshairManager`. Their sources are still
compiled by `AuroraCrosshairDX.vcxproj` (155–158). `DXRenderer.cpp` contains a
separate D3D11/swap-chain implementation with placeholder/test behavior;
`main_v2.cpp` and the interactive `test_dx.cpp` are not production entry points.
The optimization must retain the active C++ GDI/WIC engine, not switch engines.

The primary controller is Python/Tk (`CrosshairGUI/gui.py`). Its IPC is the
two-key UTF-8 text file `overlay_config.txt`, with no socket or worker service.
Both applications assume `Documents/Crosshair overlay`. The Python controller
expects the executable at `AuroraCrosshairDX/x64/Release`, while normal solution
builds can put it at the solution's `x64/Release`. Resources are relative to the
executable in C++ and hardcoded in Python. The Qt/CMake controller is optional
legacy code, not a dependency of the Python workflow.

## Five highest-impact changes, in order

| Rank | Evidence in original revision | Incremental change | Risk and validation |
| --- | --- | --- | --- |
| 1 | `main.cpp:wWinMain` 469–499 calls `RenderCrosshair` then `Sleep(16)` even with unchanged state. | Draw once and on effective changes; block on Win32 messages and directory notifications. Keep a low-rate fallback for unavailable directory watching. | Missed change/repaint notifications can leave stale content. Check manual edits, atomic replacement, GUI-closed operation, display changes, idle wakeups and shutdown on Windows. |
| 2 | `RenderCrosshair` 225–257 allocates a full-monitor DC/DIB and clears every pixel on every redraw; 393 transfers the whole monitor; 395–399 destroys resources. | Retain a DIB/DC and scaled pixels; size the window and surface to visible crosshair bounds, centered at the same physical screen point. | Cropping/orientation/alpha and odd-sized positioning regressions are possible. Compare asymmetric and transparent PNGs, fallback crosshair, large assets, multiple resolutions and GDI handle counts. |
| 3 | `LoadConfiguration` 186–220 opens disk every 500 ms and mutates globals while parsing; `gui.py:on_scale_changed` 277 and `save_config` 284 truncate/write for every slider event. GUI startup also overwrites previous config (257–259). | Validate configuration, publish complete files atomically, coalesce slider writes, skip unchanged values, notify the renderer and preserve saved state. | Reader sharing must permit Windows replacement; reject NaN/traversal without losing last valid state. Keep the text IPC compatible with manual edits and the legacy controller. Flush pending values on start, slider release and close. |
| 4 | `LoadPNGTexture` 37–184 recreates COM/WIC for each selection; indexed formats are incorrectly assumed to use one byte per pixel (89–137), all other formats four (151–168); early failure can retain inconsistent old state. | Use a WIC format converter, transactional image replacement, checked dimensions and scoped ownership; retain the current decoded image/scaled surface instead of decoding on redraw. | PNG colors, transparency and vertical orientation must match. Test palette/gray/RGB/RGBA and invalid/oversized inputs. Bound caching to avoid retaining hundreds of full-screen images. |
| 5 | Python eagerly creates all 194 previews (`load_crosshairs` 112–255); sleeps/waits block Tk in start/stop (311–357); process matching uses name alone; tab closures capture the last canvas (147, 255). | Populate categories when opened, retain previews, bind each canvas correctly, and use bounded one-shot lifecycle callbacks with process identity checks. | Lazy loading must restore selections and support nested relative asset paths. Preserve GUI-close/overlay-remains-running behavior; prevent pending writes or process races from losing settings or stopping another instance. |

## Other correctness and reliability findings

- The Python GUI has **no recurring idle polling or background thread**. Its five
  delayed canvas callbacks are one-shot. Do not add a permanent status poller.
- `main.cpp` uses primary-screen size once (404–406), assumes origin `(0,0)`,
  declares no DPI awareness and handles neither `WM_DPICHANGED` nor
  `WM_DISPLAYCHANGE`. Preserve primary-monitor targeting while handling physical
  bounds, DPI changes and negative coordinates; do not follow foreground games
  or add input hooks implicitly.
- `SetWindowDisplayAffinity(WDA_MONITOR)` (452) controls capture behavior; it
  cannot make an overlay visible over true exclusive fullscreen. Preserve the
  existing capture choice and document borderless/windowed compatibility.
- `_wtof` accepts malformed/non-finite scale values poorly (205–207). Config
  crosshair paths are not constrained to resources. WIC/GDI/COM failures mostly
  lack diagnostics and return checks.
- The repository contains 390 PNGs (~2.45 MB compressed); only 194 immediate
  category files are exposed. The other 196 are nested under `crosses`. Several
  PNGs are 1920×1080 or larger, including a 3072×1536 image. Bounds and allocation
  limits must account for these instead of assuming every image is a tiny icon.
- Closing the Python GUI already leaves its child overlay running. Preserve it
  and flush pending settings. The optional Qt destructor instead stops it; Qt
  scans root PNGs (none currently exist), blocks during process lifecycle and
  has a thickness control that is not serialized. Do not introduce Qt into the
  primary workflow.
- `run_gui.bat` performs dependency installation every launch and omits Pillow.
  Setup should be explicit; startup should only start the controller.
- Historical Markdown contains unsupported claims such as '<1% CPU', '60+ FPS',
  and 'fullscreen compatible'. These are not measurements or acceptance evidence.

## Baseline and measurement boundary

Baseline source is preserved by Git at the audited SHA. Its cross-compiled
64-bit executable is retained outside the checkout under
`/workspace/.cloud-environment/performance/baseline/AuroraCrosshairDX.exe`
(SHA-256 `527ee24959bc3c2e0ce70aa2ee4574feba3d96f7164d0ad94760afd9ada9f9ad`).
The full four-source cross-build and controller functional checks passed before
implementation. There was no automated test suite in the original repository.

Static cost estimate: a 1920×1080×4 buffer is 8,294,400 bytes; at an idealized
60 redraws/s the clear alone writes ~498 MB/s. At 3840×2160 it is ~1.99 GB/s,
before image work, allocation, transfer and composition. These are arithmetic
estimates, **not measured bandwidth, CPU usage, GPU load or FPS degradation**.

The available machine is Debian 13 with no Windows desktop, game, native DWM or
input-latency rig. Native overlay CPU, working set, GPU use, game FPS/1% lows,
frame-time distributions, end-to-end input latency and extended-gameplay
stability are therefore **unmeasured**, not zero or passed. Linux/Xvfb controller
startup/idle/memory/config-write measurements can compare Python behavior only.
Raw repeated trials and equivalent-condition Windows capture instructions will
accompany implementation. Never substitute a synthetic loop or Linux GUI
measurement for a Windows gameplay result.

Windows comparisons must cover no overlay, original overlay and candidate on
the same game replay, build, scene, resolution, refresh rate, DPI, monitor,
fullscreen mode, frame cap, VSync/VRR/HDR and power plan. Warm up first, alternate
the order, retain raw captures, repeat runs and report variability. Record GUI
open/minimized/closed separately. Use process CPU/working set and opt-in external
ETW/PresentMon captures where allowed; do not inject, hook input or bypass game
protections. Define 1% lows explicitly, and report unavailable GPU/latency fields
as unavailable. Reliable input latency needs a suitable instrumented game or
external hardware measurement; frame pacing is not an input-latency measurement.

## Implementation and acceptance

Make independent commits for audit/baseline, event-driven wakeups, cached surface
and image ownership, configuration/controller behavior, tests/benchmark tooling
and documentation. Keep unused legacy engines available. Each step must pass the
available C++ cross-build and relevant portable/GUI tests before proceeding.
Native visual and gameplay acceptance remains open until Windows captures and
manual checks are run; do not claim zero impact or native validation from builds.
