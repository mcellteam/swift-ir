# Project: SWiFT-IR

- Repository: git@github.com:mcellteam/swift-ir
- Main branch: development
- Current branch: devel_claude_pyside6

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

## TACC (Lonestar6) Launch Requirements (2026-02-25)

TACC runs RHEL8 without hardware GPU on compute nodes. The following TACC modules **must** be loaded before launching alignEM to provide software OpenGL (for neuroglancer WebGL):

```bash
module purge
ml intel/19.1.1      # Intel compiler runtime libraries
ml swr/21.2.5        # Mesa OpenSWR software rasterizer (provides OpenGL 4.5 via CPU)
ml impi/19.0.9       # Intel MPI runtime
ml fftw3/3.3.10      # FFTW libraries
```

Without these modules (especially `swr/21.2.5`), neuroglancer viewers show "Error: WebGL not supported."

### Launch with uv

Use the `tacc_launch` script which loads modules and runs via `uv`:
```bash
source tacc_launch
```

### Chromium GPU Blocklist

Even with SWR loaded, Chromium may blacklist software renderers for WebGL. `alignEM.py` sets `--ignore-gpu-blocklist` in `QTWEBENGINE_CHROMIUM_FLAGS` to prevent this. Combined with `MESA_GL_VERSION_OVERRIDE=4.5` (also set in `alignEM.py`), this allows WebGL on software OpenGL implementations.

### Legacy conda launch

The old `tacc_bootstrap` and `tacc_develop` scripts activate a conda environment (`alignTACC1024`) instead of using `uv`. They load the same four modules.

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

## PyQt5 to PySide6 Migration (2026-02-26)

Migrated from PyQt5 to PySide6. The `qtpy` abstraction layer (used in all 34 source files under `src/`) handled most API differences automatically, including ~150+ unscoped enum usages. Direct PyQt5 references only existed in 2 files.

### Dependency Changes

**`pyproject.toml`**: Removed `pyqt5>=5.15.11`, `pyqtwebengine>=5.15.7`, `pyqtwebengine-qt5`. Added `PySide6>=6.7.0` (bundles all Qt modules including WebEngine). Libraries `qtpy`, `pyqtgraph`, `qtconsole`, `qtawesome` are all PySide6-compatible and unchanged.

### Files Changed (21 files, ~200 lines)

| File | Changes |
|---|---|
| `pyproject.toml` | PyQt5 → PySide6 dependency |
| `alignEM.py` | Plugin path, env vars, `AA_UseDesktopOpenGL` removal, `--use-angle=gl` (macOS), shutdown cleanup |
| `src/resources/icons_rc.py` | `from PyQt5 import QtCore` → `from qtpy import QtCore` |
| `src/ui/main_window.py` | `exec_()`, `PluginsEnabled` removal, `QImageReader.setAllocationLimit(0)`, `hud.update()`, QPainter, init guards |
| `src/ui/tabs/manager.py` | `exec_()`, `PluginsEnabled`, `QUrl.fromLocalFile(None)` guards, `QLabel.setAlignment` chaining, QPainter, alignment combo persistence |
| `src/ui/tabs/project.py` | `setCheckState` enums, `Qt.KeyboardModifier`, `PluginsEnabled`, `exec_()`, `super()` fix, init guards, QPainter |
| `src/models/jsontree.py` | `QModelIndex.child()` removal, `self.parent` → `self._parent_widget` |
| `src/ui/views/thumbnail.py` | `drawLines` → `drawLine`, `QFont.Weight` enum, `pixmap().fill()` semantics, QPainter lifecycle |
| `src/ui/widgets/clickable.py` | QPainter `end()`, double-self fix |
| `src/ui/views/alignmenttable.py` | `exec_()`, QPainter |
| `src/viewers/viewerfactory.py` | Graceful dm-None handling, log message fix |
| 8 other files | `exec_()` → `exec()` |
| `tacc_launch`, `tacc_bootstrap` | `QT_API=pyside6` |

### PySide6 Compatibility Issues Found

These are the key behavioral differences between PyQt5 and PySide6 that required code changes:

#### 1. Strict type checking — `None` rejected for typed parameters
PySide6 raises `TypeError` where PyQt5 silently accepted `None`. Example: `QUrl.fromLocalFile(None)` crashes. Guard with `if os.getenv('VAR'):` checks.

#### 2. `exec_()` alias removed
PySide6 only provides `exec()`. Changed in 10 files (12 call sites).

#### 3. `QModelIndex.child()` removed in Qt6
Replace `index.child(row, col)` with `model.index(row, col, parent_index)`.

