# Test Infrastructure & Verification Strategy Handoff Report

## 1. Observation

### 1.1 Test Suite Architecture & Headless Pygame Environment
- **Configuration (`pytest.ini:1-4`)**:
  ```ini
  [pytest]
  testpaths = tests
  norecursedirs = scratch venv .venv .git
  ```
- **Headless Environment Setup (`tests/conftest.py:5-32`)**:
  ```python
  os.environ["SDL_VIDEODRIVER"] = "dummy"
  os.environ["SDL_AUDIODRIVER"] = "dummy"
  os.environ["DISABLE_TELEMETRY"] = "1"

  @pytest.fixture(scope="session", autouse=True)
  def init_headless_pygame():
      """Ensure headless SDL video driver, font system, and display surface are initialized for all tests."""
      pg.init()
      pg.font.init()
      try:
          pg.mixer.init()
      except Exception:
          pass
      screen = pg.display.set_mode((1280, 720))
      ...
  ```
- **Cache Management (`tests/conftest.py:33-70`)**:
  - `reset_asset_manager_font_cache`: invokes `AssetManager.clear()` and confirms `pg.font.init()` is healthy before and after each test.
  - `reset_hitbox_registry_cache`: resets `HitboxRegistry._cached_config` and `_rollback_checkpoint` before and after each test.
- **Test Invocation Baseline (`TEST_INFRA.md:25`)**:
  - Headless runner: `$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest` or `PYTHONPATH=. pytest`.

### 1.2 Existing Overlay, Dialogue, and Input Tests
- **`tests/test_cinematic_narrative_overlay.py`**:
  - Lines 42-47: `test_cinematic_narrative_overlay_initial_state()` verifies `is_active` defaults to `False`.
  - Lines 49-64: `test_cinematic_narrative_overlay_activation()` verifies `activate(evt)` sets `is_active = True` and copies `dialogue_text`.
  - Lines 75-95: `test_cinematic_narrative_overlay_keypress_choice_selection()` tests `pg.event.Event(pg.KEYDOWN, key=pg.K_1)` selects choice 1.
  - Lines 108-135: `test_cinematic_narrative_overlay_space_and_return_advance()` tests `pg.event.Event(pg.KEYDOWN, key=pg.K_SPACE)` and `pg.event.Event(pg.KEYDOWN, key=pg.K_RETURN)` advance monologue dialogue.
  - *Gap observed*: No tests exist for controller buttons (`JOYBUTTONDOWN`), nor for monster/boss avatar sprite presentation or layout bounding.
- **`tests/test_narrative_backbone.py`**:
  - Lines 146-170: tests book opening ritual auto-advance in overlay.
  - Lines 207-265: tests book ritual advance into Andras monologue via `pg.K_SPACE`.
  - Lines 266-295: tests book ritual single-image asset loading and drawing on surface `(1280, 720)`.
- **`tests/test_atmospheric_dialogue_overlay.py`**:
  - Lines 35-50: tests `ObjectiveDisplay` skip flow via `pg.K_RETURN`.
  - *Gap observed*: No tests exist for gamepad button advance or skip.
- **`tests/test_boss_defeat_pipeline.py`**:
  - Lines 149-154:
    ```python
    joy_event = pg.event.Event(pg.JOYBUTTONDOWN, button=0, instance_id=0)
    game_state.handle_event(joy_event)
    self.assertTrue(game_state.relic_reveal_overlay is None or not game_state.relic_reveal_overlay.is_active)
    ```
    Confirms direct instantiation of `pg.event.Event(pg.JOYBUTTONDOWN, ...)` works cleanly in headless tests without hardware.
- **`tests/test_joystick_hotplug.py`**:
  - Lines 30-43: mocks `pg.joystick.get_count` and `pg.joystick.Joystick` using `unittest.mock.patch`.

