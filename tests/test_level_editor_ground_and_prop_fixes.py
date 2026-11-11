import os
import sys
import json
import pytest
import pygame as pg

if not pg.get_init():
    pg.init()
if not pg.display.get_surface():
    pg.display.set_mode((1280, 720), pg.NOFRAME)

from v3x_zulfiqar_gideon import UITheme, AssetManager
from src.game.systems.environment_manager import EnvironmentManager, EnvironmentProp
from level_editor import App


def test_prop_default_collision_deco():
    """Verify that newly created props default to deco and is_ground=False."""
    prop = EnvironmentProp(
        texture_path="assets/graphics/background images/new_bg_images/bg_image.png",
        slice_rect=[0, 0, 32, 32],
        pos_x=100.0,
        pos_y=200.0,
    )
    assert prop.collision_type == "deco"
    assert prop.is_ground is False


def test_prop_explicit_solid_is_ground():
    """Verify that props explicitly set to solid or platform default is_ground to True."""
    p_solid = EnvironmentProp(
        texture_path="assets/graphics/background images/new_bg_images/bg_image.png",
        slice_rect=[0, 0, 32, 32],
        pos_x=100.0,
        pos_y=200.0,
        collision_type="solid",
    )
    assert p_solid.collision_type == "solid"
    assert p_solid.is_ground is True

    p_plat = EnvironmentProp(
        texture_path="assets/graphics/background images/new_bg_images/bg_image.png",
        slice_rect=[0, 0, 32, 32],
        pos_x=100.0,
        pos_y=200.0,
        collision_type="platform",
    )
    assert p_plat.collision_type == "platform"
    assert p_plat.is_ground is True


def test_get_ground_y_at_layer_isolation():
    """Verify that props on non-gameplay layers (e.g. layer 9, or parallax != 1.0) do NOT pollute ground height."""
    env = EnvironmentManager(1280, 720, env_config={"ground_y": 568})
    # Add a prop on layer 9 with parallax 1.0 that was accidentally solid
    p_airborne_l9 = EnvironmentProp(
        texture_path="assets/graphics/background images/new_bg_images/bg_image.png",
        slice_rect=[0, 0, 32, 32],
        pos_x=100.0,
        pos_y=200.0,
        layer_index=9,
        parallax_ratio=1.0,
        collision_type="solid",
        is_ground=True,
    )
    env.props.append(p_airborne_l9)

    # get_ground_y_at should ignore layer 9 and return ground_y (568.0)
    assert env.get_ground_y_at(105.0) == 568.0


def test_get_ground_y_at_current_y_ceiling_isolation():
    """Verify that a high platform above entity's head is not treated as ground when entity is on the road."""
    env = EnvironmentManager(1280, 720, env_config={"ground_y": 568})
    p_bridge = EnvironmentProp(
        texture_path="assets/graphics/background images/new_bg_images/bg_image.png",
        slice_rect=[0, 0, 100, 32],
        pos_x=50.0,
        pos_y=200.0,
        layer_index=6,
        parallax_ratio=1.0,
        collision_type="solid",
        is_ground=True,
    )
    env.props.append(p_bridge)

    # When entity is standing on the road (current_y = 568.0), ground should be 568.0
    gy_on_road = env.get_ground_y_at(75.0, current_y=568.0)
    assert gy_on_road == 568.0

    # When entity jumps onto the bridge (current_y = 200.0), ground should be 200.0
    gy_on_bridge = env.get_ground_y_at(75.0, current_y=200.0)
    assert gy_on_bridge == 200.0


def test_level_editor_slicer_creates_deco_prop():
    """Verify that slicing a prop on L4 (props) defaults to deco collision and L3 defaults to solid."""
    app = App()
    app.active_idx = 0
    app.level_files = ["game_data/level_1.json"]
    app.load(0)
    app.go5()

    # On L4 (Props & Objects), newly added props are decorative
    app.active_layer_filter = 4
    initial_count = len(app.env_mgr.props)
    app._on_select_prop_from_slicer("assets/graphics/background images/new_bg_images/bg_image.png", [0, 0, 32, 32])
    assert len(app.env_mgr.props) == initial_count + 1

    newly_added = app.env_mgr.props[-1]
    assert newly_added.collision_type == "deco"
    assert newly_added.is_ground is False

    # On L3 (Ground & Terrain), newly added props are solid
    app.active_layer_filter = 3
    app._on_select_prop_from_slicer("assets/graphics/background images/new_bg_images/bg_image.png", [0, 0, 32, 32])
    terrain_prop = app.env_mgr.props[-1]
    assert terrain_prop.collision_type == "solid"
    assert terrain_prop.is_ground is True


def test_level_editor_level_manager_modal_event_delegation():
    """Verify that _h5 delegates events to level_mgr_modal when open."""
    app = App()
    app.active_idx = 0
    app.level_files = ["game_data/level_1.json"]
    app.load(0)
    app.go5()

    modal_handled = []
    class DummyModal:
        def on(self, ev):
            modal_handled.append(ev)

    app.level_mgr_modal = DummyModal()
    dummy_ev = pg.event.Event(pg.MOUSEBUTTONDOWN, button=1, pos=(100, 100))
    app._h5(dummy_ev)

    assert len(modal_handled) == 1
    assert modal_handled[0] == dummy_ev


