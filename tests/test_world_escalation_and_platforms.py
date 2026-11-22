"""Integration and regression tests for Guardian-Runner Zone 1-4 world escalation,
jumpable platforms/buildings, Demon Mine chain blasts, chasing exploders, flying eyes,
and the Zone 4 Forest-to-Hell Rift transition.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pygame as pg
import pytest

from v3x_zulfiqar_gideon import AssetManager, UITheme

UITheme.configure_buttons(
    assets={
        "big": ("dummy_big", "dummy_big_p"),
        "medium": ("dummy_med", "dummy_med_p"),
        "cancel": ("dummy_cancel", "dummy_cancel_p"),
        "new_start": ("dummy_new", "dummy_new_p"),
    },
    font_path="dummy_font",
)
UITheme.configure_notifications(
    banner_path="dummy_banner",
    icons={"gray": "dummy_gray", "red": "dummy_red", "yellow": "dummy_yellow"},
    font_path="dummy_font",
)
UITheme.configure_overlays(
    stone_path="dummy_stone",
    parchment_path="dummy_parchment",
    title_font_path="dummy_font",
    body_font_path="dummy_font",
)

from src.game.entities.player import Player, PlayerState
from src.game.entities.skeleton import Skeleton, SkeletonState
from src.game.systems.environment_manager import EnvironmentManager, EnvironmentProp

REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)


@pytest.fixture(scope="module", autouse=True)
def setup_pygame():
    if not pg.get_init():
        pg.init()
    if not pg.font.get_init():
        pg.font.init()
    if not pg.display.get_init() or pg.display.get_surface() is None:
        pg.display.set_mode((1280, 720), pg.NOFRAME)
    yield


def test_known_spritesheet_grids_registered():
    """Verify AssetManager knows exact grid slicing for all Hell & Dungeon sheets."""
    assert AssetManager.KNOWN_SPRITESHEET_GRIDS["imp.png"] == (10, 5)
    assert AssetManager.KNOWN_SPRITESHEET_GRIDS["old demon covered.png"] == (7, 1)
    assert AssetManager.KNOWN_SPRITESHEET_GRIDS["demon mine.png"] == (7, 2)
    assert AssetManager.KNOWN_SPRITESHEET_GRIDS["pot_frames.png"] == (2, 2)
    assert AssetManager.KNOWN_SPRITESHEET_GRIDS["statue_frames.png"] == (6, 1)
    assert AssetManager.KNOWN_SPRITESHEET_GRIDS["totem.png"] == (6, 1)
    assert AssetManager.KNOWN_SPRITESHEET_GRIDS["plague flies.png"] == (4, 1)


def test_level1_all_props_exist_and_platforms_are_jumpable():
    """Verify every prop texture in level_1.json exists and every building/bridge platform aligns above road."""
    level_path = REPO_ROOT / "game_data" / "level_1.json"
    level = json.loads(level_path.read_text(encoding="utf-8"))
    props = level["environment"]["props"]

    for idx, p in enumerate(props):
        tex = REPO_ROOT / p["texture_path"]
        assert tex.exists(), f"Prop #{idx} missing texture: {p['texture_path']}"

    em = EnvironmentManager(1280, 720)
    em.load_config(level["environment"])
    road_y = float(em.ground_y)

    # Check key platforms across Zones 1-4 via real get_ground_y_at()
    expected_platforms = [
        ("z1_abandoned_cabin", 3470.0, 290.0, 380.0),
        ("Wooden Shed Z1", 6150.0, 330.0, 400.0),
        ("supply_wagon", 6940.0, 440.0, 500.0),
        ("z2_cursed_wagon", 11070.0, 360.0, 430.0),
        ("scaffold_bridge Z2", 14330.0, 380.0, 440.0),
        ("z3_collapsed_outpost", 18540.0, 270.0, 340.0),
        ("Wooden Shed Z3", 22200.0, 330.0, 400.0),
        ("blacksmith_forge", 22960.0, 360.0, 420.0),
        ("scaffold_bridge Z3", 23400.0, 380.0, 440.0),
        ("z4_obsidian_stronghold", 27480.0, 230.0, 300.0),
        ("scaffold_bridge Z4", 31700.0, 370.0, 435.0),
    ]
    for label, wx, y_min, y_max in expected_platforms:
        surf_y = em.get_ground_y_at(wx, current_y=0.0)
        assert surf_y < road_y, f"{label} at x={wx} did not register above road_y={road_y} (got {surf_y})"
        assert y_min <= surf_y <= y_max, f"{label} at x={wx} had unexpected surf_y={surf_y} (expected {y_min}..{y_max})"


def test_rift_zone_and_zone_tints_progression():
    """Verify Zone 4 Rift crossfade and zone_tints render cleanly across Zones 1-4."""
    level_path = REPO_ROOT / "game_data" / "level_1.json"
    level = json.loads(level_path.read_text(encoding="utf-8"))

    em = EnvironmentManager(1280, 720)
    em.load_config(level["environment"])

    assert em._compute_rift_alpha(24000.0) == 0.0
    mid_alpha = em._compute_rift_alpha(26050.0)
    assert 0.25 <= mid_alpha <= 0.75
    assert em._compute_rift_alpha(27200.0) == 1.0

    surf = pg.Surface((1280, 720))
    for cam_x in (3000.0, 10800.0, 18100.0, 26050.0, 27400.0):
        em.draw(surf, cam_x=cam_x, max_layer=6, clear_bg=True, foreground_pass=False)
        em.draw(surf, cam_x=cam_x, min_layer=7, clear_bg=False, foreground_pass=True)


def test_spawn_zone_enemy_variants_and_ai_modes():
    """Verify all Zone 1-4 spawn variants load animations, hover-fly, and execute chase suicide-explosion."""
    level_path = REPO_ROOT / "game_data" / "level_1.json"
    level = json.loads(level_path.read_text(encoding="utf-8"))
    mock_audio = MagicMock()
    player = Player(400, 568, mock_audio)
    player.rect = pg.Rect(400, 504, 48, 64)

    loaded = {}
    for z_idx, zone in enumerate(level["spawn_zones"], start=1):
        for v in zone.get("variants", []):
            is_flying = bool(v.get("is_flying", False))
            hover_y = v.get("hover_y")
            sk = Skeleton(
                x=600,
                y=int(hover_y) if is_flying and hover_y else 568,
                player=player,
                sprite_root=v.get("sprite_root"),
                behaviour_map=v.get("behaviour_map"),
                tier=v.get("tier", "minion"),
                custom_scale=v.get("scale"),
                custom_health=v.get("health"),
                audio_manager=mock_audio,
                spritesheet_path=v.get("spritesheet_path"),
                sheet_grid=v.get("sheet_grid"),
                row_map=v.get("row_map"),
                tint_color=v.get("tint_color"),
                shadow_outline_color=v.get("shadow_outline_color"),
                custom_speed=v.get("speed"),
                explode_on_proximity=bool(v.get("explode_on_proximity", False)),
                explode_trigger_range=int(v.get("explode_trigger_range", 85)),
                explode_radius=int(v.get("explode_radius", 110)),
                explode_damage=float(v.get("explode_damage", 20.0)),
                is_flying=is_flying,
                hover_y=hover_y,
                enemy_name=v.get("enemy_name"),
            )
            for req in (SkeletonState.IDLE, SkeletonState.CHASE, SkeletonState.ATTACK, SkeletonState.DEATH):
                assert len(sk.animations.get(req, [])) > 0, f"Zone {z_idx} {v.get('enemy_name')} missing {req}"
            loaded[v["enemy_name"]] = sk

    # Imp uses 10x5 sheet grid with exact expected frame counts
    imp = loaded["Ashen Imp"]
    assert len(imp.animations[SkeletonState.IDLE]) == 10
    assert len(imp.animations[SkeletonState.CHASE]) == 8
    assert len(imp.animations[SkeletonState.ATTACK]) == 5
    assert len(imp.animations[SkeletonState.DEATH]) == 6

    # Demon Eye stays airborne and enters fuse windup on proximity
    eye = loaded["Flying Demon Eye"]
    assert eye.is_flying is True
    assert eye.explode_on_proximity is True
    assert eye.rect.bottom <= 520

    # Bloated Damned chases, triggers swell-windup within trigger range, emits centered AoE blast, then dies
    bloated = loaded["Bloated Blight-Bomber"]
    grp = pg.sprite.Group(bloated)
    bloated.rect.midbottom = (player.rect.right + 40, 568)
    bloated._update_ai(0.016)
    assert bloated.state == SkeletonState.ATTACK
    assert bloated._explode_fuse_started is True

    saw_blast_hitbox = False
    for _ in range(40):
        bloated.update(0.016, 0)
        hb = bloated.get_attack_hitbox()
        if hb is not None:
            saw_blast_hitbox = True
            assert hb.width == int(bloated.explode_radius) * 2
            break
    assert saw_blast_hitbox is True

    # Finish attack animation frames -> self.kill() removes suicide exploder
    for _ in range(60):
        if not bloated.alive():
            break
        bloated.update(0.016, 0)
    assert not bloated.alive()


def test_demon_mine_proximity_and_slash_chain_blast():
    """Verify Demon Mine detonates on player proximity and chains blast damage onto nearby enemies."""
    mine = EnvironmentProp(
        texture_path="assets/graphics/GandalfHardcore Hell Asset Pack 32x32/GandalfHardcore The Damned Enemies and NPCs/Demon Mine.png",
        pos_x=500.0,
        pos_y=500.0,
        scale=1.0,
        collision_type="hazard",
        anim_grid=(7, 2),
        trap_hp=15.0,
        trap_loop_frames=6,
        trap_hazard_range=(99, 99),
        proximity_explode=True,
        explode_radius=120.0,
        explode_damage=20.0,
    )
    assert len(mine.frames) > 6

    with patch("v3x_zulfiqar_gideon.asset_manager.AssetManager.get_texture") as mock_tex, \
         patch("v3x_zulfiqar_gideon.asset_manager.AssetManager.get_font") as mock_font:
        mock_tex.return_value = pg.Surface((448, 128), pg.SRCALPHA)
        mock_font.return_value = pg.font.Font(None, 20)

        from src.game.states.game_state import GameState

        state = GameState(MagicMock())
        player = state.player.sprite
        assert player is not None

        state.environment_manager.props = [mine]
        state.world_distance = 0.0

        # Place enemy within blast radius of the mine
        nearby_enemy = pg.sprite.Sprite()
        nearby_enemy.rect = pg.Rect(560, 500, 48, 64)
        nearby_enemy.take_damage = MagicMock()
        state.obstacle_group = pg.sprite.Group()
        state.obstacle_group.add(nearby_enemy)

        # Position player right next to Demon Mine
        player.rect = pg.Rect(468, 500, 48, 64)
        player.set_state(PlayerState.RUN, force=True)
        player._invincibility_timer = 0.0
        player._invincibility_duration = 0.0
        hp_before = player.health

        state.combat_system.check_environmental_hazards()

        assert player.health < hp_before
        assert mine.trap_state == "dissolving"
        nearby_enemy.take_damage.assert_called_once()

        for _ in range(30):
            mine.update(0.15)
        assert mine.trap_state == "destroyed"
