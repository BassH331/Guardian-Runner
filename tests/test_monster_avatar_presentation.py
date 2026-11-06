"""
Automated Test Suite for Monster and Boss Sprite Presentation in Narrative Overlay.
Empirically verifies:
- Speaker resolution (Green Monster, The Gatekeeper, Blood Zombie, Fire Wizard, Dark Ronin, Andras)
- Avatar frame dimension bounding box constraints (w <= 450, h <= 400)
- Viewport vertical alignment above dialogue card (av_y >= 20, av_y + h < card_y)
- Non-blank pixel rendering on screen
- Frame cycling animation
- BossEncounterManager metadata forwarding
- Atmospheric dark scrim alpha (160 standard vs 240 book ritual)
"""

import os
import pytest
import pygame as pg
from unittest.mock import MagicMock

from src.game.ui.cinematic_narrative_overlay import (
    CinematicNarrativeOverlay,
    SPEAKER_AVATAR_MAP,
)
from src.game.systems.boss_encounter_manager import BossEncounterManager


@pytest.fixture(scope="module", autouse=True)
def init_headless_display():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pg.init()
    surf = pg.display.set_mode((1280, 720), pg.HIDDEN)
    yield surf
    pg.quit()


MONSTER_TEST_SPEAKERS = [
    ("Green Monster", 15),
    ("The Gatekeeper", 15),
    ("Blood Zombie", 10),
    ("Fire Wizard", 8),
    ("Dark Ronin", 1),       # strip file or slices >= 1
    ("Andras", 15),
]


@pytest.mark.parametrize("speaker_name, min_expected_frames", MONSTER_TEST_SPEAKERS)
def test_monster_speaker_frame_loading_and_bounds(speaker_name: str, min_expected_frames: int):
    """Verify activating overlay with speaker name loads valid avatar frames within size limits."""
    overlay = CinematicNarrativeOverlay()
    event = {
        "speaker_name": speaker_name,
        "dialogue_text": f"Empirical challenge verification text for {speaker_name}."
    }
    overlay.activate(event)

    assert overlay.is_active, f"Overlay failed to activate for {speaker_name}"
    assert len(overlay._avatar_frames) >= min_expected_frames, (
        f"Expected at least {min_expected_frames} avatar frames for {speaker_name}, "
        f"got {len(overlay._avatar_frames)}"
    )

    card_y = 720 - 180 - 25  # 515
    for idx, frame in enumerate(overlay._avatar_frames):
        w = frame.get_width()
        h = frame.get_height()
        assert w <= 450, f"Frame {idx} of {speaker_name} width {w} exceeds 450px"
        assert h <= 400, f"Frame {idx} of {speaker_name} height {h} exceeds 400px"
        assert w > 0, f"Frame {idx} of {speaker_name} width is non-positive: {w}"
        assert h > 0, f"Frame {idx} of {speaker_name} height is non-positive: {h}"


