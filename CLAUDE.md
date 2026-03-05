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

### Important
- `Qt.AA_UseDesktopOpenGL` must be set BEFORE `QApplication()` is created
- `QLabel("x:").setAlignment(...)` returns `None` — never chain these; assign label first, then call setAlignment

## TACC Lonestar6 (LS6) Deployment

### Launch
```bash
cd $WORK/swift-ir
source tacc_launch
```

### Dependencies
Managed by `uv` via `pyproject.toml` — no conda. `uv run` creates/uses `.venv` automatically.

### Required modules
```
ml intel/19.1.1 swr/21.2.5 impi/19.0.9 fftw3/3.3.10
```

### WebGL through SWR
QtWebEngine's Chromium needs these flags to render WebGL via the SWR software rasterizer:
```
--ignore-gpu-blocklist --enable-webgl-software-rendering --use-gl=desktop
```
Without these, neuroglancer fails with "WebGL not supported".

### Environment variables (set by tacc_launch)
```
QT_API=pyqt5
BLOSC_NTHREADS=1
OPENBLAS_NUM_THREADS=1
OMP_NUM_THREADS=1
MKL_NUM_THREADS=1
LIBTIFF_STRILE_ARRAY_MAX_RESIZE_COUNT=1000000000
```

### Platform binaries
Pre-compiled SWiFT-IR C executables (swim, mir, iavg, iscale2, remod) are in `src/lib/bin_tacc/`.
