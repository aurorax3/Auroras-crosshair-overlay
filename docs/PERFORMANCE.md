# Reproducible performance measurements

The audit describes structural work removed from the render path. It does not
measure game FPS or input latency. Keep original, candidate and overlay-off
runs separate and retain the raw data, including unsuccessful captures.

## Match the conditions

Use the same Windows machine, Windows build, GPU driver, game/replay and camera,
resolution, primary monitor, refresh rate, DPI/layout, power plan, frame cap,
VSync/VRR/HDR, fullscreen mode and background workload. Record all of them.
Build original and candidate with the **same compiler, target, optimization and
runtime settings**. Record source SHA, binary SHA-256 and compiler version.
Do not compare a MinGW baseline with an MSVC candidate.

Original revision: `18c9dd3e8c7b226ce5da1ec25eacb1a2b2ac5c97`.
Export it without resetting a working checkout:

```powershell
git archive --format=zip --output C:\Bench\original-source.zip 18c9dd3e8c7b226ce5da1ec25eacb1a2b2ac5c97
Expand-Archive C:\Bench\original-source.zip C:\Bench\original-source
```

The original solution has an invalid project GUID and incorrect inherited SDK
path properties. For equivalent source builds without editing that original
snapshot, run the following command in an x64 Visual Studio 2022 developer shell
from **each** source root. These are the four sources in both project versions:

```powershell
New-Item -ItemType Directory -Force AuroraCrosshairDX\x64\Release | Out-Null
cl /nologo /std:c++17 /EHsc /O2 /MD /DNDEBUG /DUNICODE /D_UNICODE /I AuroraCrosshairDX\include AuroraCrosshairDX\src\main.cpp AuroraCrosshairDX\src\Window.cpp AuroraCrosshairDX\src\DXRenderer.cpp AuroraCrosshairDX\src\CrosshairManager.cpp /Fe:AuroraCrosshairDX\x64\Release\AuroraCrosshairDX.exe /link /SUBSYSTEM:WINDOWS d3d11.lib dxgi.lib d3dcompiler.lib windowscodecs.lib ole32.lib uuid.lib gdi32.lib user32.lib
Get-FileHash AuroraCrosshairDX\x64\Release\AuroraCrosshairDX.exe -Algorithm SHA256
```

The original configuration location is hardcoded. For original Windows trials,
use its expected `Documents\Crosshair overlay` layout and back up existing user
config before preparing a test account. `AURORA_OVERLAY_HOME` is a candidate
feature and does not relocate the original binary's config. Run only one overlay
version at a time and verify the actual image/scale visually. Keep candidate
config bytes equivalent. Exported original GUI paths also require that layout.

## Scenarios and order

1. Warm up the game/replay and shader caches. Exclude warmup from each capture.
2. Idle desktop: overlay alone, then GUI open, minimized and closed. Capture at
   least 120 seconds per state; keep the image and scale fixed.
3. In-game: a repeatable replay or built-in benchmark, with no overlay, original
   and candidate. Use at least five measured runs per variant. Alternate or
   randomize order (for example off/original/candidate, candidate/original/off).
4. Config stress: the same timed slider sweep and image selections, including
   large images; then settle to idle and verify no continuing redraw work.
5. Stability: extended gameplay (for example 60 minutes), repeated GUI open/close,
   start/stop and crosshair changes, plus monitor/DPI changes and lock/unlock.
   Record duration, exits, artifacts, handle/memory trends and failures.

An FPS difference smaller than run-to-run variance is inconclusive. Compare
per-run metrics and their spread rather than pooling different runs into one
large sample. Do not add an uncapped render test or keep a measurement process
running after a capture.

## Process CPU, memory and optional GPU counters

`tools/performance/capture_process.ps1` is an opt-in, bounded Windows sampler.
Select explicit PIDs for the overlay/controller/game, not every process with a
matching name. Omit the GUI PID when the GUI is closed. For a no-overlay run,
select the game PID. It samples at 1 Hz by default, records process creation
identity, stops on exit/PID reuse, and preserves capture status in metadata.

```powershell
.\tools\performance\capture_process.ps1 -ProcessIds @(1234,5678) -GameProcessId 9012 -RunId candidate-01 -Scenario game -DurationSeconds 120 -OutputDirectory C:\Bench\results -Conditions @{Source='candidate-sha';BinaryHash='sha256';Resolution='2560x1440';RefreshHz=144;DPI=150;VSync='off';VRR='on';Mode='borderless';Workload='fixed replay';Gui='minimized';PowerPlan='Balanced'}
```

