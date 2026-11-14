# Handoff Report: Automated Test Suite & Preview Rendering Investigation

## 1. Observation

### 1.1 Automated Test Suite Execution Baseline
- **Execution Command**: 
  ```powershell
  c:\Users\Chosen033\Documents\Guardian-Runner\.venv\Scripts\python.exe -m pytest
  ```
- **Configuration & Environment**:
  - `pytest.ini` (`testpaths = tests`, `norecursedirs = scratch venv .venv .git`)
  - Python: `3.12.10 (tags/v3.12.10:0cc8128, Apr 8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]`
  - Pytest: `9.2.0`, pluggy `1.7.0`
  - Pytest plugins: `anyio-4.16.0`, `asyncio-1.4.1.post1`
- **Execution Result**:
  - **Collected**: 529 items
  - **Passed**: 506 items
  - **Failed**: 23 items
  - **Warnings**: 6 warnings
  - **Wall-clock Duration**: 90.34s
- **Verbatim Failure Summary (23 Failures)**:
  1. `FAILED tests/test_boss_defeat_pipeline.py::TestBossDefeatPipeline::test_relic_reveal_interactive_dismiss_gamepad_and_keyboard`
  2. `FAILED tests/test_boss_music_sequence.py::TestBossMusicSequence::test_game_state_boss_defeat_music_transition`
  3. `FAILED tests/test_boss_music_sequence.py::TestBossMusicSequence::test_master_audio_config_contains_boss_music_sequence`
  4. `FAILED tests/test_entity_editor_sync.py::TestEntityEditorConsistency::test_entity_dimensions_json_contains_all_edited_entities`
  5. `FAILED tests/test_entity_editor_sync.py::TestEntityEditorConsistency::test_level_1_boss_scales_match_registry`
  6. `FAILED tests/test_game_state_popup_triggers.py::TestGameStatePopupTriggers::test_gamestate_event_ids_exist_and_valid[event_book_ponder]`
  7. `FAILED tests/test_game_state_popup_triggers.py::TestGameStatePopupTriggers::test_gamestate_event_ids_exist_and_valid[event_first_encounter]`
  8. `FAILED tests/test_game_state_popup_triggers.py::TestGameStatePopupTriggers::test_gamestate_event_ids_exist_and_valid[event_forest_inquiry_1400m]`
  9. `FAILED tests/test_game_state_popup_triggers.py::TestGameStatePopupTriggers::test_prologue_awakening_content_not_fabricator`
  10. `FAILED tests/test_game_state_popup_triggers.py::TestGameStatePopupTriggers::test_entity_trigger_distances_and_ids_match_level_1`
  11. `FAILED tests/test_game_state_popup_triggers.py::TestGameStatePopupTriggers::test_silenced_systems_remain_disabled`
  12. `FAILED tests/test_game_state_popup_triggers.py::TestGameStatePopupTriggers::test_programmatic_gamestate_trigger_resolution_without_fallback`
  13. `FAILED tests/test_item_lore_system.py::test_relic_discovery_triggers_flashback`
  14. `FAILED tests/test_item_lore_system.py::test_flashback_timer_decay`
  15. `FAILED tests/test_m1_challenger_verification.py::test_m1_all_13_scenes_conformance`
  16. `FAILED tests/test_m1_challenger_verification.py::test_m1_prologue_awakening_narrative_integrity`
  17. `FAILED tests/test_m1_challenger_verification.py::test_m1_entity_lookups`
  18. `FAILED tests/test_m1_challenger_verification.py::test_m1_silenced_systems_invariants`
  19. `FAILED tests/test_narrative_streamline.py::TestNarrativeStreamline::test_whisperer_system_cooldown_and_priority_milestones`
  20. `FAILED tests/test_popup_controller.py::test_popup_controller_entity_catalog_and_linking`
  21. `FAILED tests/test_popup_scene_manager.py::test_popup_scene_manager_load_and_lookup`
  22. `FAILED tests/test_storyline_config_manager.py::test_relics_config_content`
  23. `FAILED tests/test_wiring.py::TestGameStateWiring::test_has_spawn_zones_from_json`
