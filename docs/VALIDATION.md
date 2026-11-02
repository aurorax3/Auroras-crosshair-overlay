# Validation record

Work is committed on `perf/event-driven-overlay`. The original source is
`18c9dd3e8c7b226ce5da1ec25eacb1a2b2ac5c97`. The audit was committed before
implementation. The main branch was not changed, and nothing was merged or
published by this development task.

## Executed checks

| Check | Result and scope |
| --- | --- |
| Full C++ Windows cross-build | Passed for all four production translation units using MinGW-w64 GCC 14 POSIX, C++17, `-O2`, Unicode and the existing Windows subsystem/libraries. The resulting PE32+ x64 file was inspected; Windows execution was not tested. |
| Portable renderer logic | 113 checks passed, including parser validation/transactional behavior, finite scale clamping, Unicode/nested paths, odd-size and negative-origin centering, clipping, premultiplied sampling and edge/overflow cases. AddressSanitizer and UndefinedBehaviorSanitizer also passed. |
| Python/config/Tk/benchmark tests | `python -m unittest discover -s tests -v` ran **32 tests, all passed, none skipped**, under Xvfb. Includes real Tk widgets/config files, atomic replacement failure preservation, slider write coalescing, saved state, nested selection, lazy tabs, process identity, nonblocking lifecycle and a real child surviving GUI close; plus frame-statistic formulas/filters and capture isolation. |
| Actual bundled PNG previews | Five tabs, 28 initial default-category previews; visiting all categories produced 390 thumbnails with no fallback, logging warning or Tk callback error. A nested image selection and pending scale were saved on close. |
| Cloud GUI launcher | Started the actual controller with five tabs/28 previews, printed readiness, and was stopped after a bounded startup check. The updated cloud smoke launcher also passed all 32 tests. |
| Build/project/data checks | Valid consistent project GUID, inherited SDK include/library properties and header inventory checked. Captured raw-data/source/harness SHA-256 values verified. `git diff --check` passed. |
| Independent source review | Event waits, parent-watch rebinding, WIC/GDI ownership, primary-monitor/DPI logic, configuration replacement, GUI lifecycle, measurement formulas and documentation reviewed. No remaining blocking source-review finding; native API behavior still requires execution. |

Reproduce commands are in [BUILD_GUIDE.md](../BUILD_GUIDE.md) and
[PERFORMANCE.md](PERFORMANCE.md). Sanitizer command used for the portable checks:

```sh
g++ -std=c++17 -Wall -Wextra -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer -I AuroraCrosshairDX/include tests/renderer_logic.cpp -o /tmp/aurora-renderer-tests
/tmp/aurora-renderer-tests
```

The cloud cross-build artifact at
`/workspace/.cloud-environment/build/AuroraCrosshairDX.exe` has SHA-256
`95b7da45a3761a79ccf6ec6d8653c433a59d9ce4a80c58536e9e6581e79fc585`
(renderer source through `a08806d`). This identifies an inspected Linux-built
Windows artifact; it is not a native release approval.

## Matched GUI measurements

Three fresh-process trials per version used the same finalized harness,
390-PNG content manifest, seeded `dots/osupink.png` config, AMD EPYC 7763 host,
Debian/Linux, Python 3.12.14, Tk 9, Pillow 12.3.0, psutil 7.2.2 and
Xvfb 1280×900×24 without a window manager. Original trials ran first, candidate
second. This shared cloud host was not a controlled gaming benchmark machine.
The captured GUI source and companion module hashes identify the measured
performance implementation at `0d108f6`. The subsequent monochrome terminal-style
theme was validated separately; these timing/RSS numbers are not a new measurement
of that visual revision.

Values are median **[minimum–maximum]**:

| Python-process metric | Original | Candidate |
| --- | --- | --- |
| Startup wall time | 0.7789 s [0.7533–0.8024] | 0.1132 s [0.1101–0.1142] |
| Startup CPU time | 0.7152 s [0.6899–0.7389] | 0.0666 s [0.0651–0.0680] |
| Initial RSS | 66.93 MiB [66.92–66.93] | 35.44 MiB [35.44–35.45] |
| Visible idle CPU, percent of one core | 0.2533% [0.2117–0.3143] | 0.2428% [0.2121–0.2886] |
| Withdrawn idle CPU, percent of one core | 0.1936% [0.1840–0.2396] | 0.2264% [0.1933–0.2324] |
| Config commits during 100 slider callbacks | 100 in every trial | 25 in every trial |
| Slider-workload CPU time | 0.0329 s [0.0324–0.0457] | 0.0390 s [0.0356–0.0407] |
| Config commits during either idle phase | 0 | 0 |