#### 4. `QObject.parent()` method shadowing
Storing `self.parent = widget` on a QObject subclass shadows the C++ `parent()` method. PySide6 calls `parent()` internally and gets the stored widget instead. Rename to `self._parent_widget`.

#### 5. Integer enums rejected — scoped enums required
`setCheckState(2)` → `setCheckState(Qt.CheckState.Checked)`, `QFont.setWeight(10)` → `setWeight(QFont.Weight.Thin)`, `Qt.KeyboardModifiers()` → `Qt.KeyboardModifier(0)`.

#### 6. QPainter must be explicitly ended
PySide6 crashes (`QBackingStore::endPaint()`) if QPainter is not ended before `paintEvent` returns. PyQt5 handled this silently via destructor. Fix: always call `qp.end()` in a `try/finally` block. Also: never call `setPixmap()` or `repaint()` while a QPainter is active.

#### 7. `QLabel.pixmap()` returns a copy
In PyQt5, `self.pixmap()` returns a reference to the internal pixmap. In PySide6, it returns a copy. So `self.pixmap().fill(color)` fills a temporary and has no visible effect. Fix: create a new `QPixmap`, fill it, then `setPixmap()`.

#### 8. `QLabel.setAlignment()` returns `None`
Chaining `QLabel("x:").setAlignment(Qt.AlignRight)` assigns `None` to the variable. Split into two lines.

#### 9. `super()` class argument validation
`super(QListWidget, self).__init__()` where class is actually a subclass of `QListWidget` fails in PySide6. Use `super().__init__()`.

#### 10. Signals fire during widget construction
PySide6 emits `visibilityChanged`, `currentChanged`, etc. during widget setup before all attributes exist. Guard with `if not hasattr(self, 'attr'): return`.

#### 11. Qt6 API removals
- `QWebEngineSettings.PluginsEnabled` — removed (NPAPI dead). Delete the lines.
- `Qt.AA_UseDesktopOpenGL` — removed (desktop GL is default in Qt6). Delete.
- `QApplication.exec_()` — see #2.

#### 12. Metal ANGLE backend on macOS
Qt6 WebEngine uses Metal by default on macOS, causing XPC connection errors. Fix: add `--use-angle=gl` to `QTWEBENGINE_CHROMIUM_FLAGS` (macOS only, via `sys.platform == 'darwin'` check).

#### 13. `widget.repaint()` can crash during active paint cycle
PySide6 is stricter about synchronous `repaint()` during signal cascades. Use `widget.update()` (async) instead.

### Shutdown Cleanup

PySide6/Shiboken destroys C++ objects in unpredictable order during garbage collection, causing segfaults on exit. Fix in `alignEM.py`:
```python
_app = QApplication.instance()
ret = _app.exec()
del cfg.mw          # Explicitly destroy main window
cfg.main_window = None
del _app            # Then destroy QApplication
sys.exit(ret)
```

### Alignment Combo Persistence

Added persistence for the most recently selected alignment file in the Alignment Manager:
- `onComboTransformed()` saves `cfg.preferences['alignment_combo_text']` when user selects an alignment
- `loadAlignmentCombo()` restores the combo text from preferences on startup
- `updateCombos()` loads the DataModel and calls `updatePMViewers()` to display both viewers

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
- `_alignworker.finished` / `_zarrworker.finished` / `_scaleworker.finished` — consolidated into single handlers (`_onAlignmentComplete`, `_onZarrComplete`, `_onScaleComplete`)

### Existing Safeguards (Good Patterns)

1. **`BlockStateChanges` context manager** (`viewerfactory.py:136`): Prevents re-entrant `on_state_changed()` callbacks in all viewer types. Always use this when modifying neuroglancer state programmatically.

2. **`_position_change_in_progress` guard** (`project.py:85`): Prevents re-entrant position change handling. The consolidated handler (`_onPositionChangeConsolidated`) wraps `onPositionChange` + `updateDwMatches` + `updateDwThumbs` in a single guarded call.

3. **`dm.zpos` setter guard** (`data.py:308`): `if pos != self.zpos` prevents emitting `positionChanged` when the position hasn't actually changed. This breaks the slider→zpos→slider loop.

4. **`inspect.stack()` guards — REMOVED** (2026-02-23): Previously used in ~20 handlers to distinguish user-initiated from programmatic changes. All removed and replaced with proper `blockSignals()` at call sites or eliminated entirely (for user-only signals). See "inspect.stack() Guard Removal" section below.

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

#### 5. Worker `finished` Signal Cascades — FIXED
**File**: `src/ui/main_window.py`

