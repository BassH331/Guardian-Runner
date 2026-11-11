"""
Verification tests for the "Cycle of Vessels" Storyline Overhaul,
4-Zone Environmental Props & Landmarks (0 to 36,000px), DarkRonin Boss Integration,
RelicRevealState Memory Presentation, and Dynamic Zone/Boss/Corruption Audio.
"""

from __future__ import annotations

import json
import os
import pygame as pg
import pytest

if not pg.get_init():
    pg.init()
if not pg.display.get_surface():
    pg.display.set_mode((1280, 720), pg.NOFRAME)

from src.game.entities.boss_manager import BossManager
from src.game.entities.dark_ronin import DarkRonin
from src.game.states.relic_reveal_state import RelicRevealState
from src.game.states.story_state import StoryState
from src.game.systems.environment_manager import EnvironmentManager
from src.game.systems.whisperer_system import WhispererSystem
from src.game.audio.audio_lock import verify_config_integrity


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(REPO_ROOT)


def test_storyline_and_popups_have_no_placeholders():
    """Verify storyline_config.json and scene_popups_config.json have cohesive Cycle of Vessels lore and zero placeholders."""
    story_path = os.path.join(REPO_ROOT, "game_data", "storyline_config.json")
    popups_path = os.path.join(REPO_ROOT, "game_data", "scene_popups_config.json")

    with open(story_path, "r", encoding="utf-8") as f:
        story = json.load(f)
    with open(popups_path, "r", encoding="utf-8") as f:
        popups = json.load(f)

    raw_story = json.dumps(story)
    raw_popups = json.dumps(popups)

    # Ensure old placeholder or mismatched strings are completely gone
    forbidden = [
        "New custom spoken line",
        "milk-livered bastard",
        "Pure shite",
        "The Fabricator's Enforcer",
        "Clanking gears of malice",
        "mortal demies",
        "DONT LOSE YOURSELF TO THE FOREST WARRIOR",
    ]
    for phrase in forbidden:
        assert phrase not in raw_story, f"Found placeholder/mismatched phrase '{phrase}' in storyline_config.json"
        assert phrase not in raw_popups, f"Found placeholder/mismatched phrase '{phrase}' in scene_popups_config.json"

    # Verify all relics have memory_text, lore, and corruption_variants
    for relic_id, rdata in story["relics"].items():
        assert rdata.get("memory_text"), f"Relic '{relic_id}' missing memory_text"
        assert rdata.get("lore"), f"Relic '{relic_id}' missing lore"
        variants = rdata.get("corruption_variants", {})
        assert variants.get("low") and variants.get("mid") and variants.get("high"), (
            f"Relic '{relic_id}' missing complete corruption_variants"
        )

    # Verify all main bosses have pre_fight, death_line, corruption_variants, and combat_taunts
    for boss_key in ("BloodZombie", "Gatekeeper", "FireWizard", "DarkRonin"):
        bcfg = story["boss_dialogue"][boss_key]
        assert len(bcfg.get("pre_fight", [])) >= 2, f"Boss '{boss_key}' missing pre_fight lines"
        assert bcfg.get("death_line"), f"Boss '{boss_key}' missing death_line"
        assert len(bcfg.get("combat_taunts", [])) >= 2, f"Boss '{boss_key}' missing combat_taunts"


def test_four_story_zones_props_and_events_coverage():
    """Verify all 4 Story Zones (0-9000, 9000-18000, 18000-27000, 27000-36000) have props, lore landmarks, and world events."""
    level_path = os.path.join(REPO_ROOT, "game_data", "level_1.json")
    with open(level_path, "r", encoding="utf-8") as f:
        level = json.load(f)

    props = level["environment"]["props"]
    events = level["world_events"]

    zones = [
        (0, 9000),
        (9000, 18000),
        (18000, 27000),
        (27000, 36000),
    ]

    for idx, (z_min, z_max) in enumerate(zones, start=1):
        zone_props = [p for p in props if z_min <= float(p.get("pos_x", 0)) < z_max]
        zone_lore_props = [p for p in zone_props if p.get("lore_text")]
        zone_events = [e for e in events if z_min <= float(e.get("distance", 0)) < z_max]

        assert len(zone_props) >= 3, f"Zone {idx} ({z_min}-{z_max}) has too few props ({len(zone_props)})"
        assert len(zone_lore_props) >= 2, f"Zone {idx} ({z_min}-{z_max}) needs at least 2 interactive lore props"
        assert len(zone_events) >= 3, f"Zone {idx} ({z_min}-{z_max}) has too few world events ({len(zone_events)})"


