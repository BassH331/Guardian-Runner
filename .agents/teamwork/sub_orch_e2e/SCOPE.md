# Scope: E2E Testing Track — Guardian-Runner

## Architecture
The E2E Test Suite provides opaque-box, requirement-driven verification for the loading, parsing, previewing, and runtime integration of assets from `assets/graphics/GandalfHardcore Hell Asset Pack 32x32`.
The test suite resides in `tests/e2e/` and runs headlessly under `pytest`.

Key Subsystems under Test:
1. `v3x_zulfiqar_gideon.AssetManager`: `get_texture`, `get_animation_frames`, `slice_spritesheet`, `_load_frames_from_image_file`.
2. `level_editor`: `_load_preview`, `AssetBrowserModal`, `SpritesheetSlicerModal`, `FolderBrowser`.
3. `src/game/systems/environment_manager`: `EnvironmentProp.rebuild_frames`, `SPRITESHEET_GRIDS`.
4. `game_data`: `level_1.json`, `level_2.json` asset loading and scene graph initialization.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Backend Log Health | Zero unhandled exceptions, zero PermissionErrors/tracebacks, zero missing texture magenta fallbacks | M1 | ORIGINAL_REQUEST §R1 |
| F2 | Frame Reading & Slicing | Accurate parsing of 2D mob sheets, 1D strips, 32x32 tilesets, statues, parallax layers into discrete non-zero surfaces | M1 | ORIGINAL_REQUEST §R2 |
| F3 | Editor Preview Rendering | Headless preview generation in `_load_preview`, `AssetBrowserModal`, `SpritesheetSlicerModal` within container bounds | M1 | ORIGINAL_REQUEST §R2 |
| F4 | Level & Prop Integration | Seamless runtime integration of Hell Pack props and parallax backgrounds in level_1.json and level_2.json | M2 | ORIGINAL_REQUEST §R1, R2 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | E2E Test Suite (Tiers 1-4) | Complete test suite implementation covering Tiers 1-4 in `tests/e2e/` | none | IN_PROGRESS |
| M2 | Verification, Hardening & TEST_READY | Review, challenge, forensic integrity audit, and publication of TEST_READY.md | M1 | PLANNED |

## Code Layout
- `tests/e2e/conftest.py`: Headless Pygame fixture, stdout/stderr log capture fixture, asset path resolution.
- `tests/e2e/test_tier1_feature_coverage.py`: >=5 tests each for F1 (Log Health), F2 (Frame Reading), F3 (Editor Preview), F4 (Level Integration). (>=20 tests)
- `tests/e2e/test_tier2_boundary_corner.py`: Boundary and corner cases (corrupted config, zero/negative slice, giant sheet, invalid formats, odd aspect ratios). (>=20 tests)
- `tests/e2e/test_tier3_cross_feature.py`: Cross-feature pairwise interactions (loading + slicing + preview scaling, slicer + prop rebuild, level JSON + background render). (>=10 tests)
- `tests/e2e/test_tier4_real_world_workload.py`: Real-world end-to-end scenarios (full Level 1 & Level 2 asset loading, complete catalog discovery walk, batch asset slicer pipeline, animation loop memory stability). (>=5 tests)

## Interface Contracts
- Command line runner: `c:\Users\Chosen033\Documents\Guardian-Runner\.venv\Scripts\python.exe -m pytest tests/e2e/`
- All tests must pass headlessly (SDL_VIDEODRIVER="dummy") with zero unhandled exceptions.
