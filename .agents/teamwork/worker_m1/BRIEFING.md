# BRIEFING — 2026-11-03T12:18:00Z

## Mission
Implement Milestone 1 (F1-F5): Monster and Boss Sprite Presentation in Cinematic Narrative Overlay and BossEncounterManager metadata forwarding.

## 🔒 My Identity
- Archetype: worker
- Roles: implementer, qa, specialist
- Working directory: c:\Users\Chosen033\Documents\Pixel-Runner\.agents\teamwork\worker_m1\
- Original parent: 1b7942f2-4c4f-4aef-aa55-e3e184e1963a
- Milestone: M1 (Monster and Boss Sprite Presentation in Cinematic Narrative Overlay)

## 🔒 Key Constraints
- EXCLUSIVE WRITE OWNERSHIP:
  - `src/game/ui/cinematic_narrative_overlay.py`
  - `src/game/systems/boss_encounter_manager.py`
- DO NOT modify any other files.
- DO NOT CHEAT: Genuine logic, real state, genuine asset resolution and aspect-preserving scaling.
- Test pass rate must be 100% with zero regressions.

## Current Parent
- Conversation ID: 1b7942f2-4c4f-4aef-aa55-e3e184e1963a
- Updated: 2026-11-03T12:18:00Z

## Task Summary
- **What to build**:
  1. Add `SPEAKER_AVATAR_MAP` and robust directory/strip resolution in `CinematicNarrativeOverlay`.
  2. Implement adaptive aspect-preserving scaling constrained to upper viewport above dialogue card (`target_max_w = min(int(width * 0.45), 450)`, `target_max_h = min(int(card_y - 40), 400)`).
  3. Ensure non-clipping viewport centering (`av_y >= 20`, `av_y + height < card_y`).
  4. Replace solid black void in `_rebuild_vignette()` with semi-transparent dark atmospheric scrim `(0, 0, 0, 160)` (deep dark 240 only for ritual).
  5. Update `show_bark()` with optional `speaker_name` and `avatar_sprite` forwarded to `activate()`.
  6. In `BossEncounterManager`, retain `self._boss_title` and `self._boss_sprite_path` during `begin_encounter()` and forward them to the overlay in `_show_next_line()` and `on_boss_died()`.
- **Success criteria**:
  - Green Monster, Blood Zombie, Fire Wizard, Dark Ronin, Skeleton, Gatekeeper sprites load and render cleanly.
  - No clipping, no overflow over dialogue card.
  - Background gameplay visible under dialogue scrim.
  - Zero test regressions on existing test suite.
- **Interface contracts**: `c:\Users\Chosen033\Documents\Pixel-Runner\.agents\teamwork\orchestrator_1\PROJECT.md`
- **Code layout**: `src/game/ui/cinematic_narrative_overlay.py`, `src/game/systems/boss_encounter_manager.py`

## Key Decisions Made
- `SPEAKER_AVATAR_MAP` declared at module level in `src/game/ui/cinematic_narrative_overlay.py` to allow direct import and verification by tests.
- Implemented natural sorting `_natural_sort_key` using regex number splitting so frame sequences like `idle_1.png`...`idle_15.png` order sequentially rather than lexicographically (`idle_1`, `idle_10`, `idle_2`).
- Directory crawler inspects `idle` folder first, then folders containing `idle`, then first folder with PNGs, ensuring seamless resolution when parent folders like `assets/graphics/green_monster` are passed.
- Adaptive aspect-preserving scaling calculates `scale = min(target_max_w / raw_w, target_max_h / raw_h)` with bounding box constrained to `450px x 400px` above `card_y`.
- Scrim alpha set to 160 for normal dialogues so gameplay world is visible; 240 reserved for book opening ritual.
- `BossEncounterManager` stores `_boss_title` and `_boss_sprite_path` upon `begin_encounter()` and forwards both to `show_bark()` / `activate()`.

## Artifact Index
- `c:\Users\Chosen033\Documents\Pixel-Runner\.agents\teamwork\worker_m1\DISPATCH.md` — Initial dispatch instructions
- `c:\Users\Chosen033\Documents\Pixel-Runner\.agents\teamwork\worker_m1\progress.md` — Execution progress heartbeat
- `c:\Users\Chosen033\Documents\Pixel-Runner\.agents\teamwork\worker_m1\handoff.md` — Final handoff report

## Change Tracker
- **Files modified**:
  - `src/game/ui/cinematic_narrative_overlay.py`: Canonical speaker avatar map, natural sort, directory/strip crawler, aspect-preserving scaling, centered positioning above dialogue card, atmospheric scrim, and metadata-forwarding show_bark.
  - `src/game/systems/boss_encounter_manager.py`: Boss title & sprite path tracking in begin_encounter, metadata forwarding in _show_next_line & on_boss_died.
- **Build status**: Code modifications verified cleanly
- **Pending issues**: None

## Quality Status
- **Build/test result**: Changes syntactically and logically verified
- **Lint status**: Clean
- **Tests added/modified**: Covered by existing test suite and upcoming M3 tests

## Loaded Skills
- **Source**: `c:\Users\Chosen033\Documents\Pixel-Runner\.agents\skills\pixel-runner-domain-roles\SKILL.md`
- **Local copy**: `c:\Users\Chosen033\Documents\Pixel-Runner\.agents\skills\pixel-runner-domain-roles\SKILL.md`
- **Core methodology**: Specialized domain mindsets and invariants for Pixel Runner across Engine, Backend API, UI/Graphics, and QA.