def test_environment_prop_story_triggers_and_aura_draw():
    """Verify EnvironmentManager loads level_1.json props, renders glowing lore/fire props, and fires proximity lore."""
    level_path = os.path.join(REPO_ROOT, "game_data", "level_1.json")
    with open(level_path, "r", encoding="utf-8") as f:
        level = json.load(f)

    env_mgr = EnvironmentManager(1280, 720, env_config=level["environment"])
    assert len(env_mgr.props) >= 25

    # Check proximity trigger near Vane's Perimeter Torch (~2389px)
    triggered = env_mgr.check_prop_story_triggers(2400.0, corruption=15.0)
    assert len(triggered) >= 1
    assert any("Vane" in t["title"] for t in triggered)

    # Second check at same coordinate should not re-trigger already triggered prop
    triggered_again = env_mgr.check_prop_story_triggers(2400.0, corruption=15.0)
    assert len(triggered_again) == 0

    # Render pass check
    surf = pg.Surface((1280, 720))
    env_mgr.draw(surf, cam_x=2000.0, cam_y=0.0, foreground_pass=False)
    env_mgr.draw(surf, cam_x=2000.0, cam_y=0.0, clear_bg=False, foreground_pass=True)


def test_dark_ronin_boss_spawning_and_encounter_compatibility():
    """Verify DarkRonin can be spawned via BossManager.spawn_boss as Commander Kaelen with full boss lifecycle."""
    class DummyPlayer:
        def __init__(self):
            self.rect = pg.Rect(200, 500, 48, 64)
            self.facing_left = False

    player = DummyPlayer()
    params = {
        "title": "Commander Kaelen, The Hollowed Mentor",
        "scale": 2.6,
        "health": 260.0,
        "tier": "boss",
        "soul_value": "remaining",
        "sprite_dir": "assets/graphics/Ronin",
        "_event_id": 3,
        "_event_distance": 34500,
    }
    boss = BossManager.spawn_boss(params, player, 1280, 720, audio_manager=None)
    assert isinstance(boss, DarkRonin)
    assert getattr(boss, "is_boss", False) is True
    assert boss.health == 260.0
    assert boss.is_dead is False

    # Verify ai_frozen prevents attack state transitions
    boss.ai_frozen = True
    boss.update(16.67, bg_scroll_speed=0.0)
    assert boss.is_dead is False

    # Verify corruption scaling (>66 increases max_health by 10%)
    boss.apply_corruption_scaling(75.0)
    assert boss.max_health == pytest.approx(286.0)

    # Verify fatal damage sets is_dead = True
    boss.take_damage(500.0)
    assert boss.is_dead is True


def test_story_state_chapters_and_relic_reveal_state():
    """Verify multi-chapter StoryState and upgraded RelicRevealState render cleanly."""
    surf = pg.Surface((1280, 720))
    story_state = StoryState(None)
    story_state.on_enter()
    assert len(story_state._chapters) == 3
    story_state.update(0.1)
    story_state.draw(surf)

    story_path = os.path.join(REPO_ROOT, "game_data", "storyline_config.json")
    with open(story_path, "r", encoding="utf-8") as f:
        story = json.load(f)

    relic_data = dict(story["relics"]["candoras_tear"])
    relic_data["_corruption_value"] = 45.0
    relic_data["_corruption_delta"] = -20.0

    reveal = RelicRevealState(None, "candoras_tear", relic_data)
    reveal.on_enter()
    reveal.update(0.2)
    reveal.draw(surf)
    # Grace lock (0.85s) prevents accidental dismissal from lingering boss-fight keypresses
    reveal.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_SPACE))
    assert reveal.is_active is True
    assert reveal._renderer.is_complete is False

    # Past 0.85s, lingering combat key (Q) is ignored, while SPACE completes then dismisses
    reveal.update(0.8)
    reveal.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_q))
    assert reveal.is_active is True
    reveal.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_SPACE))
    assert reveal.is_active is True
    assert reveal._renderer.is_complete is True
    reveal.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_SPACE))
    assert reveal.is_active is False
    assert WhispererSystem.ENABLED is True


def test_master_audio_config_lock_and_zone_tracks():
    """Verify master_audio_config.json passes lock integrity and defines all 4 zone & boss tracks."""
    cfg_path = os.path.join(REPO_ROOT, "game_data", "master_audio_config.json")
    lock_path = os.path.join(REPO_ROOT, "game_data", "master_audio_config.lock")
    ok, msg = verify_config_integrity(cfg_path, lock_path)
    assert ok is True, f"Audio config integrity check failed: {msg}"

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    sounds = cfg.get("sounds", {})
    for key in (
        "zone_1_music",
        "zone_2_music",
        "zone_3_music",
        "zone_4_music",
        "boss_combat_music",
        "final_boss_music",
        "corruption_drone",
    ):
        assert key in sounds, f"Missing sound key '{key}' in master_audio_config.json"
        asset_path = os.path.join(REPO_ROOT, sounds[key])
        assert os.path.exists(asset_path), f"Audio file missing on disk for '{key}': {asset_path}"