### 1.3 Implementation Analysis: Narrative Overlay and Input
- **Black Void & Missing Monster Sprite Rendering (`src/game/ui/cinematic_narrative_overlay.py:59-61, 103-127, 307-312`)**:
  - Lines 59-61:
    ```python
    self._vignette_surface = pg.Surface((self._width, self._height), pg.SRCALPHA)
    self._vignette_surface.fill((0, 0, 0, 255))
    ```
    Draws an opaque black surface covering the entire screen.
  - Lines 103-127:
    Avatar loading only inspects `avatar_path = narrative_event.get("avatar_sprite")` with special branch strictly for `assets/Agis`. If `speaker_name` is provided (e.g. "Green Monster"), it is never mapped to monster sprite assets. Furthermore, `assets/graphics/green_monster` contains subdirectories (`idle`, `walk`, `1atk`, `2atk`) and no root PNGs, which causes `AssetManager.get_animation_frames()` to fail if the root folder is passed directly.
  - Lines 307-312:
    ```python
    elif self._avatar_frames:
        frame = self._avatar_frames[self._avatar_frame_idx % len(self._avatar_frames)]
        av_x = (self._width - frame.get_width()) // 2
        av_y = (self._height - frame.get_height()) // 3
        surface.blit(frame, (av_x, av_y))
    ```
    If `_avatar_frames` is empty, no entity is drawn. Combined with the opaque black fill, the screen renders completely blank behind the dialogue card.
- **Missing Speaker Name & Avatar in Boss Dialogue (`src/game/systems/boss_encounter_manager.py:120-128` & `src/game/ui/cinematic_narrative_overlay.py:130-137`)**:
  - In `BossEncounterManager._show_next_line()`:
    ```python
    line = self._dialogue_queue.pop(0)
    if self._overlay:
        show_fn = getattr(self._overlay, "show_bark", None)
        if show_fn:
            show_fn(line, speaker=None)
    ```
  - In `CinematicNarrativeOverlay.show_bark()`:
    ```python
    event: Dict[str, Any] = {
        "dialogue_text": text,
        "option_1_label": "[SPACE] Continue",
    }
    self.activate(event)
    ```
    No `speaker_name` or monster sprite is passed, so the dialogue box defaults to header `Kimi Narrative Director` (`cinematic_narrative_overlay.py:344`) with no avatar.
- **Missing Controller Event Handling (`src/game/ui/cinematic_narrative_overlay.py:152-176`)**:
  - In `CinematicNarrativeOverlay.handle_event(event)`:
    Only `pg.KEYDOWN` and `pg.MOUSEBUTTONDOWN` are handled. `pg.JOYBUTTONDOWN` is completely unhandled.
  - In `src/game/systems/cutscene_manager.py:80-83`:
    ```python
    cutscene_advance_pressed = (
        (event.type == pg.KEYDOWN and event.key in (pg.K_RETURN, pg.K_SPACE, pg.K_e, pg.K_x)) or
        (event.type == pg.JOYBUTTONDOWN and event.button in (0, 1, 6))
    )
    ```
    Only buttons `(0, 1, 6)` are handled. Button 2 (Xbox X) is absent.
  - In `src/game/ui/objective_display.py:152-155`:
    ```python
    is_trigger = (
        (event.type == pg.KEYDOWN and event.key in (pg.K_SPACE, pg.K_RETURN, pg.K_x))
        or (event.type == pg.JOYBUTTONDOWN and event.button in (0, 6))
    )
    ```
    Only buttons `(0, 6)` are handled. Button 2 (Xbox X) is absent.
- **Available Boss / Monster Sprite Assets on Disk**:
  - Green Monster / Gatekeeper: `assets/graphics/green_monster/idle/` (`idle_1.png` to `idle_14.png`).
  - Blood Zombie: `assets/graphics/bloodZombie/Idle/` (`blood_idle_00.png` to `blood_idle_15.png`).
  - Fire Wizard: `assets/graphics/Wizard_NPC/` (`wizard_npc_0.png` to `wizard_npc_5.png`).
  - Dark Ronin: `assets/graphics/Ronin/spr_RoninIdle_strip8_frames/` (`frame_000.png` to `frame_007.png`).
  - Andras: `assets/Agis/` (`Agis_00.png` to `Agis_14.png`).

---

## 2. Logic Chain

1. **Test Environment Feasibility (conftest.py → headless runner)**:
   - Observation 1.1 shows that `tests/conftest.py` configures `SDL_VIDEODRIVER="dummy"` and establishes an active 1280x720 display surface with font and theme caches.
   - Observation 1.2 shows that `tests/test_boss_defeat_pipeline.py:150` dispatches `pg.event.Event(pg.JOYBUTTONDOWN, button=0)` without requiring physical controllers.
   - Therefore, programmatic automated tests verifying both sprite rendering (surface drawing and pixel/bounds validation) and controller button handling can be run headlessly under pytest with zero hardware dependencies.