- **Domain-Specific Test Status**:
  - `tests/test_spritesheet.py`: 3/3 passed (1.81s). Tests `AssetManager.slice_spritesheet`, auto strip detection, and `split_spritesheet` utility.
  - `tests/test_level_editor_ground_and_prop_fixes.py`: 11/11 passed (9.70s). Tests `Large Skull.png` 10x4 spritesheet slicing, 40-frame animation, and trap loop.
  - `tests/test_editor_plugins_roundtrip_integrity.py` & `test_editor_plugins_adversarial_m2.py`: 21/21 passed (4.15s).
  - `tests/test_all_plugins_cia_integrity.py` & `test_plugin_commit_integrity.py`: 16/16 passed (2.53s).

### 1.2 Preview Rendering Components & UI Architecture
Direct inspection of the codebase revealed several preview renderers across plugins and tools:
1. **`level_editor.py` Stage 3 Live Preview**:
   - Lines 1186-1193:
     ```python
     def _load_preview(path: str, scale: float = 2.0) -> list[pg.Surface]:
         frames: list[pg.Surface] = []
         if not os.path.exists(path): return frames
         raw_frames = AssetManager.get_animation_frames(path)
         for img in raw_frames:
             w, h = img.get_size()
             frames.append(pg.transform.scale(img, (int(w*scale), int(h*scale))))
         return frames
     ```
   - Lines 3680-3699: Stage 3 `_update` checks `tgt = self.browser.selected or ""` and when changed calls `self.prev_frames = _load_preview(tgt)`.
   - Lines 4056-4065 & 4100-4110: `_draw` renders `fr = self.prev_frames[self.prev_idx % len(self.prev_frames)]` into `pbox = pg.Rect(472, CONTENT_Y+458, 782, 142)` (NPCs) or `pbox = pg.Rect(462, CONTENT_Y+435, 380, 150)` (Bosses).
2. **`level_editor.py` AssetBrowserModal (`AssetBrowserModal`)**:
   - Lines 2017-2240: Visual 3x2 grid of cards (248x155) displaying assets discovered from `assets/graphics`.
   - Lines 2056-2068: Thumbnail generation:
     ```python
     def _get_thumbnail(self, path: str) -> Optional[pg.Surface]:
         if path in self._thumb_cache: return self._thumb_cache[path]
         try:
             frames = AssetManager.get_animation_frames(path)
             if frames:
                 orig = frames[0]
                 scaled = pg.transform.smoothscale(orig, (55, 55))
                 self._thumb_cache[path] = scaled
                 return scaled
         except Exception: pass
         self._thumb_cache[path] = None
         return None
     ```
3. **`level_editor.py` SpritesheetSlicerModal (`SpritesheetSlicerModal`)**:
   - Lines 1453-2016: Allows slicing sheets via "Auto" contour, "32x32", "64x64", or "128x128" grid.
   - Lines 1485-1502: Excludes folders containing `"blood"` (`"blood"` is in `exclude_keywords`), filtering out `GandalfHardcore Blood Tiles.png`.
   - Lines 1545-1550: Loads sheet surface via `AssetManager.get_texture(path)`.
4. **`boss_editor.py` & `wizard_editor.py` Preview Container**:
   - Uses `PreviewScaler.calculate_auto_fit(surface, preview_rect, floor_y)` from `src/game/editor/preview_scaler.py` to auto-fit bounding box within an 820x400 container at `floor_y=420`.
5. **`entity_editor.py`**:
   - Lines 718-795: 630x600 preview panel at (280, 80) rendering `self.entity.image` on floor line `PREVIEW_SCREEN_BOTTOM = 550` with green bounding rect for texture bounds.
6. **`the_eye.py`**:
   - 3D narrative tree and node perception viewer with simulation preview window.