def test_environment_prop_animated_frame_discovery_and_loop():
    """Verify that EnvironmentProp discovers multi-frame sequences and loops them."""
    prop = EnvironmentProp(
        texture_path="assets/graphics/Props/spr_FirePlace_strip_frames/frame_005.png",
        slice_rect=[13, 27, 41, 37],
        pos_x=5801.0,
        pos_y=284.0,
        scale=1.0,
        anim_speed=0.1,
    )
    assert len(prop.frames) == 6
    assert prop.frame_idx == 0

    # Test update advances frames
    prop.update(0.1)
    assert prop.frame_idx == 1

    prop.update(0.5)
    # 1 + 5 = 6 -> loops back to 0
    assert prop.frame_idx == 0


def test_environment_manager_updates_animated_props():
    """Verify that EnvironmentManager.update advances all animated props."""
    env = EnvironmentManager(1280, 720)
    prop = EnvironmentProp(
        texture_path="assets/graphics/Props/spr_FirePlace_strip_frames/frame_000.png",
        slice_rect=[13, 27, 41, 37],
        pos_x=5801.0,
        pos_y=284.0,
        anim_speed=0.1,
    )
    env.props.append(prop)
    assert prop.frame_idx == 0

    env.update(0.1, player_speed=0.0)
    assert prop.frame_idx == 1


def test_spritesheet_grid_prop_animates_all_40_frames_and_scales():
    """Verify Large Skull.png slices all 10x4 frames, animates through all 40 frames, and preserves frames on rescale."""
    skull_path = (
        "assets/graphics/GandalfHardcore Hell Asset Pack 32x32/"
        "GandalfHardcore The Damned Enemies and NPCs/Large Skull.png"
    )
    prop = EnvironmentProp(
        texture_path=skull_path,
        slice_rect=[0, 0, 128, 128],
        pos_x=12201.0,
        pos_y=151.0,
        scale=3.0,
        anim_grid=[10, 4],
        anim_speed=0.1,
    )
    assert len(prop.frames) == 40
    assert prop.width == 384 and prop.height == 384

    # Advance through all 40 frames and wrap back to 0
    seen = {prop.frame_idx}
    for _ in range(40):
        prop.update(0.1)
        seen.add(prop.frame_idx)
    assert seen == set(range(40))
    assert prop.frame_idx == 0

    # Rescaling preserves all 40 frames at the new dimensions
    prop.set_scale(2.0)
    assert len(prop.frames) == 40
    assert prop.width == 256 and prop.height == 256

    # Serialization round-trip keeps anim_grid & anim_speed
    d = prop.to_dict()
    assert d["anim_grid"] == [10, 4]
    assert d["anim_speed"] == 0.1
    mgr = EnvironmentManager(1280, 720, env_config={"props": [d]})
    assert len(mgr.props[0].frames) == 40


def test_level_1_large_skull_prop_is_animated():
    """Verify the Large Skull prop in game_data/level_1.json loads with all 40 animation frames and trap loop."""
    with open("game_data/level_1.json", "r", encoding="utf-8") as f:
        lvl = json.load(f)
    mgr = EnvironmentManager(1280, 720, env_config=lvl.get("environment", {}))
    skulls = [p for p in mgr.props if "Large Skull.png" in p.texture_path]
    assert len(skulls) >= 1
    for skull in skulls:
        assert len(skull.frames) == 40
        assert skull.pos_y + skull.height == lvl["environment"]["ground_y"]
        assert skull.collision_type == "hazard"
        assert skull.trap_max_hp == 45.0
        assert skull.trap_loop_frames == 30
        assert skull.trap_reward_souls == 75


def test_hell_skull_trap_window_and_banish_dissolve():
    """Verify timed hazard window (14..23), telegraph (11..13), 0..29 loop, and Row 3 dissolve upon banish."""
    skull_path = (
        "assets/graphics/GandalfHardcore Hell Asset Pack 32x32/"
        "GandalfHardcore The Damned Enemies and NPCs/Large Skull.png"
    )
    trap = EnvironmentProp(
        texture_path=skull_path,
        slice_rect=[0, 0, 128, 128],
        pos_x=12201.0,
        pos_y=151.0,
        scale=3.0,
        collision_type="hazard",
        anim_grid=[10, 4],
        anim_speed=0.1,
        trap_hp=45.0,
        trap_loop_frames=30,
        trap_telegraph_range=[11, 13],
        trap_hazard_range=[14, 23],
        trap_reward_souls=75,
    )

    # Active trap loops strictly within 0..29 (never dissolves automatically)
    seen = set()
    for i in range(35):
        seen.add(trap.frame_idx)
        assert trap.frame_idx < 30
        assert trap.is_telegraph_active() == (11 <= trap.frame_idx <= 13)
        assert trap.is_hazard_active() == (14 <= trap.frame_idx <= 23)
        trap.update(0.1)
    assert seen == set(range(30))

    # Partial hit does not banish; lethal hit enters Row 3 dissolve (frames 30..39) -> destroyed
    assert trap.take_trap_damage(20.0) is False
    assert trap.trap_state == "active"
    assert trap.take_trap_damage(25.0) is True
    assert trap.trap_state == "dissolving"
    assert trap.frame_idx == 30
    assert trap.is_hazard_active() is False

    for _ in range(10):
        trap.update(0.1)
    assert trap.trap_state == "destroyed"


