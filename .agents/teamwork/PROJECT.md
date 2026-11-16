# Project: GandalfHardcore Hell Asset Pack 32x32 Backend & Preview Restoration

## Architecture
The asset and preview pipeline spans five key layers:
1. **Filesystem & OS Security Layer**: NTFS DACLs on `assets/graphics/GandalfHardcore Hell Asset Pack 32x32`.
2. **Offline Slicing & Utility Layer**: `split_spritesheet.py` generating `_frames/` and `config.json` metadata sidecars.
3. **Core Engine Asset Layer**: `v3x_zulfiqar_gideon.AssetManager` texture caching, animation frame extraction, and heuristic slicing.
4. **Editor & Plugin UI Layer**: `level_editor.py` (`SpritesheetSlicerModal`, `AssetBrowserModal`, `_load_preview`), `boss_editor.py`, and `wizard_editor.py`.
5. **Runtime Game Systems Layer**: `EnvironmentProp` in `src/game/systems/environment_manager.py` and level configurations (`game_data/level_1.json`, `game_data/level_2.json`).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Filesystem ACL Restoration | Restore open read/execute/write permissions on all 51 files and 36 directories in `GandalfHardcore Hell Asset Pack 32x32` | M1 | Survey |
| 2 | Slicing Engine 2D Grid Detection | Enhance `split_spritesheet.py` with `(\d+)x(\d+)` filename parsing, Hell pack grid definitions, and 2D grid heuristics | M2 | Survey |
| 3 | AssetManager Slicing & Directory Heuristics | Enhance `AssetManager._load_frames_from_image_file` to support 2D grids, fix sidecar `config.json` collision, and prevent multi-sheet folder collapse in `get_animation_frames` | M2 | Survey |
| 4 | Hell Pack Sidecar & Frame Generation | Generate clean `_frames` directories and valid `config.json` sidecars for all 2D sheets and tilesets in the Hell pack | M2 | Survey |
| 5 | Editor Slicer Modal Filter Unblocking | Remove `"blood"` and `"skeleton"` keyword exclusions from `SpritesheetSlicerModal` in `level_editor.py` | M3 | Survey |
| 6 | Asset Browser Catalog Entity Indexing | Update `AssetBrowserModal._discover_catalog()` in `level_editor.py` to index individual entity sheets rather than folder-only entries | M3 | Survey |
| 7 | Preview Scaling & Container Fitting | Update `_load_preview` in `level_editor.py` to use aspect-ratio auto-fitting rather than raw 2.0x scale clipping | M3 | Survey |
| 8 | Runtime Prop & Parallax Registry | Register `Memento Mori Skeleton` in `EnvironmentProp.SPRITESHEET_GRIDS` and update `level_1.json` / `level_2.json` parallax references | M3 | Survey |
| 9 | Opaque-Box E2E Test Suite | Comprehensive E2E test suite covering Tiers 1-4 for asset loading, backend health, and preview rendering | M4 | Survey / E2E Track |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Asset Permissions & Filesystem Integrity | Fix ACLs on `assets/graphics/GandalfHardcore Hell Asset Pack 32x32` | none | PLANNED |
| 2 | Backend Loading & Slicing Engine | Update `split_spritesheet.py`, `AssetManager`, and generate valid `_frames/config.json` | M1 | PLANNED |
| 3 | Editor Preview & Runtime Integration | Update `level_editor.py`, `environment_manager.py`, and level configs | M2 | PLANNED |
| 4 | Final E2E Test Pass & Hardening | Pass 100% of E2E tests and perform adversarial coverage hardening | M3 | PLANNED |

## Interface Contracts
### `AssetManager.get_animation_frames(target_path, ...)`
- **Input**: `target_path` pointing to either an image file (`.png`), a sliced frames directory (`_frames/`), or a directory of individual animation frames.
- **Output**: `list[pygame.Surface]` where every surface is a valid individual frame with genuine pixel dimensions. Never returns empty list on existing valid assets, and never returns single monolithic surface when grid/config defines multiple frames.
- **Error Handling**: Catches missing paths gracefully, logs informative errors, but does not crash or raise unhandled exceptions.

### `split_spritesheet.py` CLI & API
- **Input**: `--input <path>`, optional `--cols`, `--rows`, `--frame-width`, `--frame-height`, or auto-detection via `(\d+)x(\d+)` pattern and known grids.
- **Output**: `<name>_frames/` directory containing sliced `frame_NNN.png` files and `config.json` with correct `cols`, `rows`, `frame_width`, `frame_height`, `total_frames`.

### `level_editor._load_preview(path, scale=2.0)`
- **Input**: Asset path (`str`).
- **Output**: `list[pygame.Surface]` scaled to fit within preview UI bounds without exceeding container boundaries.