### 1.3 Asset Loading Backend (`v3x_zulfiqar_gideon.AssetManager`)
- **Package Location**: `C:\Users\Chosen033\Documents\V3X-Zulfiqar-Gideon\v3x_zulfiqar_gideon\asset_manager.py` (installed into `.venv`).
- **Inspection of `AssetManager.get_animation_frames(target_path, ...)`**:
  ```python
  @classmethod
  def get_animation_frames(cls, target_path, cols=None, rows=None, frame_width=None, frame_height=None):
      target_path = cls.resolve_path(target_path)
      frames = []
      if not os.path.exists(target_path):
          print(f"Error: Path not found {target_path}")
          return frames
      try:
          if os.path.isfile(target_path):
              return cls._load_frames_from_image_file(target_path, cols, rows, frame_width, frame_height)
          ...
          files = sorted([f for f in os.listdir(target_path) if f.endswith('.png') ...])
          if not files: return frames
          # Multi-file directory loading:
          if len(files) > 1 and not any("_strip" in f.lower() for f in files):
              for f in files:
                  path = os.path.join(target_path, f)
                  frames.append(cls.get_texture(path))
              return frames
  ```
- **Inspection of `AssetManager._load_frames_from_image_file(...)`**:
  ```python
  @classmethod
  def _load_frames_from_image_file(cls, img_path, cols=None, rows=None, frame_width=None, frame_height=None):
      sheet_surf = cls.get_texture(img_path)
      w, h = sheet_surf.get_size()
      ...
      json_candidates = [
          img_path + ".json",
          os.path.splitext(img_path)[0] + ".json",
          os.path.join(os.path.dirname(img_path), "config.json")
      ]
      for jpath in json_candidates:
          if os.path.exists(jpath):
              with open(jpath, "r", encoding="utf-8") as f: meta = json.load(f)
              c, r, fw, fh = meta.get("cols"), meta.get("rows"), meta.get("frame_width"), meta.get("frame_height")
              if c is not None or r is not None or fw is not None or fh is not None:
                  return cls.slice_spritesheet(sheet_surf, cols=c, rows=r, frame_width=fw, frame_height=fh)
      ...
      base = os.path.basename(img_path)
      strip_match = re.search(r'_strip(\d+)', base, re.IGNORECASE)
      if strip_match:
          return cls.slice_spritesheet(sheet_surf, cols=int(strip_match.group(1)), rows=1)
      if w > h and h > 0 and w % h == 0:
          return cls.slice_spritesheet(sheet_surf, cols=w // h, rows=1)
      elif h > w and w > 0 and h % w == 0:
          return cls.slice_spritesheet(sheet_surf, cols=1, rows=h // w)
      return [sheet_surf]
  ```

### 1.4 Target Directory Inspection: `GandalfHardcore Hell Asset Pack 32x32`
- **Location**: `c:\Users\Chosen033\Documents\Guardian-Runner\assets\graphics\GandalfHardcore Hell Asset Pack 32x32`
- **File Inventory and Dimensions**:
  - `Blue fire sheet.png` (192x32) -> 6 frames (auto-detected `192 // 32 = 6`)
  - `Fire sheet.png` (192x32) -> 6 frames (auto-detected `192 // 32 = 6`)
  - `GandalfHardcore Blood Tiles.png` (640x352) -> `640 % 352 = 288 != 0` -> returns 1 un-sliced frame
  - `GandalfHardcore Hell Tiles 32x32 dark.png` (544x288) -> `544 % 288 = 256 != 0` -> returns 1 un-sliced frame
  - `GandalfHardcore Hell Tiles 32x32.png` (544x288) -> `544 % 288 = 256 != 0` -> returns 1 un-sliced frame
  - `GandalfHardcore Lava Tiles.png` (640x352) -> `640 % 352 = 288 != 0` -> returns 1 un-sliced frame
  - `Large Statue.png` (96x160) -> returns 1 un-sliced frame
  - `Large Statue 2.png` (96x160) -> returns 1 un-sliced frame
