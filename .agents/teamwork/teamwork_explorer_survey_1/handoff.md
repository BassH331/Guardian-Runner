# Handoff Report: Monster and Boss Sprite Presentation in Narrative Overlay

**Agent**: Explorer 1 (Narrative Overlay Explorer)  
**Working Directory**: `c:\Users\Chosen033\Documents\Pixel-Runner\.agents\teamwork\teamwork_explorer_survey_1\`  
**Date**: 2026-11-03  
**Status**: Complete (Hard Handoff)  
**Objective**: Comprehensive investigation of Requirement R1 (Monster & Boss Sprite Presentation in Narrative Overlay) and controller skip mechanics (R2).

---

## 1. Observation

### 1.1 Architecture & Control Flow for Narrative Overlay and Boss Dialogues
- **Overlay Instantiation & Rendering**:
  - `src/game/states/game_state.py:187-188`: Instantiates `CinematicNarrativeOverlay`:
    ```python
    from src.game.ui.cinematic_narrative_overlay import CinematicNarrativeOverlay
    self.cinematic_narrative_overlay = CinematicNarrativeOverlay()
    ```
  - `src/game/states/game_state.py:2341-2342`: Draws overlay in game loop:
    ```python
    if hasattr(self, "cinematic_narrative_overlay") and self.cinematic_narrative_overlay.is_active:
        self.cinematic_narrative_overlay.draw(surface)
    ```
  - `src/game/states/game_state.py:1014-1016`: Routes events to overlay:
    ```python
    if hasattr(self, "cinematic_narrative_overlay") and self.cinematic_narrative_overlay.is_active:
        if self.cinematic_narrative_overlay.handle_event(event):
            return
    ```
  - `src/game/states/game_state.py:1434-1436`: Slow-motion combat scaling (10% speed) during overlay active:
    ```python
    if hasattr(self, "cinematic_narrative_overlay") and self.cinematic_narrative_overlay.is_active:
        self.cinematic_narrative_overlay.update(dt)
        dt = dt * 0.10
    ```

- **Boss Dialogue Triggering & Encounter Flow**:
  - `src/game/states/game_state.py:724-765`: In `_handle_boss_spawn()`:
    - Blood Zombie has a hardcoded cutscene event calling `activate()` directly (lines 735-749):
      ```python
      cutscene_event = {
          "speaker_name": "Blood Zombie",
          "avatar_sprite": "assets/graphics/bloodZombie/Idle",
          "dialogue_text": (
              "The one you didn't belong here, mortal... "
              "The bark of the great one, you thief!! You shall die!!"
          ),
          "option_1_label": "[SPACE] Draw Blade",
          "option_1_buff": {"start_blood_zombie_combat": True}
      }
      self.cinematic_narrative_overlay.activate(cutscene_event, _on_blood_zombie_cutscene_dismiss)
      ```
    - ALL other bosses (including Green Monster / Gatekeeper, Fire Wizard, Dark Ronin) are routed to `BossEncounterManager.begin_encounter(_enc_key, boss)` (lines 755-764).

### 1.2 BossEncounterManager Implementation
- `src/game/systems/boss_encounter_manager.py:39-68`: `begin_encounter()` freezes the boss AI and builds `self._dialogue_queue` from `pre_fight` lines and `corruption_variants`.
- `src/game/systems/boss_encounter_manager.py:120-128`: `_show_next_line()`:
  ```python
  def _show_next_line(self) -> None:
      if not self._dialogue_queue:
          return
      line = self._dialogue_queue.pop(0)
      if self._overlay:
          show_fn = getattr(self._overlay, "show_bark", None)
          if show_fn:
              show_fn(line, speaker=None)  # boss lines shown without Andras/MK tint
  ```

### 1.3 CinematicNarrativeOverlay Presentation & Sizing Mechanics
- `src/game/ui/cinematic_narrative_overlay.py:130-137`: `show_bark()`:
  ```python
  def show_bark(self, text: str, speaker: Optional[Speaker] = None) -> None:
      """Show a whisperer bark line via the overlay."""
      self._speaker = speaker
      event: Dict[str, Any] = {
          "dialogue_text": text,
          "option_1_label": "[SPACE] Continue",
      }
      self.activate(event)
  ```
  *Observed*: Does NOT pass `avatar_sprite` or `speaker_name`.
- `src/game/ui/cinematic_narrative_overlay.py:344`: Speaker label fallback:
  ```python
  speaker_label = str(self._current_event.get("speaker_name", "Kimi Narrative Director"))
  ```
- `src/game/ui/cinematic_narrative_overlay.py:59-61`: Black void vignette creation:
  ```python
  self._vignette_surface = pg.Surface((self._width, self._height), pg.SRCALPHA)
  # The user requested a completely black void
  self._vignette_surface.fill((0, 0, 0, 255))
  ```
- `src/game/ui/cinematic_narrative_overlay.py:103-127`: Avatar loading logic:
  ```python
  avatar_path = narrative_event.get("avatar_sprite")
  if avatar_path and not self._is_book_ritual:
      try:
          agis_dir = avatar_path
          individual_pngs = sorted(
              [f for f in os.listdir(agis_dir) if f.lower().endswith(".png") and not os.path.isdir(os.path.join(agis_dir, f))]
          )
          if individual_pngs:
              scale = 3.5
              for fname in individual_pngs:
                  img = pg.image.load(os.path.join(agis_dir, fname)).convert_alpha()
                  w = int(img.get_width() * scale)
                  h = int(img.get_height() * scale)
                  self._avatar_frames.append(pg.transform.smoothscale(img, (w, h)))
          else:
              frames = AssetManager.get_animation_frames(avatar_path)
              if frames:
                  scale = 3.5
                  for f in frames:
                      self._avatar_frames.append(pg.transform.smoothscale(f, (int(f.get_width() * scale), int(f.get_height() * scale))))
      except Exception as e:
          print(f"[CinematicOverlay] Avatar load error: {e}")
  ```
- `src/game/ui/cinematic_narrative_overlay.py:307-311`: Avatar positioning:
  ```python
  elif self._avatar_frames:
      frame = self._avatar_frames[self._avatar_frame_idx % len(self._avatar_frames)]
      av_x = (self._width - frame.get_width()) // 2
      av_y = (self._height - frame.get_height()) // 3
      surface.blit(frame, (av_x, av_y))
  ```
- `src/game/ui/cinematic_narrative_overlay.py:314-317`: Dialogue card dimensions & position:
  ```python
  card_w = int(self._width * 0.85)
  card_h = 180
  card_x = (self._width - card_w) // 2
  card_y = self._height - card_h - 25  # 720 - 180 - 25 = 515
  ```
- `src/game/ui/cinematic_narrative_overlay.py:152-176`: Event handling:
  - Listens only to `pg.KEYDOWN` (`K_1`, `K_KP1`, `K_RETURN`, `K_SPACE`, `K_ESCAPE`, `K_2`, `K_KP2`) and `pg.MOUSEBUTTONDOWN`.
  - Does NOT handle `pg.JOYBUTTONDOWN` at all.

### 1.4 Narrative Encounters & Configuration Mapping
- `game_data/storyline_config.json`:
  - `boss_dialogue.GreenMonster` (lines 170-184):
    - `pre_fight`: `["You should not have come this far.", "My master's patience ends here."]`
    - `death_line`: `"The gate... holds no longer..."`
    - `corruption_variants`: `{"low": "...", "mid": "...", "high": "..."}`
  - `boss_dialogue.Gatekeeper` (lines 185-205):
    - `pre_fight`: `["Nothing passes this threshold.", "You bear his mark. And yet you hesitate. Pathetic."]`
    - `death_line`: `"The threshold... was never mine to hold..."`
  - `boss_dialogue.BloodZombie` (lines 206-229)
  - `boss_dialogue.FireWizard` (lines 230-245)
  - `boss_dialogue.DarkRonin` (lines 246-265)
  - `boss_hierarchy`: `["green_monster", "gatekeeper", "necromancer", "fire_wizard", "dark_ronin"]`
- `game_data/level_1.json`:
  - Distance 12500, Entity id 1, Type: `"boss"`, Title: `"The Gatekeeper"`, `sprite_dir`: `"assets/graphics/green_monster"`, `scale`: 2.63.
  - Distance 2558, Entity id 14, Type: `"boss"`, Title: `"Blood Zombie"`, `sprite_dir`: `"assets/graphics/bloodZombie"`, `scale`: 2.0.
  - Distance 34500, Entity id 3, Type: `"boss"`, Title: `"The Fabricator's Enforcer"`, `sprite_dir`: `"assets/wizard"`, `scale`: 4.11.
  - `boss_sequence`: `["GreenMonster", "Gatekeeper", "BloodZombie", "FireWizard", "DarkRonin"]`.
- `game_data/scene_popups_config.json`:
  - Event `event_gatekeeper_encounter`: distance 12500, entity_id 1, title `"The Iron Gatekeeper"`.
- `game_data/entity_dimensions.json`:
  - `"boss:green_monster"`: `{"left": 216, "right": 210, "top": 101, "bottom": 39, "ground_offset": 127, "scale": 2.63}`.
  - `"boss:bloodzombie"`: `{"left": 65, "right": 189, "top": 136, "bottom": 28, "ground_offset": 65, "scale": 2.0}`.
  - `"boss:wizard"`: `{"left": 259, "right": 281, "top": 208, "bottom": 192, "ground_offset": 127, "scale": 4.11}`.

### 1.5 Asset Directory Inspection
- **Green Monster**: `assets/graphics/green_monster/`
  - Subdirectories: `1atk/`, `2atk/`, `death/`, `fly/`, `hurt/`, `idle/`, `walk/`.
  - Direct PNG files in root folder: **None** (all `.png` files reside inside action subdirectories such as `idle/idle_1.png` to `idle/idle_14.png`).
- **Blood Zombie**: `assets/graphics/bloodZombie/`
  - Subdirectories: `Idle/` (`blood_idle00.png` to `blood_idle09.png`), `Attack1/`, etc.
- **Fire Wizard**: `assets/wizard/`
  - Subdirectories: `Idle/` (`wizard_idle0.png` to `wizard_idle7.png`), `Attack/`, etc.
- **Dark Ronin**: `assets/graphics/Ronin/`
  - Spritesheet strip: `spr_RoninIdle_strip8.png`.
- **Skeleton**: `assets/skeleton/Skeleton_01_White_Idle/`
- **Andras**: `assets/Agis/` (`Agis_00.png` to `Agis_18.png`).

---

## 2. Logic Chain

### 2.1 Why the Green Monster Sprite Fails to Appear (Root Cause 1: Parameter Omission)
1. In `GameState._handle_boss_spawn` (line 755), non-BloodZombie bosses start their dialogue encounter via `BossEncounterManager.begin_encounter(_enc_key, boss)`.
2. When the dialogue line is delivered in `BossEncounterManager._show_next_line()` (line 125), it calls `self._overlay.show_bark(line, speaker=None)`.
3. In `CinematicNarrativeOverlay.show_bark()` (lines 130-137), the generated event dictionary contains only `dialogue_text` and `option_1_label`.
4. Neither `speaker_name` nor `avatar_sprite` is included in the event dictionary.
5. Consequently, `CinematicNarrativeOverlay.activate()` executes with `avatar_path = None`, skipping avatar frame loading entirely. `self._avatar_frames` remains empty (`[]`).
6. Furthermore, `speaker_label` defaults to `"Kimi Narrative Director"` because `speaker_name` was omitted.

### 2.2 Why Sprite Loading Fails Even When Path Is Configured (Root Cause 2: Subdirectory Structure)
1. If a caller sets `avatar_sprite: "assets/graphics/green_monster"`, `os.listdir(agis_dir)` in `CinematicNarrativeOverlay.activate()` finds only directories (`idle`, `1atk`, `walk`, etc.) and no `.png` files.
2. `individual_pngs` evaluates to an empty list (`[]`).
3. The fallback `AssetManager.get_animation_frames("assets/graphics/green_monster")` checks for images directly in that root path and returns an empty list.
4. `self._avatar_frames` remains empty. The sprite is never created or loaded.

### 2.3 Why Sprites Clip Heavily When Loaded (Root Cause 3: Unconstrained 3.5x Scaling)
1. For sprites that do load (such as Blood Zombie in `assets/graphics/bloodZombie/Idle` or if Green Monster were pointed directly to `idle/`), `CinematicNarrativeOverlay.activate()` applies a hardcoded scale multiplier: `scale = 3.5`.
2. `scale = 3.5` was tuned exclusively for the miniature Agis avatar (48x48 / 64x64px), scaling it to ~168–224px.
3. In contrast, Green Monster and Blood Zombie frames have raw canvas dimensions exceeding 450–550px wide and 350–450px high.
4. Multiplying 500x400 by 3.5 produces a massive surface of **1750x1400px**.
5. The game runs at **1280x720px**. An image sized 1750x1400 exceeds the screen dimensions in both directions, overflowing completely beyond screen borders.

### 2.4 Why Sprites Collide with the Dialogue Box or Clip Off-Screen (Root Cause 4: Y-Coordinate Positioning)
1. `CinematicNarrativeOverlay.draw()` computes avatar position as `av_y = (self._height - frame.get_height()) // 3`.
2. For a 1400px tall frame on a 720px screen: `(720 - 1400) // 3 = -226`.
3. The top 226 pixels are completely clipped above the upper screen margin.
4. The bottom of the sprite extends down to `y = -226 + 1400 = 1174`, extending far past the bottom of the screen (720px) and directly behind and through the dialogue card (`card_y = 515` to `695`).