The three background workers (`_alignworker`, `_zarrworker`, `_scaleworker`) each connected 7-10 individual slots to their `finished` signal via separate `.connect()` calls. The `_working` flag was initialized to `False` but never set to `True`, making all 8 guard conditions ineffective.

**Fix**: Consolidated each worker's cascade into a single handler method (`_onAlignmentComplete`, `_onZarrComplete`, `_onScaleComplete`). Each handler sets `_working = False` first (so `initNeuroglancer()` and `_refresh()` aren't blocked), then performs all completion actions in explicit order. Added `self._working = True` in `regenZarr()`, `align()`, and `autoscaleImages()` before worker start. Added `_working` guard to `regenZarr()` (previously unprotected). SNR plot tab check is now evaluated at completion time instead of connection time.

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
6. **Never use `inspect.stack()` for signal/slot guards** — all such guards were removed. Use `blockSignals()` at programmatic call sites or rely on user-only signals (`activated`, `textActivated`, `triggered`, `sliderReleased`, `returnPressed`, `textEdited`, `buttonClicked`).
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

### Follow-up Signal/Slot Audit (2026-02-23)

Investigated 4 additional potential signal/slot issues. Analysis of Qt signal semantics revealed 2 false positives and 2 minor improvements:

#### Issues Investigated

| # | Claim | Verdict | Reason |
|---|---|---|---|
| 1 | Missing `blockSignals` on `cbxViewerScale`/`cbxNgLayout` | **False positive** | `cbxViewerScale` signal is commented out; `cbxNgLayout` uses `activated` (user-only, not emitted by programmatic changes) |
| 2 | Missing `blockSignals` on QAction colorActions | **False positive** | `setChecked()` emits `toggled`, not `triggered`; no `toggled` connections exist on these actions |
| 3 | Missing `blockSignals` on manager.py combos | **Partially real** | `comboImages`/`comboTransformed` use `textActivated` (user-only, safe); only `comboLevel` uses `currentIndexChanged` (fires on `clear()`/`addItems()`/`setCurrentIndex()`). Fixed by `blockSignals` in `loadLevelsCombo()` |
| 4 | Repeated signal connections on viewer1 | **False positive for accumulation** | New viewer = new `WorkerSignals` QObject = fresh connections. Old viewer cleaned up by `del`. But 4-line connection block duplicated in 3 places |

#### Fixes Applied

1. **`loadLevelsCombo()` — added `blockSignals()`**: Wraps the `comboLevel.clear()` / `addItems()` / `setCurrentIndex()` sequence in `blockSignals(True/False)` to prevent spurious `currentIndexChanged` emissions. The `inspect.stack()` guard in `onComboLevel` has been removed since `blockSignals` provides the proper protection.

2. **Extracted `_connectViewerSignals()` helper**: The identical 4-line arrow key signal connection block (arrowLeft/Right/Up/Down) appeared in 3 places in `manager.py`. Extracted to `_connectViewerSignals(viewer)` method and replaced all 3 occurrences.

#### Qt Signal Semantics Reference

| Signal | Emitted by programmatic changes? | Notes |
|---|---|---|
| `QComboBox.activated` / `textActivated` | No | User-only; safe without `blockSignals` |
| `QComboBox.currentIndexChanged` | Yes | Fires on `clear()`, `addItems()`, `setCurrentIndex()` |
| `QAction.triggered` | No | User-only; safe without `blockSignals` |
| `QAction.toggled` | Yes | Fires on `setChecked()` |
| `QSlider.sliderReleased` | No | User-only; safe without `blockSignals` |
| `QSlider.valueChanged` | Yes | Fires on `setValue()` |
| `QLineEdit.returnPressed` / `textEdited` | No | User-only; safe without `blockSignals` |
| `QLineEdit.selectionChanged` | No | User-only; safe without `blockSignals` |
| `QButtonGroup.buttonClicked` | No | User-only; safe without `blockSignals` |
| `QCheckBox.stateChanged` / `toggled` | Yes | Fires on `setChecked()` |
| `QTabWidget.currentChanged` | Yes | Fires on `setCurrentIndex()` |

### inspect.stack() Guard Removal (2026-02-23)

Removed all `inspect.stack()[1].function == 'main'` guards (~20 active instances) and the `import inspect` from both `manager.py` and `project.py`. The pattern was fragile (broke silently if call chains were refactored) and has been replaced with proper Qt patterns.

#### Category A: Logging-only (removed caller tracing)

These only used `inspect.stack()` for log messages. Simplified the log lines.

