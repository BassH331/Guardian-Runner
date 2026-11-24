# Dell <-> MSI Parallel Development Directive (`Guardian-Runner` + `V3X-Zulfiqar-Gideon`)

> **Purpose:** Use this guide on the **Dell PC** (and hand it directly to your Dell AI/coding assistant) so **MSI** can complete the Level 1 story placement, dialogue cleanup, and pacing pass in parallel **without causing merge conflicts**—especially in large shared JSON configs like `game_data/level_1.json`.

---

## 1. Sync Checklist Before Starting on Dell

1. **Pull BOTH repositories first** *(two separate repos are linked together—Dell `.venv` uses an editable install of `V3X-Zulfiqar-Gideon`)*:
   ```powershell
   cd C:\Users\<USER>\Documents\V3X-Zulfiqar-Gideon
   git pull origin main

   cd C:\Users\<USER>\Documents\Guardian-Runner
   git pull origin main
   ```
   > **Why `V3X-Zulfiqar-Gideon` matters:** Engine fixes live in `v3x_zulfiqar_gideon/asset_manager.py` (exact sprite grid slicing for `"plague flies.png": (5, 2)`, `"spr_roninattack_strip33.png": (25, 1)`, `"spr_roninattackalt_strip.png": (25, 1)`, headless safety, `Spawn`/`Hurt`/`Chase`/`Die` folder slicing), `audio_manager.py` (UTF-8 JSON loading), and `settings.py` (default flags). Without pulling `V3X-Zulfiqar-Gideon`, sprites and animations will mismatch on Dell.

2. **Work on a dedicated Dell branch** *(do not commit work-in-progress directly onto `main` from two PCs simultaneously)*:
   - **Dell branch:** `feat/dell-audio-combat`
   - **MSI branch:** `story/level1-timeline`
   - Merge each completed milestone back to `main` sequentially and `git pull` on the other machine.

---

## 2. Strict File Ownership Split (Avoid JSON Merge Conflicts)

### Owned by MSI — DO NOT EDIT on Dell
MSI is re-timing, placing, and rewriting the story arc across Zones 1–4 (`0px` to `36,000px`). Leave these files untouched on Dell:

- **Story & World Placement Data:**
  - `game_data/level_1.json` *(all `world_events`, `spawn_zones`, `environment.props`, `checkpoints`, `boss_sequence`)*
  - `game_data/storyline_config.json`
  - `game_data/cutscene_config.json`
  - `game_data/notification_events.json`
  - `game_data/scene_popups_config.json`
- **Story / Encounter Systems & States:**
  - `src/game/states/story_state.py`
  - `src/game/systems/boss_encounter_manager.py`
  - `src/game/systems/cutscene_manager.py`
  - `src/game/systems/popup_scene_manager.py`
  - `src/game/systems/storyline_config_manager.py`
  - `src/game/systems/transformation_cutscene.py`
- **Level / Narrative GUI Tools:** Do **not** save changes back to disk from `level_editor.py`, `storyline_editor.py`, or `popup_controller.py` on Dell while MSI is editing `level_1.json` and `storyline_config.json`.

---

### Owned by Dell — Focus Areas (per `notes_for_game.md`)
Dell is free to iterate rapidly on **audio feel, combat polish, UI/menus, and bug fixes**:

1. **Psychoacoustics & Living Audio Mix (`notes_for_game.md` priority #1)**
   - **Files:** `game_data/master_audio_config.json`, `game_data/scene_audio_recipes.json`, `game_data/audio_emotion_catalog.json`, `game_data/bent_sounds_registry.json`, `game_data/player_audio_config.json`, `game_data/*_audio_config.json`, and `src/game/audio/`.
   - **Goals:**
     - Eliminate the "machine-gun effect" using round-robin sound pools (e.g., `Dirt Chain Run 1..5`) plus subtle pitch/volume randomization (`numpy` resampling / per-trigger jitter).
     - Build the **3-layer environmental bed**: (a) continuous low biome bed, (b) crisp footsteps & heavy landing thuds synced to actual ground/jump contact frames, (c) spatial proximity SFX for environmental hazards/torches.
     - Apply **Composite Layering** (`Transient` + `Body` + `Tail`) on melee swings/impacts and **Audio Ducking** during Demon Time, boss roars, and parries.

2. **Combat Feel, Controls, AI Polish & Bug List (`notes_for_game.md` priority #4)**
   - **Files:** `src/game/entities/player.py`, `game_data/player_config.json`, `game_data/controls_config.json`, `src/game/systems/combat_system.py`, `src/game/ai/utility_combat_engine.py`, `src/game/ai/perception_system.py`, `src/game/ai/squad_coordinator.py`.
   - **Caution on shared files:**
     - If fixing gameplay/audio bugs in `src/game/states/game_state.py` or `src/game/systems/environment_manager.py`, **keep changes small, surgical, and completely away from story triggers, `world_events`, dialogue popups, or cutscene timing**.
     - Coordinate before modifying `V3X-Zulfiqar-Gideon` so both machines stay aligned on engine code.

3. **Menus, Settings & HUD Polish**
   - **Files:** `src/game/states/main_menu_state.py`, `src/game/states/settings_state.py`, `src/game/states/controls_state.py`, `src/game/ui/hud_overlay.py`, `src/game/ui/side_notification.py`.

4. **Keep Commits Clean (Ignore Runtime Artifacts)**
   - Do not commit transient runtime saves/backups such as `save_data/slot_auto.json`, `*.lock`, or `*.backup_*` unless intentionally updating tracked defaults.

---

## 3. Ready-to-Use Prompt to Direct Your Dell Session

Copy/paste this when opening the repo on Dell:

> Read `DELL_WORKFLOW_DIRECTIVE.md` and `notes_for_game.md` first, confirm both `V3X-Zulfiqar-Gideon` and `Guardian-Runner` are up to date with `origin/main`, and switch to a Dell feature branch (`feat/dell-audio-combat`).
>
> Your focus on this machine is **audio immersion (psychoacoustics, 3-layer ambient beds, round-robin/pitch variation, composite combat SFX, audio ducking), combat/control feel, UI/menu polish, and hunting gameplay bugs**.
>
> **Hard boundary:** MSI owns the story timeline and world placement. **Do NOT modify or save** `game_data/level_1.json`, `game_data/storyline_config.json`, `game_data/cutscene_config.json`, `game_data/notification_events.json`, `game_data/scene_popups_config.json`, or any story/cutscene/popup manager files (`story_state.py`, `boss_encounter_manager.py`, `cutscene_manager.py`, `popup_scene_manager.py`, `storyline_config_manager.py`). Before finishing any milestone, run the test suite and inspect live/captured gameplay checks cleanly.

---

## 4. Verification Command Before Merging to `main`

Run from `C:\Users\<USER>\Documents\Guardian-Runner` before pushing your Dell branch:

```powershell
.venv\Scripts\python.exe -m pytest `
  tests/test_audio_channels.py `
  tests/test_audio_event_bus.py `
  tests/test_master_audio_config.py `
  tests/test_spritesheet.py `
  tests/test_player_moves.py `
  tests/test_player_damage.py `
  tests/test_perception_and_utility_ai.py `
  tests/test_skeleton_teleport_defense.py `
  tests/test_dark_ronin.py `
  tests/test_blood_zombie_behavior.py `
  tests/test_world_escalation_and_platforms.py `
  tests/test_pre_level1_menus.py `
  tests/test_environment_and_ldtk.py -q --tb=short
```

*(Note: `tests/test_environment_and_ldtk.py` calls `pg.quit()`, so keep it at the end of any multi-file pytest invocation.)*