### 2.5 Why the Scene Appears as an Empty Black Screen (Root Cause 5: 100% Opaque Vignette)
1. `CinematicNarrativeOverlay._rebuild_vignette()` creates a surface filled with `(0, 0, 0, 255)` (solid, completely opaque black).
2. When `draw()` blits `self._vignette_surface` at `(0, 0)`, the entire game world, background layers, player character, and combat arena are completely hidden.
3. Because Root Causes 1 & 2 prevent the avatar sprite from rendering, the screen consists solely of an empty black canvas with a dialogue box at the bottom.

### 2.6 Why Controller X Button Fails to Advance Dialogue (Root Cause 6: Missing Gamepad Input Handling)
1. In `CinematicNarrativeOverlay.handle_event()`, only `pg.KEYDOWN` and `pg.MOUSEBUTTONDOWN` are checked.
2. `pg.JOYBUTTONDOWN` is completely absent.
3. Controller button press events (Xbox X button index 2, PlayStation Cross/X button index 0) fall through and return `False`.

---

## 3. Caveats
- No changes to source code were made during this investigation (read-only mode strictly respected).
- While `CutsceneManager` (`src/game/systems/cutscene_manager.py`) manages NPC zoom cutscenes and already has `JOYBUTTONDOWN` for buttons `(0, 1, 6)`, it is decoupled from `CinematicNarrativeOverlay`. The boss narrative sequence runs exclusively through `CinematicNarrativeOverlay`.
- The transformation cutscene system (`cutscene_editor.py` / `src/game/states/transformation_cutscene.py`) is dedicated to player transformation and does not manage monster dialogue overlays.

