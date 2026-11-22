"""Smoke tests for pre-Level 1 flow: Splash -> MainMenu -> Settings/Controls -> StoryState."""

import os
import sys
import pygame as pg
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if not pg.get_init():
    pg.init()
if not pg.display.get_surface():
    pg.display.set_mode((1280, 720), pg.NOFRAME)

from v3x_zulfiqar_gideon import UITheme
from src.game.states.splash_state import SplashState
from src.game.states.main_menu_state import MainMenuState
from src.game.states.settings_state import SettingsState
from src.game.states.controls_state import ControlsState
from src.game.states.story_state import StoryState

UITheme.configure_buttons(
    assets={
        "big": ("assets/graphics/UI/PNG/TextBTN_Big.png", "assets/graphics/UI/PNG/TextBTN_Big_Pressed.png"),
        "medium": ("assets/graphics/UI/PNG/TextBTN_Medium.png", "assets/graphics/UI/PNG/TextBTN_Medium_Pressed.png"),
    },
    font_path="assets/font/Abaddon Bold.ttf",
)
UITheme.configure_overlays(
    stone_path="assets/graphics/UI/PNG/UI board Medium  stone.png",
    parchment_path="assets/graphics/UI/PNG/UI board Medium  parchment.png",
    title_font_path="assets/font/Abaddon Bold.ttf",
    body_font_path="assets/font/Abaddon Bold.ttf",
    text_color=(60, 40, 20),
    font_size=24,
    backdrop_alpha=170,
)


def _mock_manager():
    mgr = MagicMock()
    mgr.audio_manager = MagicMock()
    mgr.router = None
    return mgr


def test_splash_state_skip_and_render():
    os.chdir(PROJECT_ROOT)
    mgr = _mock_manager()
    splash = SplashState(mgr)
    splash.next_state = MainMenuState(mgr)
    splash.loading_timer = 0.5
    splash.state = "WAIT"
    splash.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_SPACE))
    assert splash.state == "FADE_OUT"
    surf = pg.Surface((1280, 720))
    splash.draw(surf)


def test_main_menu_buttons_navigation_and_submenus():
    os.chdir(PROJECT_ROOT)
    mgr = _mock_manager()
    menu = MainMenuState(mgr)
    labels = [lbl for lbl, _ in menu._menu_items]
    assert "NEW GAME" in labels
    assert "SETTINGS" in labels
    assert "CONTROLS" in labels
    assert "QUIT" in labels

    # Open Settings and Controls
    menu.open_settings()
    assert mgr.push.called
    pushed_settings = mgr.push.call_args[0][0]
    assert isinstance(pushed_settings, SettingsState)
    pushed_settings.draw(pg.Surface((1280, 720)))

    # Verify Cancel reverts unsaved change, while Save persists
    orig_fps = pushed_settings.current_fps
    pushed_settings._set_value("fps", 30 if orig_fps != 30 else 60)
    pushed_settings._on_cancel()
    assert pushed_settings.current_fps == orig_fps
    pushed_settings._set_value("fps", 30 if orig_fps != 30 else 60)
    pushed_settings._on_save_and_confirm()
    assert pushed_settings.settings.get("fps_cap") == (30 if orig_fps != 30 else 60)
    pushed_settings._set_value("fps", orig_fps)
    pushed_settings.settings.save()

    menu.open_controls()
    pushed_controls = mgr.push.call_args[0][0]
    assert isinstance(pushed_controls, ControlsState)
    pushed_controls.draw(pg.Surface((1280, 720)))
    pushed_controls.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE))
    assert mgr.pop.called

    # Keyboard wrap & start
    menu.time_entered = -10.0
    menu.selected_index = 0
    menu.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_DOWN))
    assert menu.selected_index == 1
    menu.draw(pg.Surface((1280, 720)))


def test_story_state_video_and_fallback_chapters():
    os.chdir(PROJECT_ROOT)
    mgr = _mock_manager()

    # Fallback chapter mode
    st_text = StoryState(mgr, text="Test chapter text", title="TEST")
    st_text.on_enter()
    st_text.update(0.05)
    st_text.draw(pg.Surface((1280, 720)))
    st_text.on_exit()

    # Full intro video mode
    st_vid = StoryState(mgr)
    st_vid.on_enter()
    assert st_vid._video_mode is True
    st_vid.update(0.05)
    st_vid.draw(pg.Surface((1280, 720)))
    st_vid.elapsed = 1.0
    st_vid.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_SPACE))
    assert st_vid.is_exiting is True
    assert st_vid._video_mode is True  # Keeps last video frame during fade-out (no chapter flash)
    st_vid.update(1000.0)
    assert st_vid._video_mode is False
    st_vid.on_exit()
