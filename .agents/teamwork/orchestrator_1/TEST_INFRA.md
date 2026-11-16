# E2E Test Infra: Cinematic Narrative Overlay Presentation & Controller Skip

## Test Philosophy
- Requirement-driven, opaque-box, headless automated verification.
- Category-Partition + Boundary Value Analysis + Real-World Workload Testing.
- Zero GUI windows required: tests execute cleanly in headless mode with `SDL_VIDEODRIVER="dummy"` and `SDL_AUDIODRIVER="dummy"`.

## Feature Inventory & Test Coverage
| # | Feature | Requirement | Tier 1 (Unit) | Tier 2 (Boundary) | Tier 3 (Integration) | Tier 4 (Workload) |
|---|---------|-------------|:-------------:|:-----------------:|:--------------------:|:-----------------:|
| 1 | Speaker-Avatar Mapping & Folder Resolver | R1 | ✓ | ✓ | ✓ | ✓ |
| 2 | Adaptive Aspect-Preserving Avatar Scaling | R1 | ✓ | ✓ | ✓ | ✓ |
| 3 | Non-Clipping Viewport Centering | R1 | ✓ | ✓ | ✓ | ✓ |
| 4 | Atmospheric Dark Scrim Vignette | R1 | ✓ | ✓ | ✓ | ✓ |
| 5 | BossEncounterManager Metadata Forwarding | R1 | ✓ | ✓ | ✓ | ✓ |
| 6 | Controller X Button Dialogue Skip (Overlay) | R2 | ✓ | ✓ | ✓ | ✓ |
| 7 | Secondary Cutscene Gamepad Skip Parity | R2 | ✓ | ✓ | ✓ | ✓ |
| 8 | Keyboard & Mouse Dialogue Invariance | R2 | ✓ | ✓ | ✓ | ✓ |
| 9 | Comprehensive Narrative Verification Suite | R3 | ✓ | ✓ | ✓ | ✓ |
| 10 | 100% Repository Pass Rate (Zero Regressions) | R3 | ✓ | ✓ | ✓ | ✓ |

## Test Architecture
- **Location**: `tests/test_narrative_overlay_presentation_and_controller.py`
- **Runner**:
  - Windows: `$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest tests/test_narrative_overlay_presentation_and_controller.py -v`
  - Full suite: `$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest`
- **Pass Criteria**:
  - 100% test pass rate with exit code 0.
  - No uncaught exceptions, no assertion failures, zero regressions on existing tests.

## Planned Test Scenarios
1. `test_speaker_avatar_map_resolution`: Verify all speaker names resolve to valid image assets (Green Monster, Blood Zombie, Fire Wizard, Dark Ronin, Andras).
2. `test_nested_idle_folder_resolution`: Verify directory paths without direct PNGs correctly locate nested `idle/` subdirectories.
3. `test_avatar_adaptive_scaling_bounds`: Verify loaded frames are scaled to fit within `(450, 400)` viewport without overflowing 1280x720 canvas.
4. `test_avatar_viewport_positioning_and_no_clipping`: Verify `av_y >= 20` and `av_y + h < card_y - 10`.
5. `test_vignette_atmospheric_transparency`: Verify standard dialogue vignette uses semi-transparent `(0, 0, 0, 160)` rather than solid opaque black.
6. `test_dialogue_text_and_speaker_title_concurrency`: Verify typewriter text and speaker label render concurrently with avatar sprite.
7. `test_controller_x_button_skip_ps_and_xbox`: Verify `JOYBUTTONDOWN` button 0 (PS Cross) and button 2 (Xbox X) advance/skip dialogue.
8. `test_keyboard_and_mouse_skip_invariance`: Verify `K_SPACE`, `K_RETURN`, and mouse click advance/skip dialogue identically.
9. `test_boss_encounter_manager_pre_fight_forwarding`: Verify `BossEncounterManager.begin_encounter()` forwards speaker name and avatar sprite on `_show_next_line()`.
10. `test_secondary_cutscene_controller_button2_parity`: Verify `CutsceneManager`, `ObjectiveDisplay`, `StoryState`, and `EndingState` support button index 2.