---

## 4. Conclusion

The failure of the Green Monster (and other monsters/bosses) to appear properly during narrative dialogue is caused by a multi-layered disconnect across `BossEncounterManager` and `CinematicNarrativeOverlay`:

1. **Parameter Starvation**: `BossEncounterManager._show_next_line()` does not pass speaker name or avatar sprite path to `_overlay.show_bark()`.
2. **Directory Slicing Failure**: `CinematicNarrativeOverlay.activate()` does not inspect child directories (e.g. `idle/`) when a parent sprite directory is provided.
3. **Unbounded Scaling**: Hardcoded `scale = 3.5` balloons monster frames (up to 1750x1400px), causing extreme off-screen clipping.
4. **Collision with Dialogue Card**: Avatar Y-positioning lacks a bounding box constraint relative to the top of the dialogue card (`card_y = 515`).
5. **Opaque Blackout**: Solid black void vignette (`(0, 0, 0, 255)`) hides the game world instead of providing a translucent cinematic overlay.
6. **Missing Gamepad Skip**: `CinematicNarrativeOverlay.handle_event()` omits `pg.JOYBUTTONDOWN` for button indices 0 and 2.

---

## 5. Concrete Implementation Plan

### Step 1: Add Speaker-Avatar Registry & Folder Resolver to `CinematicNarrativeOverlay`
- **File**: `src/game/ui/cinematic_narrative_overlay.py`
- Add a canonical speaker-to-avatar mapping dictionary:
  ```python
  SPEAKER_AVATAR_MAP = {
      "green monster": "assets/graphics/green_monster/idle",
      "the gatekeeper": "assets/graphics/green_monster/idle",
      "gatekeeper": "assets/graphics/green_monster/idle",
      "greenmonster": "assets/graphics/green_monster/idle",
      "blood zombie": "assets/graphics/bloodZombie/Idle",
      "bloodzombie": "assets/graphics/bloodZombie/Idle",
      "the fabricator's enforcer": "assets/wizard/Idle",
      "fire wizard": "assets/wizard/Idle",
      "firewizard": "assets/wizard/Idle",
      "dark ronin": "assets/graphics/Ronin/spr_RoninIdle_strip8.png",
      "darkronin": "assets/graphics/Ronin/spr_RoninIdle_strip8.png",
      "skeleton": "assets/skeleton/Skeleton_01_White_Idle",
      "andras": "assets/Agis",
      "andras, marquis of discord": "assets/Agis",
      "agis": "assets/Agis",
  }
  ```