| File | Function |
|---|---|
| `manager.py` | `updateCombos`, `validate_project_selection`, `WebEngine.setnull` |
| `project.py` | `_onTabChange`, `refreshTab`, `initNeuroglancer`, `fn_leMatch`, `set_transforming`, `_updatePointLists`, `slotUpdateZoomSlider` |

#### Category B: User-only signals (guard was dead logic)

These handlers are connected to signals that never fire on programmatic changes. The guard was unnecessary — removed it, kept the body.

| File | Function | Signal |
|---|---|---|
| `manager.py` | `onComboSelectEmstack` | `textActivated` |
| `manager.py` | `onComboTransformed` | `textActivated` |
| `project.py` | `fn` (bgManualRBs) | `buttonClicked` |
| `project.py` | `fn` (leSwimWindow) | `returnPressed` + `selectionChanged` |
| `project.py` | `fn_cmbViewerScale` | Signal commented out (dead code) |
| `project.py` | `onNgLayoutCombobox` | `activated` |
| `project.py` | `setZoomSlider` | Dead code (never called) |
| `project.py` | `onZoomSlider` | `sliderReleased` |
| `project.py` | `fn_brightness_control` | `sliderReleased` + `textEdited` |
| `project.py` | `fn_contrast_control` | `sliderReleased` + `textEdited` |

#### Category C: Added blockSignals at call sites

These handlers are connected to signals that fire on programmatic changes. Added `blockSignals(True/False)` at the programmatic call sites, then removed the guard.

| Function | Signal | New blockSignals location |
|---|---|---|
| `onComboLevel` (manager.py) | `currentIndexChanged` | Already had `blockSignals` in `loadLevelsCombo()` — just removed guard |
| `onIncludeExcludeToggle` | `stateChanged` | Already had `blockSignals` in `onPositionChange`/`onSwimArgsChanged` — just removed guard |
| `onDefaultsCheckbox` | `toggled` | Already had `blockSignals` in `onSwimArgsChanged`/`dataUpdateMA` — just removed guard |
| `fn_method_select` | `currentChanged` | Added `blockSignals` around `twMethod.setCurrentIndex()` in `dataUpdateMA()` (2 sites) |
| `fn_cb_transformed` | `toggled` | Added `blockSignals` around `cbTransformed.setChecked()` after `connect()` |
| `cb_itemChanged` | `model().itemChanged` | No active programmatic triggers — just removed guard |
| `onBiasChanged` | `currentIndexChanged` | No active programmatic triggers (all call sites commented out) — just removed guard |
| `fn_sliderMatch` | `valueChanged` | Added `blockSignals` around internal `sliderMatch.setValue()` to prevent self-triggering |
| `fn_slider1x1` | `valueChanged` | Added `blockSignals` around `slider1x1.setValue()` and `slider2x2.setValue()` cross-calls |
| `fn_slider2x2` | `valueChanged` | Added `blockSignals` around `slider2x2.setValue()` self-correction |

## Bug Fix: Clobber Size Field Ignored (2026-03-04)

**File**: `src/ui/tabs/project.py`, line 873

The clobber "size" line edit (`leClobber`) passed its value as a string to `dm.set_clobber_px()`, which guards with `isinstance(x, int)`. The string silently failed the check, so edits to the clobber size were never stored in the data model — the "Apply to All" button stayed disabled and alignments used the old value.

**Fix**: Convert to `int()` in the `textEdited` lambda, with an empty-string guard (since `textEdited` fires on every keystroke):
```python
self.leClobber.textEdited.connect(lambda: self.dm.set_clobber_px(x=int(self.leClobber.text())) if self.leClobber.text() else None)
```

## Replace Image in Emstack (2026-03-04)

Added the ability to replace a single image in an existing emstack without rebuilding the entire stack and alignment from scratch. Accessible via right-click context menu in the alignment Table tab.

### Constraints

- **Same dimensions required**: The replacement image must match the original image's width and height. This avoids cascading updates to `size_xy`, `size_zyx`, swim windows, and zarr array shapes.
- **Synchronous operation**: Rescaling a single image across a few levels is fast (seconds), so no background worker is needed.
- **Old filename preserved on disk**: The new image is copied into the emstack under the original filename, so all path references in the DataModel remain valid. The new source path is recorded in `info.json`'s `paths[]` for provenance.

### Files Changed

| File | Changes |
|---|---|
| `src/workers/scale.py` | New `replace_single_image()` module-level function |
| `src/models/data.py` | New `_reset_section_results()` and `replace_image()` methods on `DataModel` |
| `src/ui/views/alignmenttable.py` | "Replace Image..." context menu action + `replaceImage()` handler |

