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
```

## Signal/Slot UI Debugging (2026-02-23)

### Architecture Overview

The central signal chain for position changes:
```
User action (slider, arrow key, neuroglancer click)
    → dm.zpos setter (data.py:302)
        → positionChanged.emit() (data.py:311)
            → _onPositionChangeConsolidated (project.py:115)
                → onPositionChange → updates slider, viewers, dock widgets
```

Key signal hubs:
- `DataModel.signals.positionChanged` — drives all position-dependent UI updates
- `DataModel.signals.swimArgsChanged` — drives alignment parameter UI updates
- `WorkerSignals` on each viewer — arrow keys, zoom, layout, state changes
- `_alignworker.finished` / `_zarrworker.finished` — 12-13 slots each, big cascades

### Existing Safeguards (Good Patterns)

1. **`BlockStateChanges` context manager** (`viewerfactory.py:136`): Prevents re-entrant `on_state_changed()` callbacks in all viewer types. Always use this when modifying neuroglancer state programmatically.

2. **`_position_change_in_progress` guard** (`project.py:85`): Prevents re-entrant position change handling. The consolidated handler (`_onPositionChangeConsolidated`) wraps `onPositionChange` + `updateDwMatches` + `updateDwThumbs` in a single guarded call.

3. **`dm.zpos` setter guard** (`data.py:308`): `if pos != self.zpos` prevents emitting `positionChanged` when the position hasn't actually changed. This breaks the slider→zpos→slider loop.

4. **`inspect.stack()[1].function == 'main'` guard**: Used in ~6 combo/slider handlers to distinguish user-initiated changes from programmatic ones. Fragile but functional.

### Issues Found and Fixed (2026-02-23)

#### 1. `shared_state.add_changed_callback` Accumulation — FIXED
**File**: `src/viewers/viewerfactory.py` (PMViewer)

`PMViewer.initViewer()` called `self.shared_state.add_changed_callback(...)` every time. Unlike EMViewer/MAViewer (which only add the callback in `__init__`), PMViewer added it in `initViewer()`, which is called repeatedly from `updatePMViewers()` on tab switches, combo changes, and scale changes. Callbacks accumulated without cleanup.

**Fix**: Added `_state_callback_registered` flag in `PMViewer.__init__()`, guarding the `add_changed_callback()` call in `initViewer()` so it only registers once per viewer instance.

#### 2. No `blockSignals()` on Programmatic Widget Updates — FIXED
**Files**: `src/ui/tabs/project.py`, `src/ui/main_window.py`

When `onPositionChange()` called `self.mw.sldrZpos.setValue(self.dm.zpos)`, the slider emitted `valueChanged`, which called `setattr(self.dm, 'zpos', ...)` again. The `dm.zpos` setter guard prevented infinite recursion, but the round-trip was wasteful.

**Fix**: Added `blockSignals(True/False)` around all programmatic `setValue`/`setChecked` calls for: `sldrZpos`, `cbInclude`, `cbDefaults`, `slider1x1`, `slider2x2`, `sliderMatch`, `cbBB`, `cbClobber`. Affected methods: `onPositionChange`, `onSwimArgsChanged`, `dataUpdateMA`, `updateSlidrZpos`, `reload_zpos_slider_and_lineedit`, `_onGlobTabChange`, `disableControlPanel`.

**Gotcha**: `sldrZpos.valueChanged` had a side-effect connection (`leJump.setText(...)`) that was also suppressed by `blockSignals`. Fixed by adding explicit `self.mw.leJump.setText(str(self.dm.zpos))` in `onPositionChange()` after the blocked slider update.

#### 3. Debug Print Lambdas Connected to Signals — FIXED
**Files**: `project.py`, `main_window.py`, `snrplot.py`, `filebrowser.py`

Removed/commented ~10 debug `print()` lambdas connected to signals (`arrowLeft`, `arrowRight`, keyboard shortcuts, list widgets, group boxes, file browser, webengine load, zarrworker finished, SNR checkboxes). Converted 3 high-frequency `print(flush=True)` calls in signal handlers to `logger.debug()`.

#### 4. `QApplication.processEvents()` Re-entrancy (~25 active calls) — FIXED
**Files**: `project.py`, `manager.py`, `main_window.py`, `alignmenttable.py`

`processEvents()` dispatches all pending events synchronously. When called from within a signal handler, it can trigger other handlers before the current one finishes — causing re-entrant execution, partial state updates, and crashes.

**Categorized analysis and fixes:**

- **`viewerfactory.py` (6 calls) — LOW RISK → LEFT AS-IS**: Lines 553, 657, 813, 1046, 1178, 1279. All in viewer methods after neuroglancer transactions, giving JavaScript/WebSocket time to process state changes. Protected by `BlockStateChanges` context manager and not on hot signal chains.

- **`main_window.py` `tell()` (1 call) — MEDIUM RISK → FIXED**: Replaced `processEvents()` with `self.hud.repaint()` to force only the HUD widget to repaint without processing the full event queue.

- **`project.py` (7 calls) — HIGH RISK → FIXED**: `initNeuroglancer()` alone had 4 sequential calls. Added `_initializing_neuroglancer` re-entrancy guard flag with `try/finally`. Consolidated 4 sequential calls down to 1. Changed all calls to `ExcludeUserInputEvents`.

- **`manager.py` (9 calls) — MEDIUM-HIGH RISK → FIXED**: `updatePMViewers()` had 3 sequential calls. Added `_updating_viewers` re-entrancy guard flag with `try/finally`. Changed all calls to `ExcludeUserInputEvents` (except line 1167 after modal dialog — safe as-is).

- **`alignmenttable.py` (1 call) — HIGH RISK → FIXED**: `alignHighlighted()` loop changed to `ExcludeUserInputEvents` to allow paint/timer events but prevent user actions from modifying state mid-loop.

### Remaining Issues (Not Yet Fixed)

#### Worker `finished` Signal Cascades
**File**: `src/ui/main_window.py:1067-1077, 1147-1165`

The `_alignworker.finished` signal has ~13 connected slots including `initNeuroglancer()`, `updateTab0UI()`, `dataUpdateWidgets()`. Each fires sequentially and may trigger its own sub-cascades. Not a bug but adds unpredictability.

### Signal Connection Map (Key Files)

| File | Signal Connections | Notes |
|---|---|---|
| `main_window.py` | ~80 | Toolbar, menu, shortcuts, workers |
| `project.py` (AlignmentTab) | ~90 | Viewer signals, sliders, checkboxes, buttons |
| `manager.py` (ManagerTab) | ~40 | File watchers, combos, viewer signals |
| `viewerfactory.py` | ~5 per viewer | Neuroglancer shared_state callbacks |

### Rules for Future Signal/Slot Work

1. **Never call `add_changed_callback()` in a method that gets called multiple times** — use `__init__` or track/remove old callbacks.
2. **Use `blockSignals(True/False)` when setting widget values programmatically** to prevent wasteful signal round-trips.
3. **Avoid `QApplication.processEvents()` inside signal handlers** — it creates re-entrancy. If unavoidable, use `QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)` and add a boolean re-entrancy guard with `try/finally`.
4. **When recreating viewers, delete the old viewer AFTER clearing its webengine** — prevents JavaScript errors from accessing deleted SharedObjects.
5. **Consolidate multiple connections to the same signal** into a single handler when they should execute as a unit.
6. **The `inspect.stack()` guard pattern is fragile** — prefer `blockSignals()` or explicit boolean flags instead.
7. **When adding `blockSignals()`, audit ALL connections on that signal** — blocking suppresses every connected slot, not just the one you're targeting. E.g., `sldrZpos.valueChanged` also updated `leJump`; blocking it required adding an explicit `leJump.setText()` call.
8. **Prefer `widget.repaint()` over `processEvents()`** when the goal is just to update the display — `repaint()` paints a single widget immediately without processing the event queue.
9. **Re-entrancy guard pattern** — for methods that call `processEvents()`, use a boolean flag with `try/finally`:
```python
if self._guard_flag:
    return
self._guard_flag = True
try:
    # ... code with processEvents() ...
finally:
    self._guard_flag = False
```