- **Subdirectory: `GandalfHardcore The Damned Enemies and NPCs/`**:
  - `Bloated Damned.png` (512x192) -> returns 1 un-sliced frame
  - `Burning Damned blue.png` (512x256) -> returns 2 giant 256x256 frames (`512 % 256 == 0`), but sprites are 64x64
  - `Burning Damned.png` (512x256) -> returns 2 frames (256x256) instead of 8x4 grid
  - `Burning Skull.png` (448x128) -> returns 1 un-sliced frame
  - `Burning Skull blue.png` (448x128) -> returns 1 un-sliced frame
  - `Cheeky Devil.png` (640x64) -> returns 10 frames of 64x64
  - `Demon eye.png` (448x128) -> returns 1 un-sliced frame
  - `Demon Mine.png` (448x128) -> returns 1 un-sliced frame
  - `Female Damned.png` (512x256) -> returns 2 frames
  - `Female Hell Giant.png` (1120x128) -> returns 1 un-sliced frame
  - `Flying Demon Head.png` (384x128) -> returns 3 frames of 128x128
  - `Imp.png` (640x320) -> returns 2 frames (320x320) instead of 10x5 grid
  - `Large Skull.png` (1280x512) -> returns 1 un-sliced frame (1280x512) instead of 40 frames (10x4 of 128x128)
  - `Male Damned.png` (512x256) -> returns 2 frames
  - `Memento Mori Skeleton.png` (512x384) -> returns 1 un-sliced frame
  - `Old Demon.png` (560x64) -> returns 1 un-sliced frame
  - `Plague Flies.png` (160x64) -> returns 1 un-sliced frame
  - `The Devil.png` (672x560) -> returns 1 un-sliced frame
  - `Tree Damned.png` (448x128) -> returns 1 un-sliced frame
  - `Twisted Damned.png` (512x256) -> returns 2 frames
- **Existing `_frames/config.json` Files Generated by `split_spritesheet.py`**:
  - Reading `assets\graphics\GandalfHardcore Hell Asset Pack 32x32\GandalfHardcore Blood Tiles_frames\config.json`:
    `{"cols": 1, "rows": 1, "frame_width": 640, "frame_height": 352, "total_frames": 1}`
  - Reading `assets\graphics\GandalfHardcore Hell Asset Pack 32x32\GandalfHardcore The Damned Enemies and NPCs\Large Skull_frames\config.json`:
    `{"cols": 1, "rows": 1, "frame_width": 1280, "frame_height": 512, "total_frames": 1}`
  - All multi-row / multi-column sheets were sliced with `cols=1, rows=1` because `split_spritesheet.py` only auto-detected horizontal 1-row square strips (`w % h == 0 and rows=1`).
- **File System Permissions & Denial Logs**:
  - Sandboxed execution throws:
    `PermissionError: [Errno 13] Permission denied` when attempting to access files in `GandalfHardcore Hell Asset Pack 32x32` and `[WinError 5] Access is denied` on the `_frames` directories.
  - In `level_editor.py`'s `FolderBrowser._walk()`:
    `except OSError: children, pngs = [], []`
    When `os.listdir(fp)` encounters `PermissionError`, it catches `OSError`, clearing `pngs`. The directory is rendered with `has_pngs = False`, disabling the `[SELECT]` button and preventing preview generation.

---

## 2. Logic Chain