Replace the example IDs with the processes you actually launched. The sampler
creates per-run process CSV and metadata JSON. CPU is reported both as a percent
of **one logical core** (`100 × delta CPU seconds / elapsed wall seconds`) and
normalized by the machine's logical processor count. Working set and private
bytes are different measurements; retain both. Handle counts help reveal leaks,
but do not replace a native GDI-object inspection where one is needed.

`-IncludeGpuCounters` requests Windows GPU Engine counters for the selected PIDs.
They can be unavailable, localized, permission-limited or missing for an idle
process. Preserve their status; never substitute zero or sum utilization across
engines/adapters. These counters are sampled, not an end-to-end composition cost
measurement. DWM work can occur in a different process; record/inspect it
separately when investigating composition. The sampler itself has overhead, so
use identical sampling in compared trials and check a capture-off control.

## Game frame times

Use a current external PresentMon/ETW capture only where permitted by the game's
policy. Record the tool version and exact capture command/options. Do not
inject, hook input or work around a denied capture. PresentMon CLI/CSV schemas
vary; inspect that version's help and CSV header instead of assuming one schema.
Capture the game, not the static overlay's update rate.

Analyze **one PID and one swap chain** from a raw CSV:

```powershell
python tools/performance/analyze_frames.py C:\Bench\results\candidate-01.csv --run-id candidate-01 --process-id 9012 --swapchain 0x12345678 --interval-column MsBetweenPresents --output C:\Bench\results\candidate-01-frames.json
```

Choose the exact swap-chain value and interval column in your capture. For other
PresentMon versions, pass its documented equivalent (for example `CPUFrameTime`)
and appropriate `--interval-units ms|s|us`. Label the selected metric: present
intervals, CPU frame intervals and displayed intervals are not interchangeable.
`--process-column` and `--swapchain-column` accommodate explicit header mappings.
The default includes all selected interval rows. To report a separate subset,
use `--dropped-column Dropped --drop-policy presented` or `dropped`; this is a
conditional interval distribution and does not by itself establish display FPS.

Definitions in the JSON:

- Average FPS = `1000 / mean(selected positive frame intervals in ms)`.
- 1% low FPS = `1000 / mean(slowest ceil(N × 0.01) selected intervals)`.
- p50/p95/p99 use linear interpolation at `(N−1) × percentile` (type 7).
- Spike counts are intervals strictly above 16.667, 33.333, 50 and 100 ms by
  default; custom thresholds are available. Keep them identical across variants.

The analyzer rejects missing columns, empty/mixed selection, invalid/nonfinite/
nonpositive selected intervals and unknown dropped-state values. A capture may
have a first interval without a predecessor; explicitly use
`--skip-invalid-intervals` only after understanding it, and report the excluded
count. Keep raw CSV, filters and interval definitions with results. Input latency
is **not** derived from these frame statistics. Use supported game instrumentation
or suitable external hardware for reliable input-to-photon measurements; otherwise
record latency as unavailable.

## Python controller microbenchmark

`tools/performance/measure_gui.py` runs fresh real-Tk processes with an isolated
Documents/config directory and existing resource assets. It records startup
wall/CPU time, process RSS, 5 seconds visible idle, 5 seconds withdrawn idle and
100 slider callbacks at 5 ms spacing. It counts actual filesystem config commits,
then verifies the final config. The workload and short durations are deliberately
identical between the baseline and candidate.

```sh
xvfb-run -a -s '-screen 0 1280x900x24 -nolisten tcp' python tools/performance/measure_gui.py --source CrosshairGUI/gui.py --run-id candidate-gui-01 --display-description 'Xvfb 1280x900x24, no window manager' --output candidate-gui.json
```

Use the same Python/Tk/Pillow/psutil versions, display and trial counts. The source
path/hash and raw trial metadata are retained. Xvfb has no window manager here:
**withdrawn means hidden, not Windows minimized**. CPU excludes the X server, and
RSS is sampled at defined phases rather than a peak. Lazy-tab startup is measured
with only the initially selected category loaded; loading every category is a
separate workload. These results cannot establish Windows renderer/game impact.
The raw baseline and candidate trials and final acceptance state are linked from
[VALIDATION.md](VALIDATION.md).