### How It Works

1. **UI** (`alignmenttable.py`): Right-click a single row in the Table tab → "Replace Image [N] filename..." → file dialog (TIFF only) → dimension validation → confirmation dialog (with warning if stack is already aligned) → executes replacement.

2. **Orchestration** (`data.py:replace_image()`):
   - Validates new image dimensions match `images['size_xy']['s1']`
   - Reads emstack `info.json` for `scale_factors` and `thumbnail_scale_factor`
   - Calls `replace_single_image()` for on-disk updates
   - Updates in-memory `images['paths'][index]`
   - Finds affected sections: the replaced index + any section whose `reference_index` points to it
   - Invalidates hash table cache entries (`ht.remove()`) for affected sections so `needsAlignIndexes()` correctly flags them for re-alignment
   - If aligned: resets alignment results (`_reset_section_results()`) for affected sections and recomputes cumulative affines (`set_stack_cafm()`)
   - Saves and emits `positionChanged` to refresh viewers

3. **Disk updates** (`scale.py:replace_single_image()`):
   - Runs `iscale2` to rescale the new source image at each scale level → `tiff/s{N}/{old_name}`
   - Updates the corresponding zarr slice (`store[:, :, index] = im.transpose()`) at each level
   - Regenerates the thumbnail via `iscale2` at `thumbnail_scale_factor`
   - Updates `info.json` `paths[index]` on disk

### Cache Invalidation Strategy

After replacement, cache entries are removed (not just invalidated) for:
- The replaced section at all levels
- Any section at any level whose `swim_settings['reference_index']` points to the replaced index (typically the next section, but can skip further if sections are excluded)

This ensures `needsAlignIndexes()` returns these sections, prompting the user to re-align them.

## Memory-Aware Worker Parallelism (2026-03-05)

Replaced the fixed `physical_cores - 2` worker count with a memory-aware computation that prevents RAM exhaustion and thrashing when aligning large images (e.g., 300 images at 24k×24k).

### Problem

The old `get_core_count()` used `psutil.cpu_count(logical=False) - 2` workers regardless of image size, scale, or available RAM. For 24k×24k images at scale s1, each swim subprocess allocates ~4.6 GB (window buffers + source images). With 14 workers that demands ~64 GB — fine on 128 GB machines but causes severe thrashing on 64 GB systems.

### swim Memory Model (from swim.c analysis)

swim.c allocates per invocation:
- 4 float buffers: 16 × W × H bytes (window size)
- 4 FFT complex buffers: ~16 × W × H bytes (`sizeof(fftwf_complex)` = 8 bytes, single-precision)
- 3 image structs: 3 × W × H bytes
- 2 full source images via `read_img()`: 2 × img_w × img_h bytes

Total: **35 × W × H + 2 × img_w × img_h** bytes, where W,H = swim window dimensions.

**History**: Prior to 2026-03-11, the FFT buffers used `sizeof(fftw_complex)` (double-precision, 16 bytes) instead of `sizeof(fftwf_complex)` (8 bytes), doubling FFT buffer allocations for a total of 51 bytes/pixel. Fixed in swim.c and `_SWIM_BYTES_PER_WINDOW_PIXEL` updated from 51 to 35.

### Recipe-Aware Window Sizing

The alignment recipe uses different window sizes depending on the scale:
- **Coarsest scale** (`is_refinement=False`): 1×1 ingredient uses `size_1x1` (81.25% of image), then 2×2 ingredients use `size_2x2` (half of that). Peak = `size_1x1`.
- **Finer scales** (`is_refinement=True`): Only 2×2 ingredients are used. Peak = `size_2x2`.

For 24k×24k images: at s1 the peak window is 9750² (2×2 only), not 19500² (1×1).

### New Functions

**`src/utils/helpers.py`**:

- **`estimate_swim_memory(img_size, max_window)`**: Returns estimated bytes per alignment worker (Python overhead + swim subprocess memory).
- **`compute_worker_count(n_tasks, per_worker_bytes, use_threads=False)`**: Returns optimal worker count, capped at `min(physical_cores - 2, available_RAM × 0.70 / per_worker, n_tasks, TACC_MAX_CPUS)`.

### Files Changed

| File | Changes |
|---|---|
| `src/utils/helpers.py` | New `estimate_swim_memory()` and `compute_worker_count()` functions |
| `src/workers/align.py` | Scans tasks for max window size, uses memory-aware count. HUD shows window size and GB/worker |
| `src/workers/generate.py` | Memory-aware count for both run_mir and convert_zarr_block phases |
| `src/workers/scale.py` | Memory-aware count for both iscale2 TIFF reduction and zarr conversion phases |