- In `activate()`, resolve avatar path:
  1. Check `narrative_event.get("avatar_sprite")`.
  2. If missing, look up `narrative_event.get("speaker_name", "").lower()` in `SPEAKER_AVATAR_MAP`.
  3. If resolved path is a directory without direct PNG files, check for child folders `idle/`, `Idle/`, or pick the first directory containing PNGs.
  4. If path ends with `.png` (e.g. `spr_RoninIdle_strip8.png`), load using `AssetManager.get_animation_frames(path)`.

### Step 2: Implement Adaptive Aspect-Preserving Scaling & Viewport Placement
- **File**: `src/game/ui/cinematic_narrative_overlay.py`
- Calculate available presentation viewport above the dialogue card:
  - `card_y = self._height - card_h - 25` (515px on 720p).
  - Define target bounding box:
    - `target_max_w = min(int(self._width * 0.45), 450)`
    - `target_max_h = min(int(card_y - 40), 400)`
- For each raw frame loaded:
  - Calculate aspect-preserving scale factor:
    `scale = min(target_max_w / raw_w, target_max_h / raw_h)`
  - For small pixel-art sprites (`raw_w <= 96 and raw_h <= 96`), allow scale up to 3.5x–4.0x while staying within `target_max_w` and `target_max_h`.
  - Scale surfaces using `pg.transform.smoothscale(img, (int(raw_w * scale), int(raw_h * scale)))`.