```
[Observation 1.1] Full pytest suite runs 529 items with 506 passes and 23 failures.
                  Test suite tests/test_spritesheet.py and test_level_editor_ground_and_prop_fixes.py PASS.
                  In test_level_editor_ground_and_prop_fixes.py, Large Skull.png is explicitly tested
                  with anim_grid=[10, 4] via EnvironmentProp.
         │
         ▼
[Observation 1.3 & 1.4] AssetManager.get_animation_frames() has two loading pathways:
                        A) Directory target
                        B) Single image file target
         │
         ├────────────────────────────────────────────────────────────────────────┐
         │                                                                        │
         ▼                                                                        ▼
[Pathway A: Directory Selected in UI]                     [Pathway B: Image File or Sliced Folder Selected]
- FolderBrowser selects directory path:                   - Image file passed to _load_frames_from_image_file:
  `assets/graphics/GandalfHardcore Hell Asset Pack 32x32`    - Checks json_candidates for sidecar metadata.
- Target contains 8 .png files (tiles, statues, fire).    - If none found, checks `_strip\d+` regex.
- `len(files) > 1 and not any("_strip" in f)` is TRUE.    - Checks square strip heuristic: `w > h and w % h == 0`.
- AssetManager loads every file in the directory          - 2D grid sheets (Blood Tiles 640x352, Hell Tiles 544x288,
  as sequential animation frames of a SINGLE sprite:        Large Skull 1280x512, Bloated Damned 512x192) fail
  Frame 0: Blue fire sheet (192x32)                         `w % h == 0`!
  Frame 1: Fire sheet (192x32)                            - Fallback triggers: returns [sheet_surf] (1 frame).
  Frame 2: Blood Tiles (640x352 tileset)                  - Returns full un-sliced spritesheet!
  ...                                                                             │
  Frame 7: Large Statue (96x160)                                                  │
- In `_load_preview`, each image is scaled 2.0x                                   │
  (e.g. Blood Tiles becomes 1280x704).                                            │
- Preview box is only 782x142 (NPCs) or 380x150 (Bosses).                         │
- Huge un-sliced tileset / sprite sheet blitted to tiny box                       │
  renders clipped or missing the intended frame.                                  │
         │                                                                        │
         ├────────────────────────────────────────────────────────────────────────┘
         │
         ▼
[Observation 1.4: split_spritesheet.py Execution Defect]
- When `split_spritesheet.py` previously sliced `GandalfHardcore Hell Asset Pack 32x32`,
  it had no explicit `--cols` or `--rows` arguments.
- It evaluated `w % h == 0` and fell back to `cols = 1, rows = 1`.
- It created `_frames/config.json` with `"cols": 1, "rows": 1, "total_frames": 1`.
- It created a single `frame_000.png` containing the full un-sliced spritesheet.
         │
         ▼
[Observation 1.3: Sidecar config.json Collision Defect]
- In `AssetManager._load_frames_from_image_file`:
  `json_candidates` includes `os.path.join(os.path.dirname(img_path), "config.json")`.
- When loading `Blue fire sheet_frames/frame_000.png`:
  It finds `config.json` (cols=6, rows=1) and attempts to slice `frame_000.png` (already 32x32)
  into 6 subsurfaces of 5x32 pixels, producing distorted / sliced sub-pixel slivers.
         │
         ▼
[Observation 1.4: Missing SPRITESHEET_GRIDS & Sidecars]
- In `EnvironmentProp` (`src/game/systems/environment_manager.py`), only `"large skull.png": (10, 4)`
  is in `SPRITESHEET_GRIDS`.
- No other `GandalfHardcore Hell Asset Pack 32x32` asset has a grid definition or sidecar `.json`
  file defining its grid dimensions (32x32 for tilesets, 64x64 for damned mobs).
         │
         ▼
[Conclusion]
Frames in `GandalfHardcore Hell Asset Pack 32x32` fail to appear in preview due to:
1. `AssetManager.get_animation_frames()` concatenating disparate spritesheet files in directory mode instead of detecting individual sheets.
2. Fallback to `cols=1, rows=1` in `split_spritesheet.py` generating 1-frame dummy `config.json` sidecars for 2D grid sheets.
3. Lack of sidecar JSON metadata or `SPRITESHEET_GRIDS` definitions for Hell Asset Pack 32x32 tilesets and 64x64 mobs.
4. Preview container scale overflow when 1-frame giant sheets are blitted into 782x142 / 380x150 preview boxes without `PreviewScaler` auto-fitting.
```

---

## 3. Caveats
1. **Existing Test Suite Baseline**:
   - The 23 test failures observed during the pytest run are pre-existing test suite failures related to narrative storyline configs (`relics_config_content`, `scene_popups_config`, `boss_defeat_pipeline`), NOT caused by the asset preview system.
   - The asset and spritesheet test suites (`test_spritesheet.py`, `test_level_editor_ground_and_prop_fixes.py`, `test_editor_plugins_roundtrip_integrity.py`) currently pass 100%.
2. **Read-Only Scope**:
   - As an explorer agent, no code, sidecar files, or permissions were modified during this investigation.
3. **External Package Location**:
   - `AssetManager` is provided by `v3x_zulfiqar_gideon`, which is installed from the sibling repository `c:\Users\Chosen033\Documents\V3X-Zulfiqar-Gideon`. Any modifications to `AssetManager` methods (`get_animation_frames`, `_load_frames_from_image_file`) affect both projects and must maintain backward compatibility with `test_spritesheet.py`.

---

## 4. Conclusion
The failure of frames from `GandalfHardcore Hell Asset Pack 32x32` to appear in editor previews is fully explained by four interrelated architectural bottlenecks:

