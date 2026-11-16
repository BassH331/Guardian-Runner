"""
capture_readme_screenshots.py — Headless gameplay capture for the README.

Runs the real GameState through the StateManager with a tiny scripted "bot"
pressing keys (run right, attack enemies in range, jump occasionally), and
saves a frame every N ticks to an output folder (default: scratch/readme_capture,
which is git-ignored). Nothing is posed: every frame is produced by the actual
update/draw loop. Pick the best frames and copy them into docs/screenshots/.

Usage (from the repo root):
    .venv\\Scripts\\python.exe tools/capture_readme_screenshots.py [out_dir] [seconds] [every_n_ticks]
"""

import os
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.setdefault("GAME_LEVEL_PATH", "game_data/level_1.json")
# Keep argparse inside GameState from picking up our CLI args.
_cli = sys.argv[1:]
sys.argv = sys.argv[:1]

import pygame as pg

pg.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
pg.init()
try:
    pg.mixer.init()
except Exception:
    pass

W, H = 1280, 720
screen = pg.display.set_mode((W, H))

OUT = pathlib.Path(_cli[0]) if len(_cli) > 0 else ROOT / "scratch" / "readme_capture"
SECONDS = float(_cli[1]) if len(_cli) > 1 else 90.0
EVERY = int(_cli[2]) if len(_cli) > 2 else 30
OUT.mkdir(parents=True, exist_ok=True)

from v3x_zulfiqar_gideon import UITheme, StateManager, AudioManager  # noqa: E402

UITheme.configure_buttons(
    assets={
        "big": ("assets/graphics/UI/PNG/TextBTN_Big.png", "assets/graphics/UI/PNG/TextBTN_Big_Pressed.png"),
        "medium": ("assets/graphics/UI/PNG/TextBTN_Medium.png", "assets/graphics/UI/PNG/TextBTN_Medium_Pressed.png"),
        "cancel": ("assets/graphics/UI/PNG/TextBTN_Cancel.png", "assets/graphics/UI/PNG/TextBTN_Cancel_Pressed.png"),
        "new_start": ("assets/graphics/UI/PNG/TextBTN_New-Start.png", "assets/graphics/UI/PNG/TextBTN_New-Start_Pressed.png"),
    },
    font_path="assets/Colorfiction_HandDrawnFonts/Colorfiction - Papyrus.otf",
)
UITheme.configure_notifications(
    banner_path="assets/graphics/UI/PNG/IRONY TITLE  Large.png",
    icons={
        "gray": "assets/graphics/UI/PNG/Exclamation_Gray.png",
        "red": "assets/graphics/UI/PNG/Exclamation_Red.png",
        "yellow": "assets/graphics/UI/PNG/Exclamation_Yellow.png",
    },
    font_path="assets/font/Abaddon Bold.ttf",
)
UITheme.configure_overlays(
    stone_path="assets/graphics/UI/PNG/UI board Medium  stone.png",
    parchment_path="assets/graphics/UI/PNG/UI board Medium  parchment.png",
    title_font_path="assets/font/Abaddon Bold.ttf",
    body_font_path="assets/graphics/Darinia/Darinia.ttf",
    text_color=(60, 40, 20),
    font_size=32,
    backdrop_alpha=170,
)

audio_manager = AudioManager()
state_manager = StateManager(audio_manager=audio_manager)

DT = 1000.0 / 60.0


def save(surface: pg.Surface, name: str) -> None:
    pg.image.save(surface, str(OUT / f"{name}.png"))


# ── Front-end screens ────────────────────────────────────────────────────────
try:
    from src.game.states.main_menu_state import MainMenuState

    menu = MainMenuState(state_manager)
    for _ in range(20):
        menu.update(DT)
    menu.draw(screen)
    save(screen, "menu_main")
except Exception as e:  # pragma: no cover - capture tool
    print(f"[menu] {e}")

try:
    from src.game.states.story_state import StoryState

    story = StoryState(state_manager)
    for i in range(1, 60 * 20 + 1):
        story.update(DT)
        if i % 180 == 0:
            story.draw(screen)
            save(screen, f"story_{i:05d}")
except Exception as e:  # pragma: no cover
    print(f"[story] {e}")


# ── Scripted input ───────────────────────────────────────────────────────────
class BotKeys:
    def __init__(self) -> None:
        self.down: set[int] = set()

    def __getitem__(self, key: int) -> bool:
        return key in self.down


bot = BotKeys()
pg.key.get_pressed = lambda: bot  # type: ignore[assignment]

from src.game.states.game_state import GameState  # noqa: E402

game = GameState(state_manager)
state_manager.push(game)


def post_key(key: int) -> None:
    for etype in (pg.KEYDOWN, pg.KEYUP):
        state_manager.handle_event(pg.event.Event(etype, key=key, mod=0, unicode="", scancode=0))


ATTACKS = [pg.K_q, pg.K_e, pg.K_q, pg.K_w]
total_ticks = int(SECONDS * 60)
attack_i = 0

for tick in range(1, total_ticks + 1):
    pg.event.pump()
    bot.down.clear()

    top = state_manager.current_state if hasattr(state_manager, "current_state") else None
    player = game.player.sprite if game.player else None

    # Keep the demo run alive so we can see the whole level.
    if player is not None:
        for attr in ("health", "current_health", "hp"):
            max_attr = {"health": "max_health", "current_health": "max_health", "hp": "max_hp"}[attr]
            if hasattr(player, attr) and hasattr(player, max_attr):
                try:
                    setattr(player, attr, getattr(player, max_attr))
                except Exception:
                    pass

    # Dismiss dialogue / tutorial overlays every ~1.5 s.
    if tick % 90 == 0:
        post_key(pg.K_SPACE)
        post_key(pg.K_RETURN)

    if player is not None:
        enemies_ahead = [
            e for e in game.obstacle_group
            if -120 < e.rect.centerx - player.rect.centerx < 260 and not getattr(e, "is_dead", False)
        ]
        if enemies_ahead:
            if tick % 20 == 0:
                bot.down.add(ATTACKS[attack_i % len(ATTACKS)])
                attack_i += 1
            nearest = min(enemies_ahead, key=lambda e: abs(e.rect.centerx - player.rect.centerx))
            if nearest.rect.centerx < player.rect.centerx:
                bot.down.add(pg.K_LEFT)
        else:
            bot.down.add(pg.K_RIGHT)
            if tick % 150 < 12:
                bot.down.add(pg.K_SPACE)

    state_manager.update(DT)
    try:
        audio_manager.update()
    except Exception:
        pass

    if tick % EVERY == 0:
        state_manager.draw(screen)
        n_enemies = len(game.obstacle_group)
        save(screen, f"play_{tick:05d}_e{n_enemies}")

print(f"done -> {OUT}")
pg.quit()