- In `draw()`, position avatar centered in the upper viewport:
  - `av_x = (self._width - frame.get_width()) // 2`
  - `av_y = max(20, (card_y - frame.get_height()) // 2)`
  - *Guarantee*: Avatar bottom edge (`av_y + frame.get_height()`) is strictly less than `card_y - 10`, eliminating any overlap with the dialogue card, while `av_y >= 20` prevents top-edge clipping.

### Step 3: Replace Solid Black Void with Atmospheric Semi-Transparent Vignette
- **File**: `src/game/ui/cinematic_narrative_overlay.py`
- Modify `_rebuild_vignette()`:
  - Use `(0, 0, 0, 160)` (semi-transparent dark scrim) for standard dialogue so the gameplay world, characters, and arena remain visible in atmospheric slow motion.
  - Retain deeper darkness `(0, 0, 0, 240)` only when `_is_book_ritual` is `True` (as specified for the grimoire occult void).

### Step 4: Update `BossEncounterManager` to Pass Speaker & Avatar Metadata
- **File**: `src/game/systems/boss_encounter_manager.py`
- In `begin_encounter(boss_name, boss_entity)`:
  - Store `self._boss_name = boss_name` and display title `self._boss_title = getattr(boss_entity, "boss_title", boss_name)`.
  - Extract sprite root: `self._boss_sprite_path = getattr(boss_entity, "_base_path", None) or getattr(boss_entity, "sprite_root", None)`.