2. **Root Cause of R1 Defect (Blank Screen & Missing Monster Sprites)**:
   - In `cinematic_narrative_overlay.py:59-61`, the vignette fill is `(0, 0, 0, 255)` (opaque black).
   - In `cinematic_narrative_overlay.py:103-127`, `activate()` does not resolve monster or boss speaker names to asset directories, and does not navigate into nested `idle/` subdirectories.
   - In `boss_encounter_manager.py:125-127`, `_show_next_line()` invokes `show_bark(line, speaker=None)`, omitting the boss name and sprite.
   - As a result, when Green Monster or any boss encounters trigger narrative dialogue, `_avatar_frames` is empty, leaving only the opaque black void and a generic "Kimi Narrative Director" text card on screen.
   - Therefore, the test suite must explicitly assert that:
     (a) Given any narrative speaker (Green Monster, Gatekeeper, Blood Zombie, Fire Wizard, Dark Ronin, Andras), avatar frames are non-empty.
     (b) The monster sprite bounding rect is scaled and positioned above the dialogue card within `[0, 0, 1280, 515]` without clipping.
     (c) The rendered surface in the monster region contains non-black sprite pixels (confirming the entity is visible, not covered by black void).
     (d) Dialogue text is concurrently displayed with the correct speaker tag.

3. **Root Cause of R2 Defect (Controller X Button Skip Failure)**:
   - `cinematic_narrative_overlay.py:152-176` has no branch for `pg.JOYBUTTONDOWN`.
   - `cutscene_manager.py:82` only checks `button in (0, 1, 6)`, omitting button 2 (Xbox X).
   - `objective_display.py:154` only checks `button in (0, 6)`, omitting button 2 (Xbox X).
   - `controls_config.json` and `controls_manager.py:70-72` define Button 0 as PlayStation Cross/X and Button 2 as Xbox X.
   - Therefore, tests must explicitly assert that:
     (a) `JOYBUTTONDOWN` with `button=0` advances/skips dialogue.
     (b) `JOYBUTTONDOWN` with `button=2` advances/skips dialogue.
     (c) `KEYDOWN` with `key=pg.K_SPACE` and `key=pg.K_RETURN` continues to advance dialogue without regression.

4. **Regression Prevention & Architecture (R3)**:
   - Existing tests (`test_cinematic_narrative_overlay.py`, `test_narrative_backbone.py`, `test_atmospheric_dialogue_overlay.py`) must continue to pass without regression.
   - The method signature of `CinematicNarrativeOverlay.activate()` and `show_bark()` must maintain backwards compatibility (optional kwargs with defaults).
   - A dedicated test module `tests/test_narrative_overlay_presentation_and_controller.py` along with targeted additions to `tests/test_cinematic_narrative_overlay.py` provides high cohesion, clear test traceability, and prevents merge conflicts.

---

## 3. Caveats

1. **Hardware Joystick Polling vs Event Queue**:
   - The game loop receives events from `pg.event.get()`. In automated tests, events are instantiated as `pg.event.Event(...)` and passed directly into `overlay.handle_event(event)`. This matches the codebase's existing pattern in `tests/test_boss_defeat_pipeline.py`.
2. **Font Glyph Availability in Headless CI**:
   - When rendering custom fonts (`Abaddon Bold.ttf`, `Darinia.ttf`), tests must rely on `UITheme` or `AssetManager` fallbacks so missing OS-specific fonts do not trigger test crashes.
3. **Alpha Channel & Color Matching in Tests**:
   - When verifying that a monster sprite is drawn onto a surface, tests should check bounding dimensions and verify that non-background pixels exist (e.g. `surface.get_at((x, y))` or checking alpha/color deltas) rather than exact RGB values, because smoothscaling and vignette tints introduce minor floating-point color shifts.

---

## 4. Conclusion

1. **Test Infrastructure Readiness**:
   - The existing test suite under `tests/` and configuration in `tests/conftest.py` is fully capable of testing monster sprite rendering, coordinate layout bounds, and gamepad input events in headless mode without mocks or C-extension rebuilds.
2. **Defect Scope**:
   - R1 is caused by lack of speaker-to-asset mapping in `CinematicNarrativeOverlay.activate()`, empty avatar handling during `show_bark()`, and an opaque black void fill.
   - R2 is caused by completely absent `JOYBUTTONDOWN` handling in `CinematicNarrativeOverlay.handle_event()` and missing button 2 (Xbox X) checks in `CutsceneManager` and `ObjectiveDisplay`.