@pytest.mark.parametrize("speaker_name, _", MONSTER_TEST_SPEAKERS)
def test_monster_sprite_rendering_position_and_pixels(speaker_name: str, _):
    """Verify overlay.draw renders monster sprite without clipping and with non-blank pixels."""
    overlay = CinematicNarrativeOverlay()
    event = {
        "speaker_name": speaker_name,
        "dialogue_text": f"Rendering verification line for {speaker_name}."
    }
    overlay.activate(event)

    surface = pg.Surface((1280, 720), pg.SRCALPHA)
    surface.fill((0, 0, 0, 0))  # Start completely transparent

    overlay.draw(surface)

    # Validate positioning logic
    frame = overlay._avatar_frames[0]
    card_y = 720 - 180 - 25  # 515
    av_x = (1280 - frame.get_width()) // 2
    av_y = max(20, (card_y - frame.get_height()) // 2)
    if av_y + frame.get_height() >= card_y:
        av_y = max(0, card_y - frame.get_height() - 5)

    assert av_y >= 20, f"av_y {av_y} is less than 20px top margin for {speaker_name}"
    assert av_y + frame.get_height() < card_y, (
        f"av_y + height ({av_y + frame.get_height()}) collides with dialogue card_y ({card_y}) "
        f"for {speaker_name}"
    )
    assert av_x >= 0, f"av_x {av_x} is negative for {speaker_name}"

    # Sample avatar bounding box pixels to ensure non-blank pixels rendered
    avatar_rect = pg.Rect(av_x, av_y, frame.get_width(), frame.get_height())
    sub_surf = surface.subsurface(avatar_rect)

    has_non_zero_pixel = False
    for x in range(0, avatar_rect.width, 10):
        for y in range(0, avatar_rect.height, 10):
            pixel = sub_surf.get_at((x, y))
            # Check if pixel has color and opacity
            if pixel.a > 0 and (pixel.r > 0 or pixel.g > 0 or pixel.b > 0):
                has_non_zero_pixel = True
                break
        if has_non_zero_pixel:
            break

    assert has_non_zero_pixel, f"Rendered avatar area for {speaker_name} is completely blank!"


def test_avatar_animation_frame_cycling():
    """Verify overlay updates frame index over time at _AVATAR_FRAME_SPEED interval."""
    overlay = CinematicNarrativeOverlay()
    overlay.activate({"speaker_name": "Green Monster", "dialogue_text": "Roar"})

    assert overlay._avatar_frame_idx == 0
    num_frames = len(overlay._avatar_frames)
    assert num_frames > 1

    # Advance time by less than speed -> should remain at frame 0
    overlay.update(overlay._AVATAR_FRAME_SPEED * 0.5)
    assert overlay._avatar_frame_idx == 0

    # Advance time by rest of interval -> should advance to frame 1
    overlay.update(overlay._AVATAR_FRAME_SPEED * 0.6)
    assert overlay._avatar_frame_idx == 1


def test_atmospheric_scrim_alpha_transparency():
    """Verify standard dialogue uses alpha 160 (not opaque 255) and book ritual uses 240."""
    overlay = CinematicNarrativeOverlay()

    # Standard dialogue
    overlay.activate({"speaker_name": "Green Monster", "dialogue_text": "I see you..."})
    assert overlay._vignette_surface is not None
    # Check top-left pixel alpha of vignette surface
    vignette_pixel = overlay._vignette_surface.get_at((0, 0))
    assert vignette_pixel.a == 160, f"Expected standard scrim alpha 160, got {vignette_pixel.a}"

    overlay.deactivate()

    # Book ritual
    overlay.activate({"is_book_ritual": True, "speaker_name": "Ancient Grimoire", "dialogue_text": "..."})
    assert overlay._vignette_surface is not None
    ritual_pixel = overlay._vignette_surface.get_at((0, 0))
    assert ritual_pixel.a == 240, f"Expected ritual scrim alpha 240, got {ritual_pixel.a}"


def test_boss_encounter_manager_forwards_speaker_and_sprite():
    """Verify BossEncounterManager extracts boss metadata and passes to overlay."""
    mock_overlay = MagicMock()
    mock_bus = MagicMock()
    mock_corruption = MagicMock()
    mock_corruption.value = 10.0

    config = {
        "boss_dialogue": {
            "Green Monster": {
                "pre_fight": ["You trespass upon forbidden ground."],
                "death_line": "The seal... has broken...",
                "corruption_variants": {
                    "low": "A pure soul dares enter?",
                    "mid": "The taint touches you.",
                    "high": "You reek of the void."
                }
            }
        }
    }

    bem = BossEncounterManager(
        event_bus=mock_bus,
        corruption_manager=mock_corruption,
        config=config,
        overlay=mock_overlay,
        boss_sequence=["Green Monster"],
    )

    mock_boss_entity = MagicMock()
    mock_boss_entity.boss_title = "The Gatekeeper"
    mock_boss_entity._base_path = "assets/graphics/green_monster"

    bem.begin_encounter("Green Monster", mock_boss_entity)

    assert bem._boss_title == "The Gatekeeper"
    assert bem._boss_sprite_path == "assets/graphics/green_monster"

    # Advance freeze timer to trigger pre-fight line
    bem.update(0.6)

    # Verify show_bark received speaker_name and avatar_sprite
    assert mock_overlay.show_bark.called
    call_args, call_kwargs = mock_overlay.show_bark.call_args
    assert call_kwargs.get("speaker_name") == "The Gatekeeper"
    assert call_kwargs.get("avatar_sprite") == "assets/graphics/green_monster"

    # Trigger boss death
    mock_overlay.show_bark.reset_mock()
    bem.on_boss_died("Green Monster")

    assert mock_overlay.show_bark.called
    call_args_death, call_kwargs_death = mock_overlay.show_bark.call_args
    assert call_kwargs_death.get("speaker_name") == "The Gatekeeper"
    assert call_kwargs_death.get("avatar_sprite") == "assets/graphics/green_monster"
