# Project: SWiFT-IR

- Repository: git@github.com:mcellteam/swift-ir
- Main branch: devel_protocol_1
- Current branch: devel_claude_pyqt5_ls6

## Git History Cleanup (2026-01-28)

The .git directory was reduced from 2.9 GB to 633 MB by removing large binary and log files from history using `git filter-repo`. All commit SHAs were rewritten and force-pushed to origin.

### Files removed from history
- All `.tif` / `.tiff` files (3.3 GB across `tests/test_images/`, `tests/r34_protocol_1_test/`, `alignEM/test_data/`, `scale_2/img_aligned/`)
- `messages.log` (2.2 GB across 27 versions)
- `source/PySide2/make_zarr.log` and `source/PySide6/make_zarr.log`
- All `.gif` files (including `src/resources/alignem_animation.gif`)
- All `.jpg` / `.jpeg` files
- All `.jar` and `.whl` files
- `chromedriver` and `src/chromedriver`
- `scale_2/` directory
- `source/PySide2/vj_097_4k4k_1.png`

### .gitignore already excludes
- `**/messages.log`, `*.egg-info`, `**/__pycache__`, `**/.DS_Store`, `**/*.jpg`, `**/*.tif`, `**/*.tiff`

### Backup
- A `.git-backup` directory was created before the rewrite. It can be deleted once the cleanup is confirmed stable.
- All collaborators need to re-clone after the force push.

## Environment
- macOS, using MacPorts (not Homebrew)
- Python 3 with pip-installed `git-filter-repo`
- GitHub CLI (`gh`) installed via MacPorts

## Network Configuration (Salk Institute)

This machine is on the Salk Institute network, routed through SDSC (San Diego Supercomputer Center) and Internet2 (academic backbone).

### GitHub Download Speed Issue

GitHub clone speeds are limited to ~2-5 MB/s (vs 25 MB/s on commercial internet) due to poor peering between Internet2 and GitHub's core infrastructure.

| GitHub Endpoint | IP Range | Latency | Speed |
|---|---|---|---|
| github.com / codeload | 140.82.116.x | 29 ms | 2-3 MB/s (SSH), 4-5 MB/s (HTTPS) |
| GitHub CDN (releases) | 185.199.x.x | 3 ms | 16+ MB/s |

**Recommendation**: Use HTTPS instead of SSH for faster clones on this network.

### Network Path
```
Salk Institute → SDSC → CENIC → Internet2 → GitHub
```

General internet speed is fine (60 MB/s to Cloudflare). The bottleneck is specific to GitHub's core servers (140.82.116.x) via Internet2 peering.

## Qt / PyQt5

This branch uses PyQt5 (not PySide6). All Qt imports go through `qtpy` with `QT_API=pyqt5`.

### Enum style
Use PyQt5 old-style flat enums everywhere:
- `Qt.AlignLeft` not `Qt.AlignmentFlag.AlignLeft`
- `Qt.NoFocus` not `Qt.FocusPolicy.NoFocus`
- `Qt.Vertical` not `Qt.Orientation.Vertical`
- `QSizePolicy.Minimum` not `QSizePolicy.Policy.Minimum`
- `Qt.AscendingOrder` not `Qt.SortOrder.AscendingOrder`
- `Qt.StrongFocus` not `Qt.FocusPolicy.StrongFocus`
- `Qt.LeftButton` not `Qt.MouseButton.LeftButton`
- `QScrollerProperties.OvershootAlwaysOff` not `QScrollerProperties.OvershootPolicy.OvershootAlwaysOff`

### Important
- `Qt.AA_UseDesktopOpenGL` must be set BEFORE `QApplication()` is created (in `__main__`, not `main()`)
- `QLabel("x:").setAlignment(...)` returns `None` — never chain widget creation with method calls; assign first, then call methods
- `src/resources/icons_rc.py` has a direct `from PyQt5 import QtCore` import (not through qtpy) — leave as-is

### Files modified for PyQt5 enum port
98 enum replacements across 10 files:
- `src/ui/main_window.py` — 41 replacements (FocusPolicy, AlignmentFlag, Orientation, StrongFocus)
- `src/ui/tabs/project.py` — 20 replacements (Orientation, FocusPolicy, SizePolicy, ScrollPhase, KeyboardModifiers)
- `src/ui/tabs/webbrowser.py` — 19 replacements (FocusPolicy, AlignmentFlag)
- `src/ui/tabs/manager.py` — 5 replacements (Orientation, null widget fix)
- `src/ui/tools/snrplot.py` — 4 replacements (AlignmentFlag, MouseButton)
- `src/ui/layouts/layouts.py` — 2 replacements (Orientation)
- `src/ui/views/filebrowser.py` — 1 replacement (SortOrder)
- `src/ui/widgets/toggleswitch.py` — 1 replacement (FocusPolicy)
- `src/ui/widgets/vertlabel.py` — 3 replacements (AlignmentFlag)
- `alignEM.py` — 1 replacement (ApplicationAttribute)

### WebEngine JS console filtering
`FilteredWebEnginePage` in `src/ui/views/webengine.py` suppresses known SWR/software-renderer noise from QtWebEngine's JS console. Applied to both WebEngine classes:
- `src/ui/views/webengine.py` — used by project/alignment tab neuroglancer viewers
- `src/ui/tabs/manager.py` — used by Alignment Manager tab viewers

To suppress additional messages, add substrings to `_JS_SUPPRESS` in `src/ui/views/webengine.py`.

## TACC Lonestar6 (LS6) Deployment

### Launch
```bash
cd $WORK/swift-ir
source tacc_launch
```
Uses `uv run` to launch — no conda activation needed.

### Dependencies
Managed by `uv` via `pyproject.toml`. `uv run` creates/uses `.venv` automatically.

### Required modules
```
ml intel/19.1.1 swr/21.2.5 impi/19.0.9 fftw3/3.3.10
```
- `intel/19.1.1` — Intel compilers and runtime
- `swr/21.2.5` — Mesa Software Rasterizer (provides OpenGL on nodes without GPUs)
- `impi/19.0.9` — Intel MPI
- `fftw3/3.3.10` — FFT library used by SWiFT-IR C binaries

### WebGL through SWR
QtWebEngine's Chromium needs these flags (set in `alignEM.py`) to render WebGL via the SWR software rasterizer:
```
--ignore-gpu-blocklist --enable-webgl-software-rendering --use-gl=desktop
```
Without `--ignore-gpu-blocklist`, Chromium blocklists SWR and neuroglancer fails with "WebGL not supported". The `--use-gl=desktop` flag tells Chromium to use the system's desktop OpenGL (provided by SWR) rather than its built-in ANGLE/SwiftShader.

### Chromium log suppression
Chromium logging is set to `--enable-logging --log-level=3` (fatal only) in `alignEM.py` to suppress verbose GPU process warnings. The `FilteredWebEnginePage` class handles remaining JS-level SWR noise.

### Environment variables (set by tacc_launch)
```
QT_API=pyqt5
BLOSC_NTHREADS=1
OPENBLAS_NUM_THREADS=1
OMP_NUM_THREADS=1
MKL_NUM_THREADS=1
LIBTIFF_STRILE_ARRAY_MAX_RESIZE_COUNT=1000000000
```
`MESA_DEBUG` is explicitly unset to suppress Mesa debug output.

### Platform binaries
Pre-compiled SWiFT-IR C executables (swim, mir, iavg, iscale2, remod) are in `src/lib/bin_tacc/`.

### Access
LS6 is accessed via DCV (Desktop Cloud Visualization) sessions for GUI work. Performance through DCV is acceptable for neuroglancer viewing.