### How It Works

1. **AlignWorker** (`align.py`): After building the task list, scans all tasks' `method_opts` for the actual largest window size (respecting `is_refinement`). Passes this to `estimate_swim_memory()` and `compute_worker_count()`.

2. **ZarrWorker** (`generate.py`): Estimates per-worker memory for the `run_mir` phase (input image + bounding box output) and `convert_zarr_block` phase (TIFF read + zarr write) separately.

3. **ScaleWorker** (`scale.py`): Estimates per-thread memory for `iscale2` (source image + scaled output) and zarr conversion (2× scaled image). Uses `use_threads=True` since ThreadPoolExecutor shares the Python process.

### Backward Compatibility

- `get_core_count()` preserved in helpers.py (referenced by TACC UI widget in `main_window.py:2260`)
- `SCALE_1_CORES_LIMIT` and `SCALE_2_CORES_LIMIT` kept in `config.py` (UI references) but no longer used by workers

### Bug Fix: zip Iterator Exhaustion in ScaleWorker (2026-03-05)

`main_window.py:1159` passes `scales` as a `zip()` iterator to `ScaleWorker.__init__()`. The new `max(self.scales, ...)` call in `run()` consumed the entire iterator, leaving all subsequent `for s, siz in deepcopy(self.scales):` loops empty — no TIFFs were generated and thumbnails failed with `FileNotFoundError`. Fixed by materializing with `list(scales)` in `__init__`.

## Emstack Creation UI Fixes (2026-03-06)

### Viewer Shows Stale Content During Creation

When clicking "+" to create a new emstack, the viewer continued showing the previous stack's content. Three fixes:

1. **Blank viewer on "+" click** (`manager.py:onPlusEmstack`): Added `self.webengine0.setnull()` when the create panel opens.

2. **Don't exit create panel prematurely** (`manager.py:confirmCreateImages`): Removed the immediate `resetView(init_viewer=True)` call after launching the background worker. The viewer stays blank until `_onScaleComplete` calls `resetView(init_viewer=True)` when the worker finishes.

3. **Skip viewer init while worker is active** (`manager.py:updateCombos`): The `QFileSystemWatcher` fires when the new `.emstack` directory is created, triggering `updateCombos()` → `updatePMViewers()` which tried to open the incomplete zarr. Added `self.parent._working` guard to skip `updatePMViewers()` during background work.

### Thumbnails Not Generated (fire-and-forget Popen)

`thumbnailer.py:run_subprocess()` used `sp.Popen()` which spawns iscale2 and returns immediately without waiting. The `pool.map` completed instantly (~300k it/s), then the metadata rewrite loop failed with `FileNotFoundError` because iscale2 hadn't finished writing yet. Fixed by replacing `sp.Popen()` with `sp.run()` which waits for completion.

## Content Roots and Preferences Cleanup (2026-03-09)

### Content Roots Architecture

Replaced the old single `content_root` + manual search path configuration with a `content_roots` list — an ordered list of `alignem_data` directories. Each root contains `images/` and `alignments/` subdirectories, which are inferred automatically (not user-configurable).

**Key design:**
- `content_roots` is the single source of truth, persisted in `~/.swiftrc`
- `images_root`, `alignments_root`, `images_search_paths`, `alignments_search_paths` are derived at runtime from `content_roots` and NOT persisted
- The default root is `~/alignem_data` (or `$SCRATCH/alignem_data` on TACC)
- New roots are added via a combo + "Browse..." button in the emstack creation panel
- The browse dialog auto-appends `alignem_data` to the selected path if not already present

### Files Changed

| File | Changes |
|---|---|
| `src/utils/helpers.py` | New `derive_search_paths()` function; `content_roots` list with migration from old `content_root`; strip legacy keys on load; strip runtime keys on save; removed dead `cleanup_project_list()`, `convert_projects_model()`, `configure_project_paths()` |
| `src/core/files.py` | `DirectoryWatcher._loadSearchPaths()` re-reads from preferences each time (fixes stale reference); `clearWatches()` cleaned up |
| `src/ui/tabs/manager.py` | Content root combo + browse button in creation panel; `_addContentRoot()`, `_syncContentRoots()`, `_getAlignmentsRootForEmstack()` helpers; `_updateWatchPaths()` clears old watches; `_onCancelCreate()` properly resets both panels; removed Panel 3 (FileBrowser) and all dead code (`open_zarr_selected`, `deleteContextMethod`, `delete_projects`, `validate_zarr_selection`); removed `FileBrowser`, `ZarrTab`, `HSplitter` imports |
| `src/ui/main_window.py` | `saveUserPreferences()` strips runtime-only keys before writing; `_onScaleComplete()` calls `updateCombos()` so new emstack appears in combo; `_RUNTIME_ONLY_KEYS` class constant |
| `alignEM.py` | Removed `convert_projects_model` import and call |

