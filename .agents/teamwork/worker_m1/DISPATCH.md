## 2026-11-03T11:52:24Z
You are Worker M1 for Pixel Runner.
Your working directory is: c:\Users\Chosen033\Documents\Pixel-Runner\.agents\teamwork\worker_m1\

MANDATORY FIRST STEP:
Read c:\Users\Chosen033\Documents\Pixel-Runner\.agents\teamwork\ORIGINAL_REQUEST.md before starting work.
Also read the project architecture and Explorer 1's detailed findings:
- Scope: c:\Users\Chosen033\Documents\Pixel-Runner\.agents\teamwork\orchestrator_1\PROJECT.md
- Technical findings: c:\Users\Chosen033\Documents\Pixel-Runner\.agents\teamwork\teamwork_explorer_survey_1\handoff.md

OBJECTIVE:
Implement Milestone 1: Monster and Boss Sprite Presentation in Cinematic Narrative Overlay (Requirements F1-F5).

Detailed Implementation Steps:
1. In `src/game/ui/cinematic_narrative_overlay.py`:
   - Add canonical `SPEAKER_AVATAR_MAP` mapping speaker names (e.g. "green monster", "the gatekeeper", "gatekeeper", "blood zombie", "the fabricator's enforcer", "fire wizard", "dark ronin", "andras", "agis", "skeleton") to their respective sprite folders/strips.
   - In `activate()`, resolve the avatar sprite path:
     - Check `narrative_event.get("avatar_sprite")`. If missing, look up `narrative_event.get("speaker_name", "").lower()` in `SPEAKER_AVATAR_MAP`.
     - Implement robust directory/file resolution: if the given path is a directory with no direct PNGs, check child subfolders (e.g. `idle/`, `Idle/`, etc.) or select the first child folder containing PNGs. If it's a sprite strip PNG (e.g. `spr_RoninIdle_strip8.png`), load via `AssetManager.get_animation_frames(path)`.
   - Implement adaptive aspect-preserving scaling:
     - Calculate target bounding box above dialogue card: `target_max_w = min(int(self._width * 0.45), 450)` and `target_max_h = min(int(card_y - 40), 400)`.
     - Smoothscale raw frames preserving aspect ratio (`scale = min(target_max_w / raw_w, target_max_h / raw_h)`).
   - In `draw()`, position the avatar cleanly centered above the dialogue card:
     - `av_x = (self._width - frame.get_width()) // 2`
     - `av_y = max(20, (card_y - frame.get_height()) // 2)`
     - Ensure the avatar never overlaps the dialogue card (`av_y + frame.get_height() < card_y`) and never clips top/side borders.
   - Replace solid black void in `_rebuild_vignette()`:
     - Use semi-transparent dark atmospheric scrim `(0, 0, 0, 160)` for standard dialogue so the gameplay world and characters remain visible. Deeper dark `(0, 0, 0, 240)` only for `_is_book_ritual`.
   - Update `show_bark()`:
     - Add optional parameters `speaker_name: Optional[str] = None` and `avatar_sprite: Optional[str] = None` and forward them into the event dictionary passed to `activate()`.

2. In `src/game/systems/boss_encounter_manager.py`:
   - In `begin_encounter(boss_name, boss_entity)`:
     - Retain boss display title `self._boss_title = getattr(boss_entity, "boss_title", boss_name)` and sprite path `self._boss_sprite_path = getattr(boss_entity, "_base_path", None) or getattr(boss_entity, "sprite_root", None)`.
   - In `_show_next_line()`:
     - When calling `self._overlay.show_bark()` or `self._overlay.activate()`, pass `speaker_name=self._boss_title` and `avatar_sprite=self._boss_sprite_path`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

EXCLUSIVE WRITE OWNERSHIP:
- You exclusively own:
  - `src/game/ui/cinematic_narrative_overlay.py`
  - `src/game/systems/boss_encounter_manager.py`
- DO NOT modify any other files.

VERIFICATION:
- Run verification tests using PowerShell:
  `$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest tests/`
- Ensure your changes compile, import cleanly, and don't introduce regressions.

OUTPUT:
- Write your complete handoff report to `c:\Users\Chosen033\Documents\Pixel-Runner\.agents\teamwork\worker_m1\handoff.md`.
- Report completion via `send_message` to the parent orchestrator.