Startup improves by deferring unopened categories: the candidate initially
loads 28 selected-category previews rather than all 194 formerly exposed
previews. Other categories are deferred, not removed; all 390 are available
when visited. Initial RSS is not peak RSS after opening every category.

Idle CPU ranges overlap and the withdrawn median increased. Slider CPU also
shows no supported reduction. **These samples do not support an idle-CPU or
slider-CPU improvement claim.** Fewer config publications, faster initial GUI
startup and lower initial Python RSS are the supported observations.

The 5-second idle windows are short. CPU excludes X server work. Withdrawn means
hidden under Xvfb, not Windows minimized. Slider callbacks requested `after(5)`
spacing, but the observed burst took approximately 2.33 seconds including a
300 ms settle: requested timer spacing is not measured realized spacing.
Both versions used the same requests and persisted exactly scale 3.0 and
`dots/osupink.png`. No renderer/game performance inference follows from these
GUI measurements.

Raw evidence:

- [Matched original trials](performance/gui-baseline-matched.json)
- [Candidate trials](performance/gui-optimized.json)
- [Comparison and ranges](performance/gui-comparison.json)
- [Source, resource and capture provenance](performance/gui-matched-provenance.json)
- [Earlier original baseline](performance/gui-baseline.json), retained separately
- [Explicit native measurement status](performance/native-measurement-status.json)

## Native validation still open

The available host cannot run a native Windows desktop/game session. The
following are **unrun or unmeasured**, with no inferred pass or zero value:

- MSVC/MSBuild execution and the added Windows CI workflow.
- Native WIC format/alpha/orientation output and actual GDI handle lifetime.
- Click-through/nonactivation, topmost behavior, physical primary positioning,
  mixed DPI, monitor reconnection, lock/unlock and DWM composition transitions.
- Native directory notifications, atomic replacement and directory rebinding,
  including Windows editor sharing and files on unusual/network filesystems.
- Windows process start/WM_CLOSE/shutdown integration and GUI minimized behavior.
- Overlay CPU/working set/private bytes, GPU/DWM utilization, average game FPS,
  1% lows, frame-time distributions/spikes and extended gameplay stability.
- Reliable input-to-photon latency.

The PowerShell process sampler was statically reviewed but could not run on this
host. Frame analyzer tests use deterministic fixtures; they validate calculations,
not a captured game's performance. Run the equivalent-condition protocol in
[PERFORMANCE.md](PERFORMANCE.md) and retain native captures before release or
claiming reduced gameplay impact. No zero-performance-impact claim is made.

## Remaining limits and handoff

The renderer still targets the primary monitor by default. Image memory and
surface bounds are documented in [CONFIGURATION.md](../CONFIGURATION.md).
Only the current decoded image and scaled surface are cached. Editing a PNG in
place requires selecting another image and returning, or restarting the overlay;
resource files are not continuously watched. Very unusual malformed unknown-key
or unrepresentable numeric inputs can be rejected differently by the two parsers;
normal generated configs and tested valid manual updates agree.

The existing C++ renderer/Python GUI architecture and legacy classes remain.
No game injection, input hook, new framework, high-frequency render loop or
permanent helper service was added. The cloud install/start draft was refreshed
for the changed import path and test-based readiness check, and those current
instance commands passed. A draft save does not publish an environment snapshot
or establish fresh-task restoration. Review/save and publish in environment
settings if retaining that updated cloud setup.

## Monochrome controller theme

The visual follow-up retains Tk and uses static grayscale styles, a monospace
font, numbered sections and bracketed controls. Preview cards keep their neutral
background and display the original colored images. Selection has an outlined
card, and keyboard focus contrasts with the selected tab.

All 32 existing Python/config/Tk/benchmark tests passed after the final styling.
Separate processes compared every generated preview against the pre-theme
controller at `67ae3ca`: all 390 PhotoImages have identical RGBA pixel hashes and
dimensions. PNG resource files and the thumbnail conversion are unchanged.
The renderer, configuration and process-lifecycle implementation were not changed;
no timer, background process or dependency was added.

The rendered Xvfb window was inspected and captured in the
[controller screenshot](images/controller-monochrome.png). Native Windows title
bar/dialog appearance remains controlled by Windows and was not inspected here.
Performance figures above remain measurements of the earlier stated revision.
