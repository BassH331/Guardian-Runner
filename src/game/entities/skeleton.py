"""
Skeleton enemy module with precision frame-based combat system.

This module implements a skeletal enemy with state-machine AI and
frame-accurate hit detection for responsive, fair combat gameplay.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Final, Optional, Sequence

import pygame as pg

from v3x_zulfiqar_gideon import AssetManager, Actor, AttackConfig
from src.game.audio.entity_audio_mixin import EntityAudioMixin
from .hitbox_registry import HitboxRegistry
from .base_enemy import BaseEnemy
from ..services import ConfigClient
from src.game.ai import PerceptionSystem, AlertLevel, SquadTokenManager, SquadCoordinator, SquadRole, UtilityCombatEngine, TacticalAction

if TYPE_CHECKING:
    from src.game.entities.player import Player


class SkeletonState(Enum):
    """Enumeration of all possible skeleton behavioral states."""
    
    DEATH = 0
    HURT = 10
    ATTACK = 20
    CHASE = 30
    IDLE = 40


@dataclass(slots=True)
class StateConfig:
    animation_speed: float = 0.15
    loops: bool = True
    next_state: Optional[SkeletonState] = None
    interruptible: bool = True


class BoneShardParticle:
    """Procedural bone fragment / dust particle for punchy visual feedback."""
    __slots__ = ("x", "y", "vx", "vy", "size", "color", "life", "max_life")

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        size: int,
        color: tuple[int, int, int],
        life: float = 0.35,
    ):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.size = size
        self.color = color
        self.life = life
        self.max_life = life

    def update(self, dt_sec: float, scroll_speed: int = 0) -> bool:
        self.x -= scroll_speed
        self.x += self.vx * dt_sec * 60.0
        self.y += self.vy * dt_sec * 60.0
        self.vy += 0.25 * dt_sec * 60.0
        self.vx *= 0.95
        self.life -= dt_sec
        return self.life <= 0.0

    def draw(self, surface: pg.Surface) -> None:
        if self.life > 0:
            alpha_ratio = max(0.0, min(1.0, self.life / self.max_life))
            current_size = max(1, int(self.size * alpha_ratio))
            pg.draw.rect(surface, self.color, (int(self.x), int(self.y), current_size, current_size))


class BoneDustEffect:
    """Transient bone dust shatter/re-assembly visual effect with bone shard particles."""

    def __init__(
        self,
        x: int,
        y: int,
        frames: list[pg.Surface],
        fps: float = 24.0,
        offset_y: int = 0,
        num_particles: int = 14,
    ):
        self.frames = frames
        self.fps = fps
        self.frame_duration = 1.0 / fps
        self.timer = 0.0
        self.current_frame = 0
        self.is_finished = False
        self.image = frames[0] if frames else None
        self.rect = self.image.get_rect(midbottom=(x, y + offset_y)) if self.image else pg.Rect(x, y, 0, 0)
        self.particles: list[BoneShardParticle] = []

        # Spawn outward bursting bone shards and bone dust specks
        if num_particles > 0:
            colors = [
                (245, 245, 235),
                (225, 220, 210),
                (195, 195, 185),
                (165, 165, 160),
                (255, 255, 250),
            ]
            for _ in range(num_particles):
                ang = random.uniform(0.0, 6.28)
                spd = random.uniform(2.5, 6.0)
                vx = math.cos(ang) * spd
                vy = math.sin(ang) * spd - 1.8
                p_size = random.randint(2, 5)
                p_color = random.choice(colors)
                p_y = float(y - random.randint(15, 65))
                self.particles.append(
                    BoneShardParticle(
                        float(x + random.randint(-16, 16)),
                        p_y,
                        vx,
                        vy,
                        p_size,
                        p_color,
                        random.uniform(0.25, 0.45),
                    )
                )

    def update(self, dt_sec: float, scroll_speed: int = 0) -> None:
        self.rect.x -= scroll_speed
        self.particles = [p for p in self.particles if not p.update(dt_sec, scroll_speed)]
        if self.is_finished or not self.frames:
            if not self.particles:
                self.is_finished = True
            return
        self.timer += dt_sec
        while self.timer >= self.frame_duration:
            self.timer -= self.frame_duration
            self.current_frame += 1
            if self.current_frame >= len(self.frames):
                self.is_finished = True
                break
            else:
                self.image = self.frames[self.current_frame]

    def draw(self, surface: pg.Surface) -> None:
        if self.current_frame < len(self.frames) and self.image:
            surface.blit(self.image, self.rect)
        for p in self.particles:
            p.draw(surface)


class Skeleton(BaseEnemy):

    """
    A skeletal enemy with state-machine AI and frame-precise combat.
    """
    
    # Class-level attack configurations (immutable)
    ATTACK_1_CONFIG: Final[AttackConfig] = AttackConfig(
        hit_frames=frozenset({6}),
        base_damage=1.0,
        knockback_force=8.0,
    )
    
    ATTACK_2_CONFIG: Final[AttackConfig] = AttackConfig(
        hit_frames=frozenset({5, 6}),
        base_damage=0.75,
        knockback_force=5.0,
    )
    
    STATE_CONFIGS: Final[dict[Enum, StateConfig]] = {
        SkeletonState.IDLE: StateConfig(0.1),
        SkeletonState.CHASE: StateConfig(0.15),
        SkeletonState.ATTACK: StateConfig(0.15, loops=False, next_state=SkeletonState.IDLE, interruptible=False),
        SkeletonState.HURT: StateConfig(0.30, loops=False, next_state=SkeletonState.IDLE, interruptible=False),
        SkeletonState.DEATH: StateConfig(0.15, loops=False, interruptible=False),
    }

    hit_vfx_type: str = "bone_sparks"
    _SHEET_ANIM_CACHE: dict[tuple, dict] = {}

    def __init__(
        self,
        x: int,
        y: int,
        player: Player,
        sprite_root: Optional[str] = None,
        behaviour_map: Optional[dict[str, str]] = None,
        tier: str = "minion",
        custom_scale: Optional[float] = None,
        custom_health: Optional[float] = None,
        audio_manager=None,
        spritesheet_path: Optional[str] = None,
        sheet_grid: Optional[Sequence[int]] = None,
        row_map: Optional[dict[str, Sequence[int]]] = None,
        tint_color: Optional[Sequence[int]] = None,
        shadow_outline_color: Optional[Sequence[int]] = None,
        custom_speed: Optional[float] = None,
        explode_on_proximity: bool = False,
        explode_trigger_range: int = 85,
        explode_radius: int = 110,
        explode_damage: float = 20.0,
        is_flying: bool = False,
        hover_y: Optional[int] = None,
        enemy_name: Optional[str] = None,
    ) -> None:
        super().__init__(x, y)

        self._player: Player = player
        self.state_configs = dict(self.STATE_CONFIGS)
        self.tier = tier
        self.enemy_name: Optional[str] = enemy_name
        self.explode_on_proximity: bool = bool(explode_on_proximity)
        self.explode_trigger_range: int = int(explode_trigger_range)
        self.explode_radius: int = int(explode_radius)
        self.explode_damage: float = float(explode_damage)
        self._explode_fuse_started: bool = False
        self.is_flying: bool = bool(is_flying)
        self._hover_y: Optional[int] = int(hover_y) if hover_y is not None else None
        self._flight_clock: float = random.uniform(0.0, 6.28)
        self._custom_hit_frames: Optional[frozenset[int]] = None

        # Load margins and scale first
        if self.tier == "boss":
            margins_key = "boss"
            if sprite_root:
                import os
                folder_name = os.path.basename(sprite_root.rstrip("/"))
                margins_key = f"boss:{folder_name.lower()}"
        else:
            margins_key = "skeleton"
            if sprite_root:
                import os
                folder_name = os.path.basename(sprite_root.rstrip("/"))
                margins_key = f"skeleton_{folder_name.lower()}"

        margins = HitboxRegistry.get_margins(margins_key)
        # If margins for custom skeleton/boss are missing, fall back to default
        if margins.scale == 1.0 and margins.ground_offset == 0:
            if self.tier == "boss":
                margins = HitboxRegistry.get_margins("boss")
            else:
                margins = HitboxRegistry.get_margins("skeleton")

        # Determine scale: custom_scale priority when spritesheet_path is given, else registry priority -> margins scale
        registry_scale = None
        if not spritesheet_path:
            try:
                if HitboxRegistry.has_custom_margins(margins_key):
                    registry_scale = margins.scale
            except Exception:
                pass

        self.scale = registry_scale if registry_scale is not None else (custom_scale if custom_scale is not None else margins.scale)
        self._scale_is_explicit = (registry_scale is not None or custom_scale is not None)

        # 1. Load animations (spritesheet path takes priority if configured)
        self._sheet_body_margins: Optional[tuple[int, int, int, int]] = None
        if spritesheet_path and sheet_grid and row_map:
            self._load_spritesheet_animations(
                spritesheet_path=spritesheet_path,
                sheet_grid=sheet_grid,
                row_map=row_map,
                tint_color=tint_color,
                shadow_outline_color=shadow_outline_color,
            )
            sp_low = spritesheet_path.lower()
            self.natively_facing_left = any(
                tok in sp_low
                for tok in ("damned", "imp", "demon eye", "plague flies", "old demon", "devil")
            )
        else:
            self.animations[SkeletonState.IDLE] = self._load_frames(
                "assets/skeleton/Skeleton_01_White_Idle/skeleton-idle_{}.png", 8
            )
            self.animations[SkeletonState.CHASE] = self._load_frames(
                "assets/skeleton/Skeleton_01_White_Walk/skeleton-walk_{:02d}.png", 10
            )
            self._attack1_frames = self._load_frames(
                "assets/skeleton/Skeleton_01_White_Attack1/skeleton-atk2_{:02d}.png", 10
            )
            self.animations[SkeletonState.ATTACK] = self._attack1_frames
            self._attack2_frames = self._load_frames(
                "assets/skeleton/Skeleton_01_White_Attack2/skeleton-atk1_{}.png", 9
            )
            self.animations[SkeletonState.HURT] = self._load_frames(
                "assets/skeleton/Skeleton_01_White_Hurt/skeleton-hurt_{}.png", 5
            )
            self.animations[SkeletonState.DEATH] = self._load_frames(
                "assets/skeleton/Skeleton_01_White_Die/skeleton-death_{:02d}.png", 13
            )

            # 2. Overwrite with dynamic folder sprites if provided
            if sprite_root and behaviour_map:
                import os
                tag_to_folders = {}
                for sub, tag in behaviour_map.items():
                    if tag == "skip":
                        continue
                    tag_to_folders.setdefault(tag, []).append(os.path.join(sprite_root, sub))

                def load_from_folders(folders: list[str]) -> list[pg.Surface]:
                    frames = []
                    for f in folders:
                        raw = AssetManager.get_animation_frames(f)
                        for frame in raw:
                            w = int(frame.get_width() * self.scale)
                            h = int(frame.get_height() * self.scale)
                            frames.append(pg.transform.scale(frame, (w, h)))
                    return frames

                self.natively_facing_left: bool = bool(sprite_root and "skeletonzombie" in sprite_root.lower())

                if "idle" in tag_to_folders:
                    self.animations[SkeletonState.IDLE] = load_from_folders(tag_to_folders["idle"])
                if "walk" in tag_to_folders or "chase" in tag_to_folders:
                    walk_folders = tag_to_folders.get("walk", []) + tag_to_folders.get("chase", [])
                    self.animations[SkeletonState.CHASE] = load_from_folders(walk_folders)
                if "attack" in tag_to_folders:
                    attack_folders = tag_to_folders["attack"]
                    if len(attack_folders) >= 2:
                        self._attack1_frames = load_from_folders([attack_folders[0]])
                        self._attack2_frames = load_from_folders([attack_folders[1]])
                        self.animations[SkeletonState.ATTACK] = self._attack1_frames
                    else:
                        self._attack1_frames = load_from_folders(attack_folders)
                        self._attack2_frames = self._attack1_frames
                        self.animations[SkeletonState.ATTACK] = self._attack1_frames
                if "hurt" in tag_to_folders:
                    self.animations[SkeletonState.HURT] = load_from_folders(tag_to_folders["hurt"])
                if "death" in tag_to_folders:
                    self.animations[SkeletonState.DEATH] = load_from_folders(tag_to_folders["death"])
                elif "die" in tag_to_folders:
                    self.animations[SkeletonState.DEATH] = load_from_folders(tag_to_folders["die"])
                elif "hurt" in tag_to_folders:
                    self.animations[SkeletonState.DEATH] = load_from_folders(tag_to_folders["hurt"])

                # Align variable-width folder sprites (e.g. SkeletonZombie 64x64 Idle vs 146x64 Attack)
                # onto a uniform feet-grounded canvas centered around the IDLE visual body.
                if sprite_root and "skeletonzombie" in sprite_root.lower() and self.animations.get(SkeletonState.IDLE):
                    self._normalize_folder_body_alignment()
                
        # 3. Apply Tier Scaling (Health, Speed, Size)
        damage_scale = 1.0
        knockback_scale = 1.0
        
        if self.tier == "boss":
            if not sprite_root and not self._scale_is_explicit:
                self.scale *= 1.8
                # Scale all pre-loaded animation frames to boss scale
                for state in list(self.animations.keys()):
                    self.animations[state] = [
                        pg.transform.scale(img, (int(img.get_width() * 1.8), int(img.get_height() * 1.8)))
                        for img in self.animations[state]
                    ]
                self._attack1_frames = [
                    pg.transform.scale(img, (int(img.get_width() * 1.8), int(img.get_height() * 1.8)))
                    for img in self._attack1_frames
                ]
                self._attack2_frames = [
                    pg.transform.scale(img, (int(img.get_width() * 1.8), int(img.get_height() * 1.8)))
                    for img in self._attack2_frames
                ]
            self._max_health = custom_health if custom_health is not None else 150.0
            self._speed = 3.2
            damage_scale = 3.0
            knockback_scale = 1.8
            
            # Additional boss AI fields
            self._detection_range = 3000
            self._attack_range = 75
            self._vertical_tolerance = 500
        elif self.tier == "elite":
            if not sprite_root and not self._scale_is_explicit:
                self.scale *= 1.3
                # Scale all pre-loaded animation frames to elite scale
                for state in list(self.animations.keys()):
                    self.animations[state] = [
                        pg.transform.scale(img, (int(img.get_width() * 1.3), int(img.get_height() * 1.3)))
                        for img in self.animations[state]
                    ]
                self._attack1_frames = [
                    pg.transform.scale(img, (int(img.get_width() * 1.3), int(img.get_height() * 1.3)))
                    for img in self._attack1_frames
                ]
                self._attack2_frames = [
                    pg.transform.scale(img, (int(img.get_width() * 1.3), int(img.get_height() * 1.3)))
                    for img in self._attack2_frames
                ]
            self._max_health = custom_health if custom_health is not None else 60.0
            self._speed = 3.2
            damage_scale = 1.6
            knockback_scale = 1.3
            self._detection_range = 2000
            self._attack_range = 70
            self._vertical_tolerance = 300
        else:  # minion
            self._max_health = custom_health if custom_health is not None else 30.0
            self._speed = 2.5
            damage_scale = 1.0
            knockback_scale = 1.0
            self._detection_range = 1000
            self._attack_range = 60
            self._vertical_tolerance = 100
            
        self._attack_hitbox_width = 60
        self._attack_hitbox_height = 80

        # Determine config type based on sprite root or tier
        config_type = None
        if sprite_root:
            sprite_lower = sprite_root.lower()
            if "goblin" in sprite_lower:
                config_type = "enemy_goblin"
            elif "green_monster" in sprite_lower:
                config_type = "enemy_green_monster"
            elif "bloodzombie" in sprite_lower:
                config_type = "enemy_blood_zombie"
            elif "skeletonzombie" in sprite_lower or "zombie" in sprite_lower:
                config_type = "enemy_skeleton_zombie"
        
        if config_type is None:
            if self.tier == "boss":
                config_type = "boss_skeleton"
            else:
                config_type = "enemy_skeleton_minion"

        try:
            config = ConfigClient.fetch_config(config_type)
            if config:
                self._max_health = float(config.get("max_health", self._max_health))
                self._speed = float(config.get("speed", self._speed))
                damage_scale = float(config.get("damage_scale", damage_scale))
                knockback_scale = float(config.get("knockback_scale", knockback_scale))
                self._detection_range = int(config.get("detection_range", self._detection_range))
                self._attack_range = int(config.get("attack_range", self._attack_range))
                self._vertical_tolerance = int(config.get("vertical_tolerance", self._vertical_tolerance))
                self._attack_hitbox_width = int(config.get("attack_hitbox_width", 60))
                self._attack_hitbox_height = int(config.get("attack_hitbox_height", 80))
                self.spidey_sense = float(config.get("spidey_sense", 0.65 if self.tier == "boss" else (0.45 if self.tier == "elite" else 0.25)))
                self.teleport_dist_min = int(config.get("teleport_dist_min", 180))
                self.teleport_dist_max = int(config.get("teleport_dist_max", 280 if self.tier == "boss" else 240))
                self.teleport_cooldown = float(config.get("teleport_cooldown", 3.0 if self.tier == "boss" else (3.5 if self.tier == "elite" else 4.5)))
                self.teleport_reaction_delay = float(config.get("teleport_reaction_delay", 0.06 if self.tier == "boss" else 0.10))
        except Exception as e:
            print(f"[WARNING] Error loading skeleton config for {config_type}: {e}")
            
        if not hasattr(self, "spidey_sense"):
            self.spidey_sense = 0.65 if self.tier == "boss" else (0.45 if self.tier == "elite" else 0.25)
            self.teleport_dist_min = 180
            self.teleport_dist_max = 280 if self.tier == "boss" else 240
            self.teleport_cooldown = 3.0 if self.tier == "boss" else (3.5 if self.tier == "elite" else 4.5)
            self.teleport_reaction_delay = 0.06 if self.tier == "boss" else 0.10

        self._teleport_defense_enabled: bool = (not self.explode_on_proximity and not self.is_flying)
        self._teleport_cooldown_timer: float = 0.0
        self._teleport_reaction_timer: float = 0.0
        self._teleport_vanish_timer: float = 0.0
        self._is_teleporting: bool = False
        self._teleport_arrival_pending: bool = False
        self._teleport_target_x: int = 0
        self._teleport_target_facing_left: bool = False
        self._teleport_counter_attack: bool = False
        self._active_vfx: list[BoneDustEffect] = []

        # Combo attack coordination state
        self._combo_count: int = 0
        self._max_combo: int = 0 if self.explode_on_proximity else (2 if self.tier == "minion" else 3)
        self._last_attack_type: int = 1

        # Load bone dust VFX frames (scaled up to cover entire skeleton stature)
        self._bone_dust_frames: list[pg.Surface] = []
        try:
            dust_path = "assets/graphics/Pixel Explosion Effects Pack 01 v1_1/DustExplosion/Frames"
            raw_dust = AssetManager.get_animation_frames(dust_path)
            target_w = max(140, int(130 * self.scale))
            target_h = max(140, int(130 * self.scale))
            self._bone_dust_frames = [
                pg.transform.scale(f, (target_w, target_h)) for f in raw_dust
            ]
        except Exception as e:
            print(f"[WARNING] Failed to load bone dust frames: {e}")

        if custom_health is not None:
            self._max_health = custom_health
        if custom_speed is not None:
            self._speed = float(custom_speed)
        self._health: float = self._max_health

        atk_hit_frames = self._custom_hit_frames if self._custom_hit_frames is not None else self.ATTACK_1_CONFIG.hit_frames
        atk_damage = self.explode_damage if self.explode_on_proximity else (self.ATTACK_1_CONFIG.base_damage * damage_scale)
        atk_kb = (12.0 if self.explode_on_proximity else self.ATTACK_1_CONFIG.knockback_force * knockback_scale)

        self.attack1_config = AttackConfig(
            hit_frames=atk_hit_frames,
            base_damage=atk_damage,
            knockback_force=atk_kb,
        )
        self.attack2_config = AttackConfig(
            hit_frames=atk_hit_frames if self._custom_hit_frames is not None else self.ATTACK_2_CONFIG.hit_frames,
            base_damage=atk_damage if self.explode_on_proximity else (self.ATTACK_2_CONFIG.base_damage * damage_scale),
            knockback_force=atk_kb if self.explode_on_proximity else (self.ATTACK_2_CONFIG.knockback_force * knockback_scale),
        )

        # Tune ATTACK speed slightly brisker for custom spritesheets / proximity detonators
        if spritesheet_path:
            self.state_configs[SkeletonState.ATTACK] = StateConfig(
                0.11 if self.explode_on_proximity else 0.13,
                loops=False,
                next_state=SkeletonState.IDLE,
                interruptible=False,
            )

        # Initial setup & spawn facing toward player
        p_rect = getattr(player, "rect", None) if player is not None else None
        if p_rect is not None and isinstance(getattr(p_rect, "centerx", None), (int, float)):
            self.facing_left = (x > p_rect.centerx)
        self.set_state(SkeletonState.IDLE)
        if self.state in self.animations:
            self.image = self.animations[self.state][0]
            if self.facing_left != getattr(self, "natively_facing_left", False):
                self.image = pg.transform.flip(self.image, True, False)
        self.rect: pg.Rect = self.image.get_rect(midbottom=(x, y))

        # Tight pre-trimmed hitboxes for spritesheet/normalized Damned enemies vs registry margins
        if self._sheet_body_margins is not None:
            ml, mr, mt, mb = self._sheet_body_margins
            self.adjust_hitbox_sides(left=ml, right=mr, top=mt, bottom=mb)
        elif spritesheet_path:
            self.adjust_hitbox_sides(left=4, right=4, top=6, bottom=0)
        else:
            self.adjust_hitbox_sides(left=margins.left, right=margins.right, top=margins.top, bottom=margins.bottom)

        # Movement and physics (sub-pixel tracking + inertia smoothing)
        self._pos_x: float = float(self.rect.x)
        self._last_rect_x: int = self.rect.x
        self._vel_x: float = 0.0
        self._target_vx: float = 0.0
        self._gravity: float = 0.0
        self._knockback_vel_x: float = 0.0
        self._checked_player_attack_id: Optional[tuple] = None
        surf = pg.display.get_surface()
        height = surf.get_height() if surf else 720
        self._ground_y: Optional[int] = height - margins.ground_offset

        # AI configuration & perception components
        if not hasattr(self, "_detection_range"):
            self._detection_range = 3000 if self.tier == "boss" else 1000
        if not hasattr(self, "_attack_range"):
            self._attack_range = self.explode_trigger_range if self.explode_on_proximity else 60
        elif self.explode_on_proximity:
            self._attack_range = self.explode_trigger_range
        if not hasattr(self, "_vertical_tolerance"):
            self._vertical_tolerance = 500 if self.tier == "boss" else 100
        self.spawn_zone: Optional[dict] = None

        self.perception = PerceptionSystem(
            vision_range=float(self._detection_range),
            hearing_range=650.0,
            reaction_delay_sec=0.14 if self.explode_on_proximity else 0.18,
        )
        self.utility_engine = UtilityCombatEngine(
            has_dash_evasion=False,
            has_block_anim=False,
            preferred_spacing=float(self._attack_range),
        )
        SquadTokenManager.get_instance().register_enemy(id(self), self.tier)

        # Size melee attack hitboxes proportionally to actual body rect (prevents huge 236px boxes)
        if spritesheet_path or (sprite_root and "skeletonzombie" in sprite_root.lower()):
            self._scaled_hitbox_w = max(54, min(104, int(self.rect.width * 1.35)))
            self._scaled_hitbox_h = max(54, min(110, int(self.rect.height * 0.90)))
        else:
            self._scaled_hitbox_w = int(self._attack_hitbox_width * self.scale)
            self._scaled_hitbox_h = min(int(self._attack_hitbox_height * self.scale), max(96, int(self.rect.height * 1.05)))

        # Audio trigger system (non-fatal; gracefully skipped if audio_manager is None)
        _entity_audio_key = "skeleton_boss" if self.tier == "boss" else ("skeleton_zombie" if (sprite_root and "zombie" in (sprite_root or "").lower()) else "skeleton_minion")
        self._init_entity_audio_config(audio_manager, _entity_audio_key)

    def _normalize_folder_body_alignment(self) -> None:
        """Align multi-folder animations onto a shared feet-grounded, body-centered canvas."""
        all_states = list(self.animations.keys())
        idle0 = self.animations[SkeletonState.IDLE][0]
        idle_br = idle0.get_bounding_rect(min_alpha=10)
        if idle_br.width <= 0 or idle_br.height <= 0:
            return
        max_w = max(f.get_width() for st in all_states for f in self.animations[st] if f)
        max_h = max(f.get_height() for st in all_states for f in self.animations[st] if f)
        # Keep tight body height up to tall frames, anchor every frame's visual bottom cleanly
        canvas_w = max_w
        canvas_h = max_h
        anchor_cx = canvas_w // 2
        anchor_bot = canvas_h

        def recenter(frames: list[pg.Surface]) -> list[pg.Surface]:
            out = []
            for f in frames:
                br = f.get_bounding_rect(min_alpha=10)
                c = pg.Surface((canvas_w, canvas_h), pg.SRCALPHA)
                if br.width > 0 and br.height > 0:
                    dx = anchor_cx - br.centerx
                    dy = anchor_bot - br.bottom
                    c.blit(f, (dx, dy))
                out.append(c)
            return out

        for st in list(self.animations.keys()):
            self.animations[st] = recenter(self.animations[st])
        self._attack1_frames = self.animations.get(SkeletonState.ATTACK, self._attack1_frames)
        self._attack2_frames = self._attack1_frames

        # Compact body hurtbox around the centered visual torso/skull of IDLE
        new_idle_br = self.animations[SkeletonState.IDLE][0].get_bounding_rect(min_alpha=10)
        body_w = min(new_idle_br.width, max(54, int(idle_br.width * 0.72)))
        m_side = max(0, (canvas_w - body_w) // 2)
        m_top = max(0, new_idle_br.top + 4)
        self._sheet_body_margins = (m_side, canvas_w - m_side - body_w, m_top, 0)

    def _load_spritesheet_animations(
        self,
        spritesheet_path: str,
        sheet_grid: Sequence[int],
        row_map: dict[str, Sequence[int]],
        tint_color: Optional[Sequence[int]] = None,
        shadow_outline_color: Optional[Sequence[int]] = None,
    ) -> None:
        """Load, outline-soften, action-preserve union-trim, and cache grid sheet animations."""
        cache_key = (
            spritesheet_path,
            int(sheet_grid[0]),
            int(sheet_grid[1]),
            tuple((k, tuple(v)) for k, v in sorted(row_map.items())),
            round(self.scale, 2),
            tuple(tint_color) if tint_color else None,
            tuple(shadow_outline_color) if shadow_outline_color else None,
            self.explode_on_proximity,
        )
        cached = Skeleton._SHEET_ANIM_CACHE.get(cache_key)
        if cached is not None:
            for k, frames in cached["anims"].items():
                self.animations[k] = frames
            self._attack1_frames = cached["atk1"]
            self._attack2_frames = cached["atk2"]
            self._custom_hit_frames = cached["hit_frames"]
            self._sheet_body_margins = cached.get("body_margins")
            return

        raw = AssetManager.get_texture(spritesheet_path)
        cols, rows = max(1, int(sheet_grid[0])), max(1, int(sheet_grid[1]))
        cw = max(1, raw.get_width() // cols)
        ch = max(1, raw.get_height() // rows)

        def extract_row(row_idx: int, count: int) -> list[pg.Surface]:
            out = []
            for c in range(min(count, cols)):
                cell = raw.subsurface(pg.Rect(c * cw, row_idx * ch, cw, ch))
                if cell.get_bounding_rect(min_alpha=10).width > 0:
                    out.append(cell)
            return out

        raw_rows: dict[str, list[pg.Surface]] = {}
        for key, spec in row_map.items():
            r_idx = int(spec[0])
            cnt = int(spec[1]) if len(spec) > 1 else cols
            if 0 <= r_idx < rows:
                raw_rows[key] = extract_row(r_idx, cnt)

        # Compute body_rect from idle + walk (torso/feet bounds), then expand symmetrically up/wide
        # across attack frames so leaping/punching limbs (e.g. Imp swoop) never get cropped!
        body_cells = raw_rows.get("idle", []) + raw_rows.get("walk", []) + raw_rows.get("chase", [])
        if not body_cells:
            body_cells = [f for fs in raw_rows.values() for f in fs]
        if body_cells:
            body_rect = body_cells[0].get_bounding_rect(min_alpha=10)
            for cell in body_cells[1:]:
                br = cell.get_bounding_rect(min_alpha=10)
                if br.width > 0 and br.height > 0:
                    body_rect = body_rect.union(br) if body_rect.width > 0 else br
            if body_rect.width <= 0 or body_rect.height <= 0:
                body_rect = pg.Rect(0, 0, cw, ch)
        else:
            body_rect = pg.Rect(0, 0, cw, ch)

        action_rect = body_rect.copy()
        for cell in raw_rows.get("attack", []):
            br = cell.get_bounding_rect(min_alpha=10)
            if br.width > 0 and br.height > 0:
                action_rect = action_rect.union(br)

        # Symmetrical horizontal canvas around body_rect.centerx keeps facing flips centered cleanly
        half_w = max(
            body_rect.centerx - action_rect.left,
            action_rect.right - body_rect.centerx,
            body_rect.width // 2,
        )
        canvas_raw_w = max(1, half_w * 2)
        crop_top = max(0, min(body_rect.top, action_rect.top))
        crop_bottom = min(ch, max(body_rect.bottom, action_rect.bottom) if self.explode_on_proximity else body_rect.bottom)
        canvas_raw_h = max(1, crop_bottom - crop_top)

        # Symmetrical body hitbox margins inside the scaled canvas
        body_half_w = max(1, body_rect.width // 2)
        m_side = max(0, int((half_w - body_half_w) * self.scale))
        m_top = max(0, int((body_rect.top - crop_top) * self.scale) + 4)
        body_margins = (m_side, m_side, m_top, 0)

        def process_cell(cell: pg.Surface, keep_full_width: bool = False) -> pg.Surface:
            if keep_full_width:
                sub = cell.subsurface(pg.Rect(0, crop_top, cw, min(ch - crop_top, canvas_raw_h + 2))).copy()
            else:
                sub = pg.Surface((canvas_raw_w, canvas_raw_h), pg.SRCALPHA)
                src_l = max(0, body_rect.centerx - half_w)
                src_r = min(cw, body_rect.centerx + half_w)
                dst_x = src_l - (body_rect.centerx - half_w)
                sub.blit(cell, (dst_x, 0), pg.Rect(src_l, crop_top, max(1, src_r - src_l), canvas_raw_h))

            if shadow_outline_color and len(shadow_outline_color) >= 3:
                sr, sg, sb = int(shadow_outline_color[0]), int(shadow_outline_color[1]), int(shadow_outline_color[2])
                for py in range(sub.get_height()):
                    for px in range(sub.get_width()):
                        r, g, b, a = sub.get_at((px, py))
                        if a < 10:
                            continue
                        lum = (r + g + b) / 3.0
                        if lum < 42.0:
                            t = 1.0 - (lum / 42.0)
                            sub.set_at((px, py), (
                                max(0, min(255, int(r * (1.0 - t) + sr * t))),
                                max(0, min(255, int(g * (1.0 - t) + sg * t))),
                                max(0, min(255, int(b * (1.0 - t) + sb * t))),
                                a,
                            ))
            if tint_color and len(tint_color) >= 3:
                ts = pg.Surface(sub.get_size(), pg.SRCALPHA)
                ts.fill((int(tint_color[0]), int(tint_color[1]), int(tint_color[2]), 255))
                sub.blit(ts, (0, 0), special_flags=pg.BLEND_RGBA_MULT)

            tw = max(1, int(sub.get_width() * self.scale))
            th = max(1, int(sub.get_height() * self.scale))
            return pg.transform.scale(sub, (tw, th))

        idle_frames = [process_cell(c) for c in (raw_rows.get("idle") or raw_rows.get("walk") or body_cells[:1])]
        walk_raw = raw_rows.get("walk") or raw_rows.get("chase") or raw_rows.get("idle") or body_cells[:1]
        walk_frames = [process_cell(c) for c in walk_raw]
        atk_raw = raw_rows.get("attack") or walk_raw
        atk_frames = [process_cell(c, keep_full_width=self.explode_on_proximity) for c in atk_raw]
        if self.explode_on_proximity and len(atk_frames) >= 2:
            atk_frames = [atk_frames[0], atk_frames[0], atk_frames[0]] + atk_frames[1:]
            custom_hf = frozenset({3, 4})
        else:
            mid = max(1, len(atk_frames) // 2)
            custom_hf = frozenset({mid - 1, mid} if len(atk_frames) >= 4 else {max(0, len(atk_frames) - 1)})

        hurt_raw = raw_rows.get("hurt") or [idle_frames[0]]
        hurt_frames = [process_cell(c) if c.get_size() == (cw, ch) else c for c in (raw_rows.get("hurt") or [])] or [idle_frames[0]]
        death_raw = raw_rows.get("death") or raw_rows.get("die") or atk_raw
        death_frames = [process_cell(c, keep_full_width=True) for c in death_raw]

        anims = {
            SkeletonState.IDLE: idle_frames,
            SkeletonState.CHASE: walk_frames,
            SkeletonState.ATTACK: atk_frames,
            SkeletonState.HURT: hurt_frames,
            SkeletonState.DEATH: death_frames,
        }
        Skeleton._SHEET_ANIM_CACHE[cache_key] = {
            "anims": anims,
            "atk1": atk_frames,
            "atk2": atk_frames,
            "hit_frames": custom_hf,
            "body_margins": body_margins,
        }
        for k, frames in anims.items():
            self.animations[k] = frames
        self._attack1_frames = atk_frames
        self._attack2_frames = atk_frames
        self._custom_hit_frames = custom_hf
        self._sheet_body_margins = body_margins

        
    def _load_frames(
        self,
        path_pattern: str,
        count: int,
        scale_factor: Optional[float] = None,
    ) -> list[pg.Surface]:
        """
        Load and scale animation frames from a file pattern.
        
        Args:
            path_pattern: Format string for frame paths with index placeholder.
            count: Number of frames to load (0-indexed).
            scale_factor: Multiplier for sprite dimensions.
            
        Returns:
            List of scaled pygame Surface objects.
            
        Raises:
            RuntimeError: If no frames could be loaded from the pattern.
        """
        if scale_factor is None:
            scale_factor = self.scale

        frames: list[pg.Surface] = []
        
        for i in range(count):
            path = path_pattern.format(i)
            try:
                frame = AssetManager.get_texture(path)
                original_size = frame.get_size()
                scaled_size = (
                    int(original_size[0] * scale_factor),
                    int(original_size[1] * scale_factor),
                )
                scaled_frame = pg.transform.scale(frame, scaled_size)
                frames.append(scaled_frame)
            except (FileNotFoundError, pg.error) as e:
                # Log but continue - partial animation sets may be acceptable
                print(f"Warning: Failed to load frame {i} from '{path}': {e}")
                
        if not frames:
            raise RuntimeError(
                f"Failed to load any frames from pattern: {path_pattern}"
            )
            
        return frames
    
    # ─────────────────────────────────────────────────────────────────────────
    # Public API: Combat and State Inspection
    # ─────────────────────────────────────────────────────────────────────────
    
    @property
    def health(self) -> float: return self._health
    @property
    def max_health(self) -> float: return self._max_health
    @property
    def entity_id(self) -> int: return id(self)
    @property
    def is_dead(self) -> bool: return self.state == SkeletonState.DEATH
    @property
    def is_teleporting(self) -> bool: return self._is_teleporting
    @property
    def is_invincible(self) -> bool: return self._is_teleporting or self.state in (SkeletonState.HURT, SkeletonState.DEATH)
    @property
    def current_frame_index(self) -> int: return int(self.animation_index)

    def is_in_hit_frame(self) -> bool:
        if self.state != SkeletonState.ATTACK:
            return False
        return self.attack_state.is_hit_frame_active()

    def should_deal_damage(self) -> bool:
        if self.state != SkeletonState.ATTACK:
            return False
        return self.attack_state.is_hit_frame_active()

    def set_state(self, new_state: Enum, force: bool = False) -> None:
        old_state = self.state
        super().set_state(new_state, force=force)
        if old_state == SkeletonState.ATTACK and self.state != SkeletonState.ATTACK:
            self.attack_state.end()

    def register_hit(self, target_id: int = 0) -> bool:
        return self.attack_state.try_register_hit(target_id)

    def try_register_hit(self, target_id: int) -> bool:
        return self.attack_state.try_register_hit(target_id)

    def get_current_attack_damage(self) -> float:
        return self.attack_state.get_current_damage()

    def get_current_attack_knockback(self) -> float:
        return self.attack_state.config.knockback_force if self.attack_state.config else 0.0

    def get_attack_hitbox(self) -> Optional[pg.Rect]:
        """Return the attack hitbox based on skeleton facing and position."""
        if not self.should_deal_damage():
            return None
        if self.explode_on_proximity:
            rad = max(40, int(self.explode_radius))
            return pg.Rect(
                self.rect.centerx - rad,
                self.rect.centery - rad // 2,
                rad * 2,
                rad,
            )
        hitbox_w = self._scaled_hitbox_w
        hitbox_h = self._scaled_hitbox_h
        if self.facing_left:
            hitbox_x = self.rect.left - hitbox_w
        else:
            hitbox_x = self.rect.right
        hitbox_y = self.rect.centery - hitbox_h // 2
        return pg.Rect(hitbox_x, hitbox_y, hitbox_w, hitbox_h)

    def update_animation(self, dt: float) -> None:
        """Orient frames consistently for natively-left and natively-right sprites."""
        orig_facing = self.facing_left
        self.facing_left = (orig_facing != getattr(self, "natively_facing_left", False))
        try:
            super().update_animation(dt)
        finally:
            self.facing_left = orig_facing

    def update(self, dt: Optional[float] = None, scroll_speed: int = 0) -> None:
        if dt is None: dt = 1.0 / 60.0
        dt_sec = dt if dt < 1.0 else dt / 1000.0
        if self.is_flying:
            self._flight_clock += dt_sec

        # Pick up any external position adjustments (e.g. test setups or knockback hooks)
        if self.rect.x != self._last_rect_x:
            self._pos_x = float(self.rect.x)

        self._pos_x -= float(scroll_speed)
        self.rect.x = int(round(self._pos_x))
        self._last_rect_x = self.rect.x
        if getattr(self, "_teleport_arrival_pending", False):
            self._teleport_target_x -= scroll_speed

        # Decrement teleport cooldown timer
        if self._teleport_cooldown_timer > 0.0:
            self._teleport_cooldown_timer = max(0.0, self._teleport_cooldown_timer - dt_sec)

        # Decrement teleport vanish timer (split-second delay from disappear to appear)
        if self._teleport_vanish_timer > 0.0:
            self._teleport_vanish_timer = max(0.0, self._teleport_vanish_timer - dt_sec)
            if self._teleport_vanish_timer == 0.0:
                if getattr(self, "_teleport_arrival_pending", False):
                    self._execute_teleport_arrival()
                else:
                    self._is_teleporting = False

        # Update active bone dust effects
        self._update_vfx(dt_sec, scroll_speed)

        # Apply horizontal knockback velocity
        if abs(self._knockback_vel_x) > 0.1:
            self._pos_x += float(self._knockback_vel_x)
            self.rect.x = int(round(self._pos_x))
            self._last_rect_x = self.rect.x
            self._knockback_vel_x *= 0.8  # Decay knockback over time
        else:
            self._knockback_vel_x = 0.0

        self._apply_gravity()
        self._target_vx = 0.0
        if not self._is_teleporting:
            self._update_ai(dt_sec)

        # Smooth inertia & crowd spacing integration (eliminates integer-step jitter and moonwalking)
        if self.state == SkeletonState.CHASE and not self._is_teleporting:
            if self._target_vx * self._vel_x < 0.0:
                self._vel_x = 0.0
            accel = min(1.0, dt_sec * 14.0)
            self._vel_x += (self._target_vx - self._vel_x) * accel
            if abs(self._vel_x) > 0.15:
                self.facing_left = (self._vel_x < 0.0)
        else:
            self._vel_x = 0.0
        if abs(self._vel_x) > 0.05:
            self._pos_x += self._vel_x * dt_sec * 60.0
            self.rect.x = int(round(self._pos_x))
            self._last_rect_x = self.rect.x

        was_in_attack = (self.state == SkeletonState.ATTACK)
        super().update(dt)  # State machine + Skeleton.update_animation handles flip cleanly
        self._update_animation_audio()

        # Check for immediate follow-up attack / combo chaining when attack finishes
        just_finished_attack = was_in_attack and (self.state != SkeletonState.ATTACK)
        if just_finished_attack and self.explode_on_proximity and self._explode_fuse_started:
            SquadTokenManager.get_instance().unregister_enemy(id(self))
            self.kill()
            return
        if just_finished_attack and self._player and not getattr(self._player, "is_dead", False):
            player_rect = getattr(self._player, "rect", None)
            if player_rect:
                edge_x, dist_y = self._get_edge_distance_to_player(player_rect)
                in_reach = (edge_x <= max(60, self._attack_range) and dist_y < self._vertical_tolerance)
                player_to_left = (player_rect.centerx < self.rect.centerx)
                facing_player = (player_to_left == self.facing_left)
                if in_reach and facing_player and self._combo_count < self._max_combo:
                    self._combo_count += 1
                    next_anim = 2 if self._last_attack_type == 1 else 1
                    self._begin_attack(force_anim=next_anim)
                else:
                    self._combo_count = 0
        
        # Release token if attack completed or left attack state
        if self.state != SkeletonState.ATTACK:
            SquadTokenManager.get_instance().release_attack_token(id(self))

        # Cleanup on death animation completion
        if self.state == SkeletonState.DEATH and int(self.animation_index) >= len(self.animations[SkeletonState.DEATH]) - 1:
            SquadTokenManager.get_instance().unregister_enemy(id(self))
            self.kill()

    def kill(self) -> None:
        SquadTokenManager.get_instance().unregister_enemy(id(self))
        super().kill()

    def take_damage(self, amount: float = 0.5, knockback: tuple[float, float] | None = None) -> bool:
        if self.state in (SkeletonState.HURT, SkeletonState.DEATH):
            return False

        # Complete iframe immunity during teleportation
        if self._is_teleporting:
            return False

        SquadTokenManager.get_instance().release_attack_token(id(self))
        self._combo_count = 0

        # Lower health, but never allow health to go below 0.
        self._health = max(0.0, self._health - amount)

        # If the skeleton was attacking, cancel the attack.
        self.attack_state.end()

        # If health is finished, switch to death animation.
        if self._health <= 0:
            SquadTokenManager.get_instance().unregister_enemy(id(self))
            self.set_state(SkeletonState.DEATH, force=True)
        # Otherwise, switch to hurt animation.
        else:
            self.set_state(SkeletonState.HURT, force=True)

        # Apply knockback if provided
        if knockback:
            self._knockback_vel_x = knockback[0] * 1.5
            if knockback[1] < 0:
                self._gravity = knockback[1] * 1.2
            else:
                self._gravity = -abs(knockback[0]) * 0.4
        return True
    
    # ─────────────────────────────────────────────────────────────────────────
    # Private: AI Logic
    # ─────────────────────────────────────────────────────────────────────────
    
    def _get_edge_distance_to_player(self, player_rect: pg.Rect) -> tuple[float, float]:
        """Calculate horizontal edge-to-edge distance and vertical center distance."""
        if self.rect.centerx < player_rect.centerx:
            edge_x = max(0, player_rect.left - self.rect.right)
        else:
            edge_x = max(0, self.rect.left - player_rect.right)
        dist_y = abs(self.rect.centery - player_rect.centery)
        return float(edge_x), float(dist_y)

    def _update_ai(self, dt_sec: float = 0.016) -> None:
        if self._player is None or self.state in (SkeletonState.HURT, SkeletonState.DEATH):
            return

        # Check for incoming player attacks and execute timed Bone Dust dodge
        self._detect_incoming_danger(dt_sec)
        if self._is_teleporting:
            return
            
        player_rect = getattr(self._player, "rect", None)
        if player_rect is None:
            return

        # 1. Update Perception (Vision Cone & Audio Detection)
        alert = self.perception.update(dt_sec, self.rect, self.facing_left, self._player)
        if alert == AlertLevel.UNAWARE and not self.explode_on_proximity:
            self.set_state(SkeletonState.IDLE)
            return

        if self.state == SkeletonState.ATTACK:
            return

        # Flying enemies steer smoothly at hover altitude toward player
        if self.is_flying:
            base_y = self._hover_y if self._hover_y is not None else max(240, player_rect.centery - 28)
            target_y = base_y + int(math.sin(self._flight_clock * 4.5) * 14.0)
            dy = target_y - self.rect.centery
            self.rect.y += max(-3, min(3, dy))
            if self._ground_y is not None and self.rect.bottom > self._ground_y - 52:
                self.rect.bottom = self._ground_y - 52

        edge_x, dist_y = self._get_edge_distance_to_player(player_rect)
        dist_x = abs(self.rect.centerx - player_rect.centerx)

        # Chasing proximity exploders (Bloated Damned / Demon Eye): relentlessly close distance and swell-detonate
        if self.explode_on_proximity:
            if edge_x <= self.explode_trigger_range and dist_y <= max(self._vertical_tolerance, 115):
                self.facing_left = (self.rect.centerx > player_rect.centerx)
                self._explode_fuse_started = True
                self._begin_attack(force_anim=1)
                return
            self.set_state(SkeletonState.CHASE)
            self._chase_player(player_rect)
            return

        in_melee_reach = (edge_x <= max(55, self._attack_range) and dist_y < self._vertical_tolerance)

        # 2. Check Attack Token & Squad Coordinator Pincer Signals
        has_token = SquadTokenManager.get_instance().request_attack_token(id(self))

        is_pincer = SquadCoordinator.get_instance().should_trigger_pincer_attack(
            id(self), dist_x, can_attack=(in_melee_reach or dist_x <= self._attack_range + 20)
        )

        # 3. Utility Engine Action Evaluation
        action = self.utility_engine.evaluate_action(
            enemy_rect=self.rect,
            player=self._player,
            can_attack=in_melee_reach,
            has_attack_token=has_token,
            dt_sec=dt_sec,
        )

        if is_pincer or action == TacticalAction.PUNISH_WHIFF or action == TacticalAction.ATTACK or (in_melee_reach and has_token):
            self.facing_left = (self.rect.centerx > player_rect.centerx)
            self._begin_attack()
        elif action == TacticalAction.RETRACT_SPACING:
            # Turn outward when repositioning away so walk legs match actual travel direction (no moonwalking)
            step_dir = 1 if self.rect.centerx > player_rect.centerx else -1
            self._target_vx = step_dir * (self._speed * 0.85)
            self.facing_left = (step_dir < 0)
            self.set_state(SkeletonState.CHASE)
        elif in_melee_reach:
            # Hold combat stance facing the player; do NOT awkwardly play chase/walk animation
            self._target_vx = 0.0
            self.set_state(SkeletonState.IDLE)
            self.facing_left = (self.rect.centerx > player_rect.centerx)
        elif action == TacticalAction.CHASE:
            self.set_state(SkeletonState.CHASE)
            self._chase_player(player_rect)
        else:
            self._target_vx = 0.0
            self.facing_left = (self.rect.centerx > player_rect.centerx)
            self.set_state(SkeletonState.IDLE)

        # Gentle horizontal separation so squad members spread naturally instead of stacking 1:1
        if self.state == SkeletonState.CHASE and not self.explode_on_proximity:
            sep_push = 0.0
            for grp in self.groups():
                for other in grp:
                    if other is self or not isinstance(other, Skeleton) or not other.alive():
                        continue
                    diff_x = self.rect.centerx - other.rect.centerx
                    if abs(diff_x) < 42 and abs(self.rect.centery - other.rect.centery) < 60:
                        sep_push += (1.1 if diff_x >= 0 else -1.1)
            if sep_push != 0.0:
                self._target_vx += max(-1.4, min(1.4, sep_push))

    def _begin_attack(self, force_anim: Optional[int] = None) -> None:
        """Initiate attack animation and config, alternating for fluid combos."""
        self._target_vx = 0.0
        self._vel_x = 0.0
        if force_anim == 2 or (force_anim is None and self._last_attack_type == 1):
            # Secondary attack animation
            self.animations[SkeletonState.ATTACK] = self._attack2_frames
            self.current_attack_config = self.attack2_config
            self._last_attack_type = 2
        else:
            # Primary attack animation
            self.animations[SkeletonState.ATTACK] = self._attack1_frames
            self.current_attack_config = self.attack1_config
            self._last_attack_type = 1
        self.set_state(SkeletonState.ATTACK, force=True)

    def _chase_player(self, player_rect: pg.Rect) -> None:
        if self.explode_on_proximity:
            target_x = float(player_rect.centerx)
        else:
            target_x = SquadCoordinator.get_instance().get_target_offset_x(
                id(self), player_rect, getattr(self._player, "facing_left", False), float(self._attack_range), enemy_x=float(self.rect.centerx)
            )
        dx = target_x - self.rect.centerx
        if abs(dx) > 6.0:
            move_dir = 1.0 if dx > 0 else -1.0
            self._target_vx = move_dir * float(self._speed)
            self.facing_left = (move_dir < 0)
        else:
            self._target_vx = 0.0
            self.facing_left = (self.rect.centerx > player_rect.centerx)
            if not self.explode_on_proximity:
                self.set_state(SkeletonState.IDLE)

    def _detect_incoming_danger(self, dt_sec: float) -> None:
        """Detect incoming player attacks and execute timed bone dust shatter dodge."""
        if not self._teleport_defense_enabled or self.spidey_sense <= 0.0:
            return
        if self._is_teleporting or self._teleport_cooldown_timer > 0.0:
            self._teleport_reaction_timer = 0.0
            return
        if self._player is None or self.state in (SkeletonState.HURT, SkeletonState.DEATH):
            self._teleport_reaction_timer = 0.0
            return

        player_rect = getattr(self._player, "rect", None)
        if player_rect is None:
            return

        # Check if player is actively attacking
        if hasattr(self._player, "is_attacking") and not getattr(self._player, "is_attacking"):
            self._teleport_reaction_timer = 0.0
            return

        player_state = getattr(self._player, "state", None)
        state_val = getattr(player_state, "value", player_state)
        state_name = getattr(player_state, "name", str(player_state))

        is_player_attacking = False
        if isinstance(state_val, int) and 20 <= state_val <= 23:
            is_player_attacking = True
        elif "ATTACK" in state_name:
            is_player_attacking = True

        if not is_player_attacking:
            is_player_attacking = getattr(self._player, "is_attacking", False)
        if not is_player_attacking and hasattr(self._player, "is_in_hit_frame"):
            try:
                is_player_attacking = self._player.is_in_hit_frame()
            except Exception:
                pass

        if not is_player_attacking:
            self._teleport_reaction_timer = 0.0
            self._checked_player_attack_id = None
            return

        # Classify attack type for dynamic danger zone & timing synchronization
        is_power = (state_val == 22 or "POWER" in state_name)
        is_smash = (state_val == 21 or "SMASH" in state_name)
        is_special = (state_val == 23 or "SPECIAL" in state_name)
        is_thrust = (state_val == 20 or "THRUST" in state_name)
        is_enhanced = getattr(self._player, "_is_enhanced", False)

        # Dynamic danger radius matching weapon reach:
        # Power Attack (W) reaches ~426px, Smash (E) reaches ~321px, Thrust (Q) reaches ~308px, Special (F) reaches ~320-450px
        if is_power:
            danger_radius = 480 if is_enhanced else 450
        elif is_smash:
            danger_radius = 390 if is_enhanced else 360
        elif is_special:
            danger_radius = 480 if is_enhanced else 370
        elif is_thrust:
            danger_radius = 370 if is_enhanced else 340
        else:
            danger_radius = max(340, self._attack_range + 220)

        dist_x = abs(self.rect.centerx - player_rect.centerx)
        vert_diff = min(abs(self.rect.bottom - player_rect.bottom), abs(self.rect.centery - player_rect.centery))
        vertical_tol = getattr(self, "_vertical_tolerance", 100)

        # Check proximity in danger zone
        if dist_x > danger_radius or vert_diff > vertical_tol:
            self._teleport_reaction_timer = 0.0
            return

        # Check player facing direction towards skeleton
        # Power Attack is a 360-degree spin; Enhanced attacks have reverse-hitting frames.
        is_omni_directional = is_power or (is_enhanced and (is_smash or is_thrust))
        if not is_omni_directional:
            player_facing_left = getattr(self._player, "facing_left", False)
            player_to_left = player_rect.centerx < self.rect.centerx
            if player_to_left and player_facing_left:
                self._teleport_reaction_timer = 0.0
                return
            if not player_to_left and not player_facing_left:
                self._teleport_reaction_timer = 0.0
                return

        # Startup synchronization for long-channel attacks
        # Special Attack has 18 frames of chanting/windup before the storm bursts at frame 19.
        # Starting reaction at frame >= 14 ensures the skeleton dissolves into bone dust right as the slashes erupt.
        player_anim_idx = getattr(self._player, "animation_index", None)
        if player_anim_idx is not None:
            cur_frame = int(player_anim_idx)
            is_hit_active = False
            attack_state = getattr(self._player, "attack_state", None)
            if attack_state is not None and hasattr(attack_state, "is_hit_frame_active"):
                try:
                    is_hit_active = attack_state.is_hit_frame_active()
                except Exception:
                    pass

            if not is_hit_active and is_special and cur_frame < 14:
                return

        # Evaluate dodge probability at most once per enemy swing (prevents 60Hz multi-roll)
        atk_key = (state_val, id(self._player))
        if self._teleport_reaction_timer <= 0.0:
            if self.spidey_sense < 0.99 and self._checked_player_attack_id == atk_key:
                return
            self._checked_player_attack_id = atk_key
            if self.spidey_sense >= 0.99 or random.random() <= self.spidey_sense:
                self._teleport_reaction_timer = max(0.01, self.teleport_reaction_delay)
            else:
                return
        self._teleport_reaction_timer -= dt_sec
        if self._teleport_reaction_timer <= 0.0:
            self._trigger_teleport_defense()

    def _trigger_teleport_defense(self, immediate: bool = False) -> None:
        """Shatter into bone dust and relocate to safety or flank behind the player."""
        if self._player is None or self.state == SkeletonState.DEATH:
            return

        player_rect = getattr(self._player, "rect", None)
        if player_rect is None:
            return

        origin_x = self.rect.centerx
        origin_bottom = self.rect.bottom

        # 1. Spawn origin Bone Dust Shatter VFX (Disappearance phase)
        if self._bone_dust_frames:
            origin_vfx = BoneDustEffect(
                origin_x,
                origin_bottom,
                self._bone_dust_frames,
                offset_y=int(40 * self.scale),
            )
            self._active_vfx.append(origin_vfx)

        # 2. Intangibility & disappear (split-second window before appearing)
        self._is_teleporting = True
        self._teleport_vanish_timer = 0.20
        self._teleport_arrival_pending = True

        # 3. Calculate destination coordinates
        player_state = getattr(self._player, "state", None)
        state_val = getattr(player_state, "value", player_state)
        state_name = getattr(player_state, "name", str(player_state))
        is_power = (state_val == 22 or "POWER" in state_name)
        is_special = (state_val == 23 or "SPECIAL" in state_name)
        is_wide_arc = is_power or is_special

        player_facing_left = getattr(self._player, "facing_left", False)
        is_god_mode = self.spidey_sense >= 0.8
        is_boss = (self.tier == "boss")

        # Flank logic:
        # High spidey_sense (> 0.35) or boss: flanks behind player (75% for minions, 95% for boss/god-mode)
        # Low spidey_sense (<= 0.35, e.g. 0.25 in test_minion_teleport_retreat): retreats away to safety
        is_flanker = (is_god_mode or is_boss or (self.spidey_sense > 0.35 and random.random() < 0.75))

        surf = pg.display.get_surface()
        display_w = surf.get_width() if surf else 1280
        max_x = (display_w - 80) if display_w >= 300 else 1200

        if is_flanker or is_god_mode or is_boss:
            # Flank behind the player with clearance tailored to the attack's rear hitboxes:
            # Special reaches up to 199px behind; Power reaches 159px behind; Smash/Thrust reach ~91px behind.
            slot_stagger = (abs(id(self)) % 3) * 28
            if is_special:
                flank_offset = random.randint(240, 280) + slot_stagger
            elif is_power:
                flank_offset = random.randint(210, 250) + slot_stagger
            else:
                flank_offset = random.randint(140, 175) + slot_stagger

            if player_facing_left:
                if player_rect.centerx <= max_x - 140:
                    target_x = min(max_x, player_rect.centerx + flank_offset)
                else:
                    target_x = player_rect.centerx + flank_offset
                new_facing_left = True
            else:
                if player_rect.centerx >= 200:
                    target_x = max(60, player_rect.centerx - flank_offset)
                else:
                    target_x = player_rect.centerx - flank_offset
                new_facing_left = False
        else:
            # Minion/Standard: Retreat backwards away from player
            min_safe_dist = 440 if is_power else 340
            dist_min = max(self.teleport_dist_min, min_safe_dist)
            dist_max = max(self.teleport_dist_max, dist_min + 70)
            dist_offset = random.randint(dist_min, dist_max)
            if origin_x > player_rect.centerx:
                target_x = player_rect.centerx + dist_offset
                new_facing_left = True
            else:
                target_x = player_rect.centerx - dist_offset
                new_facing_left = False

        # Clamp inside level bounds first, then guarantee >= 140px displacement from origin_x
        target_x = max(60, min(max_x, int(target_x)))
        if abs(target_x - origin_x) < 140:
            cand_left = max(60, origin_x - 180)
            cand_right = min(max_x, origin_x + 180)
            if abs(cand_left - origin_x) >= 140 and (origin_x > max_x - 260 or target_x <= origin_x):
                target_x = cand_left
            elif abs(cand_right - origin_x) >= 140:
                target_x = cand_right
            else:
                target_x = cand_left if abs(cand_left - origin_x) >= abs(cand_right - origin_x) else cand_right
        new_facing_left = (target_x > player_rect.centerx)

        # Store destination parameters for the arrival phase
        self._teleport_target_x = target_x
        self._teleport_target_facing_left = new_facing_left
        self._teleport_counter_attack = (is_flanker or is_god_mode or is_boss)

        self._teleport_reaction_timer = 0.0
        self._teleport_cooldown_timer = self.teleport_cooldown

        if immediate:
            self._execute_teleport_arrival()

    def _execute_teleport_arrival(self) -> None:
        """Materialize skeleton at destination and trigger appearance bone dust VFX."""
        self._teleport_arrival_pending = False
        self._is_teleporting = False

        # Materialize at destination
        self.rect.centerx = self._teleport_target_x
        self._pos_x = float(self.rect.x)
        self._last_rect_x = self.rect.x
        self._vel_x = 0.0
        self.facing_left = self._teleport_target_facing_left
        if self._ground_y is not None:
            self.rect.bottom = self._ground_y
        self._gravity = 0.0
        self._knockback_vel_x = 0.0

        # 4. Spawn destination Bone Dust Reformation VFX (Appearance phase)
        if self._bone_dust_frames:
            dest_vfx = BoneDustEffect(
                self.rect.centerx,
                self.rect.bottom,
                self._bone_dust_frames,
                offset_y=int(40 * self.scale),
            )
            self._active_vfx.append(dest_vfx)

        # God mode, boss, or flanker immediately initiates counter-attack from behind
        if self._teleport_counter_attack:
            self._begin_attack()
        else:
            self.set_state(SkeletonState.IDLE)

    def _update_vfx(self, dt_sec: float, scroll_speed: int = 0) -> None:
        """Update active visual effects and clean up finished ones."""
        for vfx in self._active_vfx:
            vfx.update(dt_sec, scroll_speed)
        self._active_vfx = [vfx for vfx in self._active_vfx if not vfx.is_finished]
    
    # ─────────────────────────────────────────────────────────────────────────
    # Private: Physics
    # ─────────────────────────────────────────────────────────────────────────
    
    def set_ground_y(self, ground_y: Optional[int]) -> None:
        """Update physics ground floor level from environment manager (None = freefall)."""
        self._ground_y = ground_y

    def _apply_gravity(self) -> None:
        """Apply gravitational acceleration and ground collision."""
        if self.is_flying:
            self._gravity = 0.0
            return
        self._gravity += 1.0
        self.rect.y += int(self._gravity)

        # Ground collision
        if self._ground_y is not None and self.rect.bottom >= self._ground_y:
            self.rect.bottom = self._ground_y
            self._gravity = 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # Rendering
    # ─────────────────────────────────────────────────────────────────────────

    def draw(self, surface: pg.Surface) -> None:
        """
        Draw the skeleton, active bone dust VFX, and UI elements.
        
        Args:
            surface: Target surface for rendering.
        """
        if self._teleport_vanish_timer <= 0.0:
            # Visual warning glow while swelling before proximity detonation
            if self.explode_on_proximity and self.state == SkeletonState.ATTACK and self.current_frame_index < 3:
                rad = max(36, int(self.explode_radius * 0.65))
                warn = pg.Surface((rad * 2, rad * 2), pg.SRCALPHA)
                alpha = 95 if (self.current_frame_index % 2 == 0) else 55
                pg.draw.circle(warn, (255, 200, 45, alpha), (rad, rad), rad)
                pg.draw.circle(warn, (255, 110, 30, alpha + 35), (rad, rad), int(rad * 0.55))
                surface.blit(warn, (self.rect.centerx - rad, self.rect.centery - rad))
            super().draw(surface)

        # Draw active VFX (bone dust shatter/re-assembly)
        for vfx in self._active_vfx:
            vfx.draw(surface)
        
        # Draw health bar when damaged and alive
        if self._teleport_vanish_timer <= 0.0 and self._health < self._max_health and self.state != SkeletonState.DEATH:
            self._draw_health_bar(surface)
    
    def _draw_health_bar(self, surface: pg.Surface) -> None:
        """Render the health bar above the skeleton."""
        bar_width: int = 40
        bar_height: int = 5
        bar_x: int = self.rect.centerx - bar_width // 2
        bar_y: int = self.rect.top - 10
        
        # Background (empty health)
        pg.draw.rect(
            surface,
            (50, 50, 50),
            (bar_x, bar_y, bar_width, bar_height),
        )
        
        # Current health (red fill)
        health_ratio = self._health / self._max_health
        pg.draw.rect(
            surface,
            (255, 0, 0),
            (bar_x, bar_y, int(bar_width * health_ratio), bar_height),
        )