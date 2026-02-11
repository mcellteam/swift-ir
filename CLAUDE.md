# Project: SWiFT-IR

- Repository: git@github.com:mcellteam/swift-ir
- Main branch: development
- Current branch: devel_claude

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

## Neuroglancer Lessons Learned (2026-02-11)

### The referencedGeneration Error

When using multiple `ng.LocalVolume` objects (one per slice) with transformation layers in neuroglancer embedded in Qt WebEngine, a JavaScript error occurs: `Cannot set property 'referencedGeneration' of undefined`. This is a race condition in neuroglancer's SharedObject management.

### What We Tried (and Failed)

These approaches did NOT fix the issue for small datasets:
- Creating layers before/after URL is set
- Various delays (500ms, 1000ms, 2000ms, 3000ms)
- Using `setOnLoadCallback` mechanism
- Refreshing URL after adding layers
- Hiding source layer after delay
- Making source layer semi-transparent
- JavaScript injection to trigger navigation/redraw
- Python position changes via `viewer.txn()`

### Key Discovery

- **Large datasets (200+ slices) work reliably** with multiple LocalVolumes and transformation layers
- **Small datasets (<50 slices) fail** with the referencedGeneration error
- User observed that pressing "." and "," (neuroglancer slice navigation keys) after the blank viewer appeared would make images display correctly - this suggested a timing/initialization issue in neuroglancer's WebGL/WebSocket handling

### Working Solution

Size-based approach in `src/ui/tabs/manager.py` and `src/viewers/viewerfactory.py`:

1. **Small datasets (<50 slices)**: Pre-compute affine transforms in Python using `scipy.ndimage.affine_transform()`, then display with a single LocalVolume. This avoids the multi-LocalVolume race condition entirely.

2. **Large datasets (≥50 slices)**: Use neuroglancer's native transformation layers (multiple LocalVolumes with per-layer affine transforms). These work reliably for larger datasets.

### Memory Management

When switching between tabs that create/destroy neuroglancer viewers:
- Call `LocalVolume.invalidate()` on all LocalVolume objects
- Clear `self.tensor = None` to release numpy array memory
- Use delayed cleanup (1 second via QTimer) to allow pending JavaScript operations to complete
- Don't accumulate old LocalVolumes in lists (memory leak)

### Code Patterns

Use the `BlockStateChanges` context manager for safe state change blocking:
```python
with self.block_state_changes():
    with self.txn() as s:
        # modifications here won't trigger on_state_changed callback
```

Use `WebEngine.setOnLoadCallback()` for operations that need the page fully loaded:
```python
def add_layers():
    viewer.add_im_layer('source', data)
    webengine.setUrl(QUrl(viewer.get_viewer_url()))
webengine.setOnLoadCallback(add_layers)