### .swiftrc Schema (Clean)

**Persisted keys:**

| Key | Purpose |
|---|---|
| `neuroglancer` | Viewer display settings |
| `gif_speed` | GIF playback speed |
| `images_combo_text` | Last selected emstack path |
| `alignment_combo_text` | Last selected alignment path |
| `notes` | Global notes dictionary |
| `content_roots` | List of `alignem_data` directory paths |
| `last_alignment_opened` | Auto-load on restart |

**Runtime-only keys** (derived from `content_roots`, not saved):

| Key | Derivation |
|---|---|
| `images_root` | `content_roots[0] + '/images'` |
| `alignments_root` | `content_roots[0] + '/alignments'` |
| `images_search_paths` | `[root + '/images' for root in content_roots]` |
| `alignments_search_paths` | `[root + '/alignments' for root in content_roots]` |

**Removed keys** (stripped from old files on load):
`locations`, `alignments`, `content_root`, `saved_paths`, `current_filebrowser_root`, `previous_filebrowser_root`, `projects`

### Panel 3 (File Browser) Removal

The File Browser panel and its "Set Content Sources" UI have been fully removed from the Alignment Manager tab. Content root management is now integrated into the emstack creation panel. The `filebrowser.py` file remains on disk but is no longer imported anywhere.

### Alignment Creation Uses Matching Content Root

When creating an alignment, `_getAlignmentsRootForEmstack()` finds the content root that contains the selected emstack's `images/` directory and uses its `alignments/` directory. This ensures emstacks and their alignments stay in the same content root. Falls back to `alignments_root` (first content root) if no match is found.

## Alignment Manager Viewer Fixes (2026-03-11)

### Double-Image Bug in Alignment Preview

The Alignment Manager's viewer1 (aligned preview) sometimes displayed two images on top of each other instead of one. Two fixes applied:

#### 1. Z-Position Voxel Boundary Fix (`viewerfactory.py`)

**Root cause**: `PMViewer.initViewer()` set the z-position to `tensor.shape[2] / 2`, which for even slice counts lands exactly on an integer voxel boundary. With `add_transformation_layers` (one LocalVolume per slice), neuroglancer renders both the voxel ending at that boundary and the voxel starting there, producing two overlapping images with two bounding box frames.

**Fix**: Changed to `tensor.shape[2] // 2 + 0.5` to land at voxel centers, matching the `EMViewer.set_layer` pattern (`pos + 0.5`).

**Rule**: Always use `+ 0.5` offset for z-positions when using per-slice transformation layers. Integer z values fall on voxel boundaries in neuroglancer.

#### 2. Stale Timer Callback Prevention (`manager.py` WebEngine class)

**Problem**: The delayed layer creation mechanism (`setOnLoadCallback` → `loadFinished` → 500ms QTimer) could leave orphaned timer callbacks. When a new viewer setup occurred before an old timer fired, `setnull()` cleared `_on_load_callback` but could not cancel the already-scheduled QTimer. The stale timer would then execute on the new viewer.

**Fix**: Added a `_callback_generation` counter to the `WebEngine` class. Each call to `setOnLoadCallback()` or `setnull()` increments the counter. When a timer fires, it checks if its captured generation matches the current generation — if not, the callback is stale and is skipped. Log message: `"Skipping stale callback (gen=X, current=Y)"`.

### Preference Unification: `last_alignment_opened` → `alignment_combo_text`

**Problem**: Two preference keys tracked the last-opened alignment: `last_alignment_opened` (written by `project.py:AlignmentTab.__init__` and `manager.py:openAlignment`) and `alignment_combo_text` (written by `manager.py:onComboTransformed` and read by `loadAlignmentCombo()`). The `last_alignment_opened` key was dead code — written in 2 places but never read. When the user opened an alignment from the Project tab, only `last_alignment_opened` was updated, leaving `alignment_combo_text` stale. On restart, `loadAlignmentCombo()` tried to restore from the stale `alignment_combo_text`, failed to match, and the viewer showed "Neuroglancer: No Data".