3. **Recommended Test Suite Architecture**:
   - Create `tests/test_narrative_overlay_presentation_and_controller.py` containing comprehensive opaque-box and integration test cases covering:
     - Monster sprite loading for all 5 boss types + Andras.
     - Screen fit, scaling, and non-clipping bounds assertions (`0 <= left < right <= 1280`, `0 <= top < bottom <= 515`).
     - Concurrent typewriter text display and speaker title verification.
     - Surface non-blank pixel verification (proving monster is visible).
     - Controller button index 0 (PS Cross/X) dialogue advance/skip.
     - Controller button index 2 (Xbox X) dialogue advance/skip.
     - Keyboard SPACE and RETURN backward compatibility.
     - Integration with `BossEncounterManager.begin_encounter()`.

---

## 5. Verification Method

### 5.1 Test Execution Commands
The project test commands to verify implementation and ensure zero regressions:

```powershell
# 1. Run the dedicated narrative overlay presentation and controller test suite
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest tests/test_narrative_overlay_presentation_and_controller.py -v

# 2. Run existing cinematic narrative overlay test suite
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest tests/test_cinematic_narrative_overlay.py -v

# 3. Run all narrative and dialogue-related test suites
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest tests/test_narrative_backbone.py tests/test_narrative_polish.py tests/test_narrative_streamline.py tests/test_atmospheric_dialogue_overlay.py tests/test_animated_dialogue_renderer.py -v

# 4. Run the full repository test suite for regression verification
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest tests/
```

### 5.2 Specific Test Cases to Implement

#### Module: `tests/test_narrative_overlay_presentation_and_controller.py`

| Test Function Name | Tested Component | Acceptance Criteria / Assertions |
|---|---|---|
| `test_green_monster_sprite_loaded_and_scaled_in_overlay` | `CinematicNarrativeOverlay` | Overlay activated with `speaker_name="Green Monster"`. Asserts `len(overlay._avatar_frames) > 0`, `overlay.is_active is True`. Bounding box `av_w > 0`, `av_h > 0`, `av_x >= 0`, `av_x + av_w <= 1280`, `av_y >= 0`, `av_y + av_h <= 515`. |
| `test_all_narrative_boss_speakers_render_visibly` | `CinematicNarrativeOverlay` | Parametrized across `["Green Monster", "The Gatekeeper", "Blood Zombie", "Fire Wizard", "Dark Ronin", "Andras"]`. Asserts frames load, surface draw produces non-background pixels in sprite region (not empty black screen). |
| `test_dialogue_text_concurrent_with_monster_sprite` | `CinematicNarrativeOverlay` | When updated over 0.2s, monster animation frame advances while `_displayed_text` progresses. Speaker label matches speaker name. |
| `test_controller_x_button_0_advances_dialogue` | `CinematicNarrativeOverlay` | Dispatch `pg.event.Event(pg.JOYBUTTONDOWN, button=0)`. Asserts `handled is True`, overlay deactivates, choice callback called with buff data. |
| `test_controller_x_button_2_advances_dialogue` | `CinematicNarrativeOverlay` | Dispatch `pg.event.Event(pg.JOYBUTTONDOWN, button=2)`. Asserts `handled is True`, overlay deactivates, choice callback called with buff data. |
| `test_keyboard_space_and_return_still_advance` | `CinematicNarrativeOverlay` | Invariant test: dispatch `K_SPACE` and `K_RETURN`. Asserts dialogue advances identically to controller buttons. |
| `test_controller_x_button_advances_book_ritual` | `CinematicNarrativeOverlay` | Activate book ritual. Dispatch button 0 or button 2. Asserts ritual transitions to completion / next dialogue. |
| `test_cutscene_manager_button_2_advance` | `CutsceneManager` | Dispatch `pg.event.Event(pg.JOYBUTTONDOWN, button=2)`. Asserts `handle_advance_input` returns `True`. |
| `test_objective_display_button_2_skip` | `ObjectiveDisplay` | Dispatch `pg.event.Event(pg.JOYBUTTONDOWN, button=2)`. Asserts first press fast-forwards to COMPLETE, second press dismisses. |
| `test_boss_encounter_manager_prefight_dialogue_shows_monster` | `BossEncounterManager` | `begin_encounter("GreenMonster", boss_entity)`. Advance past freeze phase. Asserts overlay activated with Green Monster sprite and pre-fight line. |

### 5.3 Invalidation Conditions
- Any test that requires physical USB gamepad hardware (violates headless CI invariant).
- Any test that modifies global `AssetManager` or `UITheme` state without cleaning up in teardown (violates test isolation).
- Any failure in `pytest tests/` (violates 100% pass rate / zero regression rule).