- In `_show_next_line()`:
  - Pass `speaker_name=self._boss_title` and `avatar_sprite=self._boss_sprite_path` to the overlay:
    ```python
    event = {
        "speaker_name": self._boss_title,
        "avatar_sprite": self._boss_sprite_path,
        "dialogue_text": line,
        "option_1_label": "[SPACE] Continue",
    }
    self._overlay.activate(event)
    ```
- Update `show_bark()` in `CinematicNarrativeOverlay`:
  - Accept optional `speaker_name: Optional[str] = None` and `avatar_sprite: Optional[str] = None`.

### Step 5: Implement Gamepad Dialogue Advance & Skip (Requirement R2)
- **File**: `src/game/ui/cinematic_narrative_overlay.py`
- In `handle_event(self, event: pg.event.Event)`:
  ```python
  if event.type == pg.JOYBUTTONDOWN:
      # button 0 = PlayStation Cross/X; button 2 = Xbox X
      if event.button in (0, 2):
          self._select_option(1)
          return True
  ```

---

## 6. Verification Method

### 6.1 Automated Test Verification
Run the complete test suite to ensure zero regressions:
```bash
pytest tests/
```
Targeted test commands:
```bash
pytest tests/test_cinematic_narrative_overlay.py
pytest tests/test_narrative_backbone.py
```

### 6.2 New Dedicated Tests to Add
Create `tests/test_narrative_overlay_sprites.py` containing:
1. `test_green_monster_sprite_loading_and_bounding_box()`:
   - Activate overlay with `speaker_name="The Gatekeeper"`, `avatar_sprite="assets/graphics/green_monster"`.
   - Assert `len(overlay._avatar_frames) > 0`.
   - Assert `frame.get_width() <= 450` and `frame.get_height() <= 400`.
   - Assert `av_y + frame.get_height() < card_y`.
2. `test_boss_encounter_manager_passes_speaker_and_avatar()`:
   - Verify `BossEncounterManager._show_next_line()` activates overlay with non-empty `speaker_name` and `avatar_sprite`.
3. `test_gamepad_skip_button_0_and_2()`:
   - Send `pg.event.Event(pg.JOYBUTTONDOWN, button=0)` -> assert `handled == True` and `overlay.is_active == False`.
   - Send `pg.event.Event(pg.JOYBUTTONDOWN, button=2)` -> assert `handled == True` and `overlay.is_active == False`.
4. `test_vignette_transparency()`:
   - Assert `overlay._vignette_surface.get_at((100, 100))[3] < 255` when ritual is false.

### 6.3 Invalidation Conditions
- If `overlay._avatar_frames` remains empty when `Green Monster` speaks.
- If any avatar frame dimensions exceed `450x420` or overlap `card_y`.
- If `JOYBUTTONDOWN` event with button 0 or 2 returns `False`.
- If any existing unit test in `tests/` fails.