**Fix**: Unified to `alignment_combo_text` as the single key:
- `project.py:50`: `AlignmentTab.__init__` now writes `alignment_combo_text`
- `manager.py:1126`: `openAlignment()` now writes `alignment_combo_text`
- `helpers.py:317-319`: `last_alignment_opened` added to legacy key stripping list (removed from old `.swiftrc` files on load)

## Deterministic Cache Hashing Fix (2026-03-11)

### Problem

After quitting and reopening the app, the alignment result cache failed to find any previously computed results. The match signal panel showed "No Image" / "No Signal" for every section, and clicking "Align" re-ran all tasks instead of recognizing cached results via swim_settings hash lookup.

### Root Causes (Two Issues)

1. **PYTHONHASHSEED randomization**: `HashableDict.__hash__()` used Python's `hash(str(...))` which is randomized per process. Cache keys changed on restart, causing universal cache misses.

2. **numpy type mismatch**: `getMethodPresets()` (`data.py:2008-2014`) computed grid coordinates with numpy operations, producing `(np.float64(304.0), np.float64(304.0))` tuples. These were stored in the cache pickle with numpy types. When the same swim_settings were loaded from JSON (which round-trips to `[304.0, 304.0]` plain float lists), both `str()` representations and `==` comparisons differed, so cache lookups failed even within the same session.

### Fix

1. **Deterministic hashing** (`data.py:HashableDict.__hash__`, `HashableList.__hash__`): Replaced `ctypes.c_size_t(hash(str(...))).value` with `int(hashlib.sha256(s).hexdigest(), 16) % (2**64)`. SHA-256 is deterministic across sessions, platforms, and Python versions.

2. **Type normalization** (`data.py:_normalize()`): Recursive function that converts numpy scalars → Python float/int, tuples → lists, numpy arrays → lists. Used in `HashableDict.__hash__()` before computing the hash string, ensuring consistent hashes regardless of data source.

3. **Source fix** (`data.py:getMethodPresets()`): Grid coordinates now explicitly use `float()` and `[]` lists instead of numpy float64 tuples, preventing the type mismatch at the source.

4. **Cache migration** (`cache.py:_migrate_hash_keys()`): On `unpickle()`, normalizes all cached keys (removing numpy types) and re-keys the dict with deterministic hashes. Saves the migrated cache immediately so migration only happens once.

5. **Data directory migration** (two-phase):
   - **Primary** (`cache.py:_rename_data_dirs()`): Runs atomically with cache re-keying, using precise `old_hash → new_hash` mappings from the cache entries. Correctly handles multiple hash directories per section (from alignments with different swim_settings), since each old hash maps to exactly one swim_settings → one new hash.
   - **Recovery fallback** (`data.py:_migrate_data_dirs()`): For cases where the cache was already migrated but directories weren't renamed. Only renames single-directory sections (safe). Skips multi-directory sections with a warning (hash is not invertible — can't determine which directory matches which swim_settings).

### Files Changed

| File | Changes |
|---|---|
| `src/models/data.py` | `_normalize()`, `_migrate_data_dirs()`; `HashableDict.__hash__`/`HashableList.__hash__`: SHA-256 + normalization; `getMethodPresets()`: plain Python types for grid coords |
| `src/models/cache.py` | `_migrate_hash_keys()` method; called from `unpickle()` after loading old cache |

### Rules

1. **Never use Python's `hash()` for values that persist across sessions.** Use `hashlib` (SHA-256, etc.) for any hash stored to disk.
2. **Never store numpy types in data structures that will be serialized.** Convert to plain Python types (`float()`, `int()`, `list()`) before storing. JSON round-trips lose numpy types silently, breaking equality comparisons.
3. **`ssHash()` is used in file paths** — the hash of swim_settings determines the data directory name for signal/match files. Any change to the hash function requires migrating existing directories.

## Match Signal Display on Project Open (2026-03-11)

**Problem**: After opening a saved project, the match signal panel intermittently showed "No Image" / "No Signal" for the restored position. Navigating away and back displayed them correctly.

**Root cause**: `_onGlobTabChange()` in `main_window.py` set up the match dock widget (`dwMatches.setWidget(match_widget)`) but never called `updateDwMatches()`. The match display only populated when `positionChanged` fired — but the saved position was already loaded (no change = no signal emission). The intermittency came from neuroglancer's `on_state_changed` callback sometimes accidentally triggering a position change during viewer initialization.

**Fix**: Added `self.updateDwMatches()` call in `_onGlobTabChange()` after the dock widget is set up (`main_window.py:3004`).

**Rule**: When setting up dock widget content during tab switches, always explicitly populate the display — don't rely on signals that may or may not fire during initialization.
