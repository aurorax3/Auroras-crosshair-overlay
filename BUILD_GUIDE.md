# Build, test and release

## Native Windows build

Install Visual Studio 2022 or Build Tools with the **Desktop development with
C++** workload, MSVC v143 and a Windows 10/11 SDK. Open an x64 developer shell at
the repository root (the directory containing `AuroraCrosshairDX.sln`):

```powershell
msbuild AuroraCrosshairDX.sln /m:2 /p:Configuration=Release /p:Platform=x64
python -m pip install -r CrosshairGUI/requirements.txt
python CrosshairGUI/gui.py
```

Do not run the solution command from the nested project directory. The solution
contains Debug and Release x64 configurations; project-level Win32 configurations
remain available. The SDK supplies WIC/Win32 and DirectX headers/libraries used
by the compiled legacy classes. Do not replace `stb_image.h`: the active renderer
loads PNGs with WIC and does not use that placeholder.

The renderer entry point is `AuroraCrosshairDX/src/main.cpp`. Keep
`main_v2.cpp` and `test_dx.cpp` out of the release source list; both contain
separate entry points. The optional Qt GUI is not required.

## Tests

From the repository root, with the Python requirements installed:

```powershell
python -m unittest discover -s tests -v
cl /nologo /std:c++17 /EHsc /I AuroraCrosshairDX/include tests/renderer_logic.cpp /Fe:renderer-tests.exe
.\renderer-tests.exe
```

Tk integration tests require an available desktop. On Linux, supply a virtual
display, for example `xvfb-run -a python -m unittest discover -s tests -v`.
The portable C++ logic tests can also run with GCC:

```sh
g++ -std=c++17 -Wall -Wextra -pedantic -I AuroraCrosshairDX/include tests/renderer_logic.cpp -o /tmp/aurora-renderer-tests
/tmp/aurora-renderer-tests
```

The prepared Linux cloud environment has a full Windows cross-build helper at
`/workspace/.cloud-environment/build-overlay.sh`; it builds all four production
translation units using MinGW-w64 and Microsoft's DirectXMath headers. Its
successful PE build is not a substitute for MSVC, native WIC/DWM or gameplay
validation. See [VALIDATION.md](docs/VALIDATION.md) for exactly what ran.

## Output and distribution layout

Visual Studio solution builds normally produce `x64/Release/AuroraCrosshairDX.exe`.
The controller also supports the older project-level
`AuroraCrosshairDX/x64/Release/AuroraCrosshairDX.exe` layout. Preserve resource
paths when copying or packaging the executable. A development distribution is:

```text
Crosshair overlay/
  x64/Release/AuroraCrosshairDX.exe
  AuroraCrosshairDX/resources/crosshairs/...
  CrosshairGUI/gui.py
  CrosshairGUI/overlay_config.py
  CrosshairGUI/requirements.txt
  CrosshairGUI/run_gui.bat
```

Keep nested resource directories and filenames intact. Provide Python and the
requirements, or document their installation explicitly; a standalone overlay
can run without the GUI. Do not package benchmark captures, temporary config,
logs or debug executables as application resources. Verify on a clean Windows
account, including paths containing spaces/non-ASCII characters, before release.

## Native acceptance before release

Run the [benchmark protocol](docs/PERFORMANCE.md) against original revision
`18c9dd3e8c7b226ce5da1ec25eacb1a2b2ac5c97`, the candidate and no overlay.
Keep separate output directories and label every binary with its source SHA,
compiler/options and hash. Use an existing checkout or disposable source export;
never reset a working checkout or replace the main branch to run a baseline.

Check transparent/asymmetric/packed-palette PNGs; failed image/config loads;
slider changes and manual atomic file replacement; GUI minimized and closed;
click-through, nonactivation and underlying-game clicks; odd screen dimensions;
100%, 150% and 200% DPI; monitor reconnect, primary-monitor change and negative
monitor coordinates; lock/unlock; repeated start/stop and extended gameplay.
Observe GDI/handle counts and memory before/after repeated image changes. Confirm
idle redraw/presentation work stops rather than assuming low CPU proves it.

Retain measured distributions and variability. A native test failure or
unavailable metric stays open in the validation record. Do not describe a
cross-build or a zero-test run as release readiness.
