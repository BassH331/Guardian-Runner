# Project: Cinematic Narrative Overlay Monster Sprites & Controller Skip

## Architecture
- **Cinematic Narrative Overlay (`src/game/ui/cinematic_narrative_overlay.py`)**:
  - Full-screen dialogue overlay triggered during boss encounters, grimoire rituals, and narrative milestones.
  - Features speaker label, typewriter animated text, option choices, animated sprite presentation, and atmospheric vignette.
  - Resolves monster/boss avatars via `SPEAKER_AVATAR_MAP` and directory crawling (`idle/` subfolders or sprite strips).
  - Implements dynamic aspect-preserving scaling constrained to `(450px x 400px)` viewport strictly above dialogue card (`card_y = 515px`).
  - Listens to both keyboard (`SPACE`, `RETURN`) and controller `JOYBUTTONDOWN` events (button 0 = PS Cross/X, button 2 = Xbox X).
- **Boss Encounter Manager (`src/game/systems/boss_encounter_manager.py`)**:
  - Manages boss combat intro sequences, freezes boss AI, iterates pre-fight dialogue queue.
  - Passes boss speaker title and entity sprite path to narrative overlay upon line delivery.
- **Controller Cutscene Advance Parity (`cutscene_manager.py`, `objective_display.py`, `story_state.py`, `ending_state.py`)**:
  - Unified gamepad skip mapping: both button 0 (PS Cross) and button 2 (Xbox X) advance/skip cutscenes.
- **Automated Verification Layer (`tests/test_narrative_overlay_presentation_and_controller.py`, `tests/test_monster_avatar_presentation.py`)**:
  - Headless Pygame test suite verifying sprite loading, layout constraints, surface non-blank rendering, controller event handling, and pre-fight dialogue integration.

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Speaker-Avatar Mapping & Folder Resolver | Map speaker names (Green Monster, Gatekeeper, Blood Zombie, Fire Wizard, Dark Ronin, Andras) to sprite folders/strips and resolve nested action folders (e.g. `idle/`). | M1 | Survey (Explorer 1) [DONE] |
| F2 | Adaptive Aspect-Preserving Avatar Scaling | Calculate bounding box above dialogue card (`max_w <= 450`, `max_h <= 400`) and scale frames smoothly without overflow. | M1 | Survey (Explorer 1) [DONE] |
| F3 | Non-Clipping Viewport Centering | Position avatar horizontally centered and vertically bounded above `card_y` (`av_y >= 20`, `av_y + height < card_y - 10`). | M1 | Survey (Explorer 1) [DONE] |
| F4 | Atmospheric Dark Scrim Vignette | Replace solid black void `(0, 0, 0, 255)` with semi-transparent scrim `(0, 0, 0, 160)` for standard dialogue so background world is visible. | M1 | Survey (Explorer 1) [DONE] |
| F5 | BossEncounterManager Metadata Forwarding | Retain boss title and sprite root in `begin_encounter()` and forward `speaker_name` and `avatar_sprite` in `_show_next_line()`. | M1 | Survey (Explorer 1) [DONE] |
| F6 | Controller X Button Dialogue Skip in Narrative Overlay | Handle `pg.JOYBUTTONDOWN` in `CinematicNarrativeOverlay.handle_event`: button 0 (PS Cross) and button 2 (Xbox X) advance/skip dialogue. | M2 | Survey (Explorer 2) |
| F7 | Secondary Cutscene Gamepad Skip Parity | Add button 2 to `cutscene_manager.py`, `objective_display.py`, `story_state.py`, and `ending_state.py` for full controller parity. | M2 | Survey (Explorer 2) |
| F8 | Keyboard & Mouse Dialogue Input Invariance | Ensure keyboard `SPACE`, `RETURN`, `1`, `2`, `ESCAPE` and mouse clicks continue to function identically with zero regression. | M2 | Survey (Explorer 2) |
| F9 | Narrative Overlay Automated Verification Suite | Implement `tests/test_narrative_overlay_presentation_and_controller.py` covering sprite loading, bounding box constraints, non-blank rendering, and gamepad skip. | M3 | Survey (Explorer 3) |
| F10 | Full Regression & Adversarial Gate | 100% pass rate across entire repository test suite (`pytest tests/`), Tier 5 adversarial stress testing, and forensic audit. | M4 | Survey (Explorer 3) |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Monster/Boss Sprite Presentation in Narrative Overlay | Implement F1-F5 in `cinematic_narrative_overlay.py` and `boss_encounter_manager.py`. | None | DONE |
| M2 | Controller X Button Dialogue Skip | Implement F6-F8 in `cinematic_narrative_overlay.py` and secondary cutscene systems. | M1 | PLANNED |
| M3 | Automated Test Verification Suite | Implement F9 in `tests/test_narrative_overlay_presentation_and_controller.py`. | M1, M2 | PLANNED |
| M4 | Final Milestone (100% Pass, Adversarial Hardening & Forensic Audit) | Execute F10: full pytest run, adversarial review, and forensic integrity audit. | M1, M2, M3 | PLANNED |

---

## Interface Contracts

### `CinematicNarrativeOverlay.activate(narrative_event, on_dismiss=None)`
- `narrative_event`: Dictionary accepting:
  - `"dialogue_text"`: str (mandatory)
  - `"speaker_name"`: Optional[str] (resolved against `SPEAKER_AVATAR_MAP` if `avatar_sprite` not provided)
  - `"avatar_sprite"`: Optional[str] (path to directory or PNG sprite strip)
  - `"option_1_label"`: str (e.g. `"[SPACE] / [X] Continue"`)
  - `"option_2_label"`: Optional[str]

### `CinematicNarrativeOverlay.show_bark(text, speaker=None, speaker_name=None, avatar_sprite=None)`
- Forwards `text`, `speaker_name`, and `avatar_sprite` to `activate()`.

### `CinematicNarrativeOverlay.handle_event(event)`
- Returns `True` if event was consumed (prevents background gameplay actions during dialogue).
- Consumes `pg.KEYDOWN` (`K_SPACE`, `K_RETURN`, `K_1`, `K_2`, `K_ESCAPE`).
- Consumes `pg.JOYBUTTONDOWN` (`button in (0, 2)` for Option 1 / skip; `button in (1, 3)` for Option 2).
- Consumes `pg.MOUSEBUTTONDOWN`.

---

## Code Layout
- `src/game/ui/cinematic_narrative_overlay.py`: Owned by M1 [DONE] & M2
- `src/game/systems/boss_encounter_manager.py`: Owned by M1 [DONE]
- `src/game/systems/cutscene_manager.py`: Owned by M2
- `src/game/ui/objective_display.py`: Owned by M2
- `src/game/states/story_state.py`: Owned by M2
- `src/game/states/ending_state.py`: Owned by M2
- `tests/test_narrative_overlay_presentation_and_controller.py`: Owned by M3
- `tests/test_monster_avatar_presentation.py`: Created by M1 Challenger
- Existing files in `tests/`: Read-only verification targets
