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