1. **Data Layer Format Mismatch (`v3x_zulfiqar_gideon.AssetManager`)**:
   - The preview interface expects `list[pg.Surface]` where each element is an individual animation frame.
   - For multi-image directories without `_strip`, `AssetManager.get_animation_frames()` assumes each `.png` file is an already-isolated single animation frame rather than a spritesheet. This corrupts folder previews by treating all distinct tilesets/entities in the pack as one nonsensical multi-frame sequence.
   - For 2D grid spritesheets (where `w % h != 0`), `AssetManager` fails to auto-detect grid dimensions and falls back to returning the full un-sliced sheet as a single frame.

2. **Corrupted Slicing Sidecars in `GandalfHardcore Hell Asset Pack 32x32`**:
   - The generated `_frames/` subdirectories contain invalid `config.json` sidecars with `"cols": 1, "rows": 1, "total_frames": 1` because `split_spritesheet.py` only supported 1D horizontal strips (`rows=1`) by default.
   - Furthermore, nested `_frames/frame_000_frames` directories were created by recursive splitting.

3. **Missing Grid Metadata for 32x32 Tiles and Damned Mobs**:
   - `GandalfHardcore Blood Tiles.png` (640x352 = 20x11 tiles of 32x32)
   - `GandalfHardcore Hell Tiles 32x32.png` (544x288 = 17x9 tiles of 32x32)
   - `GandalfHardcore Hell Tiles 32x32 dark.png` (544x288 = 17x9 tiles of 32x32)
   - `GandalfHardcore Lava Tiles.png` (640x352 = 20x11 tiles of 32x32)
   - Damned Enemy sheets (Bloated Damned 8x3, Burning Damned 8x4, Cheeky Devil 10x1, Imp 10x5, Large Skull 10x4, etc.) require 32x32 or 64x64 cell specifications via sidecar JSON (`<name>.json` or `<name>.png.json`) or entries in `SPRITESHEET_GRIDS`.

4. **UI Preview Container Sizing**:
   - `level_editor.py` Stage 3 draws preview frames inside fixed preview boxes (`782x142` or `380x150`) using fixed 2.0x scaling without utilizing `PreviewScaler.calculate_auto_fit()`. When given un-sliced sheets (e.g. 1280x512 scaled to 2560x1024), the graphic is clipped outside the viewport box.

---

## 5. Verification Method

### 5.1 Independent Test Suite Verification
Run the existing automated test suite using the project python interpreter:
```powershell
Set-Location 'c:\Users\Chosen033\Documents\Guardian-Runner'
.venv\Scripts\python.exe -m pytest tests/test_spritesheet.py tests/test_level_editor_ground_and_prop_fixes.py -v
```
Expected output: 14 passed in < 12 seconds.

### 5.2 Asset Loading & Frame Count Verification
Execute the following verification probe via `.venv\Scripts\python.exe`:
```python
import os, pygame
pygame.init()
pygame.display.set_mode((1, 1), pygame.NOFRAME)
from v3x_zulfiqar_gideon import AssetManager

pack_dir = "assets/graphics/GandalfHardcore Hell Asset Pack 32x32"
skull_path = os.path.join(pack_dir, "GandalfHardcore The Damned Enemies and NPCs", "Large Skull.png")

# Currently returns 1 frame (un-sliced):
frames = AssetManager.get_animation_frames(skull_path)
print(f"Large Skull frames loaded: {len(frames)} (Expected: 40 frames of 128x128)")

# Currently returns 1 frame (un-sliced):
blood_tiles = os.path.join(pack_dir, "GandalfHardcore Blood Tiles.png")
tile_frames = AssetManager.get_animation_frames(blood_tiles)
print(f"Blood Tiles frames loaded: {len(tile_frames)} (Expected: 220 tiles of 32x32)")
```

### 5.3 Invalidation Conditions
This report's diagnosis is invalidated if:
1. `AssetManager.get_animation_frames()` already possesses 2D grid auto-detection for non-square ratios (verified: lines 58-75 of `asset_manager.py` only check `w % h == 0` or `h % w == 0` for 1D strips).
2. Existing sidecar `config.json` files contain valid grid slice numbers (verified: `cols=1, rows=1` in `Large skull_frames/config.json` and `GandalfHardcore Blood Tiles_frames/config.json`).
