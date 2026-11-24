"""
DarkRonin enemy & final boss module  -  High-speed warrior with dash-slash combat AI.

Used both for elite Ronin encounters and for the final boss encounter:
Commander Kaelen, The First Vessel (your former mentor in the Star-Fire Watch).
"""

from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Final, Optional, Callable

import pygame as pg

from v3x_zulfiqar_gideon import AssetManager, Actor, AttackConfig
from src.game.audio.entity_audio_mixin import EntityAudioMixin
from .hitbox_registry import HitboxRegistry
from src.game.ai import (
    PerceptionSystem,
    AlertLevel,
    SquadTokenManager,
    SquadCoordinator,
    UtilityCombatEngine,
    TacticalAction,
)

if TYPE_CHECKING:
    from src.game.entities.player import Player


class DarkRoninState(Enum):
    """Enumeration of all possible Dark Ronin behavioral states."""

    DEATH = 0
    HURT = 10
    ATTACK = 20
    DASH_STRIKE = 25
    CHASE = 30
    IDLE = 40


@dataclass(slots=True)
class StateConfig:
    animation_speed: float = 0.15
    loops: bool = True
    next_state: Optional[DarkRoninState] = None
    interruptible: bool = True


class DarkRonin(EntityAudioMixin, Actor):
    """
    High-mobility Dark Ronin warrior / final boss (Commander Kaelen) with high-speed dash strikes.
    """

    hit_vfx_type: Final[str] = "dark_shadow"

    SLASH_CONFIG: Final[AttackConfig] = AttackConfig(
        hit_frames=frozenset({2, 3, 8, 9, 15, 16}),
        base_damage=2.0,
        knockback_force=12.0,
    )

    DASH_STRIKE_CONFIG: Final[AttackConfig] = AttackConfig(
        hit_frames=frozenset({4, 5, 6, 7}),
        base_damage=2.8,
        knockback_force=18.0,
    )

    STATE_CONFIGS: Final[dict[Enum, StateConfig]] = {
        DarkRoninState.IDLE: StateConfig(0.12),
        DarkRoninState.CHASE: StateConfig(0.20),
        DarkRoninState.ATTACK: StateConfig(0.25, loops=False, next_state=DarkRoninState.IDLE, interruptible=False),
        DarkRoninState.DASH_STRIKE: StateConfig(0.22, loops=False, next_state=DarkRoninState.IDLE, interruptible=False),
        DarkRoninState.HURT: StateConfig(0.25, loops=False, next_state=DarkRoninState.IDLE, interruptible=False),
        DarkRoninState.DEATH: StateConfig(0.15, loops=False, interruptible=False),
    }

    def __init__(
        self,
        x: int,
        y: int,
        player: Player,
        audio_manager=None,
        move_speed: float = 4.0,
        tier: str = "elite",
        sprite_root: Optional[str] = None,
        behaviour_map: Optional[dict] = None,
        custom_scale: Optional[float] = None,
        custom_health: Optional[float] = None,
        **kwargs,
    ) -> None:
        super().__init__(x, y)

        self._player: Player = player
        self.state_configs = self.STATE_CONFIGS
        self.move_speed: float = move_speed
        self.tier: str = tier
        self.sprite_root: str = sprite_root or os.path.join("assets", "graphics", "Ronin")
        self._base_path: str = self.sprite_root
        self.behaviour_map = behaviour_map
        self.ai_frozen: bool = False
        self.taunt_callback: Optional[Callable[[str, str], None]] = None

        default_hp = 220.0 if tier == "boss" else 35.0
        hp = float(custom_health) if custom_health is not None else default_hp
        self._health: float = hp
        self._max_health: float = hp
        self._direction: int = -1  # -1 = facing left, 1 = facing right
        self._state: Enum = DarkRoninState.IDLE
        self.state: Enum = DarkRoninState.IDLE
        self.animation_index: float = 0.0

        # Dash strike cooldown & range parameters
        self.dash_cooldown_ms: int = 3200 if tier == "boss" else 4000
        self.last_dash_time: int = -self.dash_cooldown_ms

        # Load hitbox margins
        self.margins = HitboxRegistry.get_margins("dark_ronin")
        self._scale_override: Optional[float] = float(custom_scale) if custom_scale is not None else None

        # Load animations from assets/graphics/Ronin
        self.animations: dict[Enum, list[pg.Surface]] = {}
        self._body_size: tuple[int, int] = (72, 92)
        self._load_animations()

        # Set default image & tight ground-flush body rect
        self.image = self.animations[DarkRoninState.IDLE][0]
        self.rect = pg.Rect(0, 0, self._body_size[0], self._body_size[1])
        surf = pg.display.get_surface()
        screen_h = surf.get_height() if surf else 720
        self.y_ground: int = screen_h - self.margins.ground_offset
        self.rect.midbottom = (x, self.y_ground)
        self._pos_x: float = float(self.rect.x)
        self._last_rect_x: int = self.rect.x
        self._vel_x: float = 0.0

        # Face player cleanly upon spawn
        player_sprite = getattr(player, "sprite", player) if player else None
        p_rect = getattr(player_sprite, "rect", None) if player_sprite else None
        if p_rect is not None and isinstance(getattr(p_rect, "centerx", None), (int, float)):
            self._direction = 1 if p_rect.centerx > self.rect.centerx else -1
        self.facing_left = (self._direction == -1)

        self._hit_targets: set[int] = set()
        self._is_invincible: bool = False
        self._audio_manager = audio_manager

        # Phase-out / Void-transport VFX state (afterimages, rifts, energy streaks)
        self._afterimages: list[dict] = []
        self._phase_rifts: list[dict] = []
        self._transport_sparks: list[dict] = []
        self._dash_phase_out_fired: bool = False
        self._dash_phase_in_fired: bool = False
        self._afterimage_accum: float = 0.0
        self._phase2_triggered: bool = False
        self._is_phase_transporting: bool = False
        self._phase_transport_timer: float = 0.0
        self._phase_transport_origin: tuple[float, float] = (0.0, 0.0)
        self._phase_transport_target_x: float = 0.0

        # AI Perception & Utility Engine
        self.perception = PerceptionSystem(
            vision_range=1500.0,
            hearing_range=800.0,
            reaction_delay_sec=0.12 if tier == "boss" else 0.15,
        )
        self.utility_engine = UtilityCombatEngine(
            has_dash_evasion=True,
            has_block_anim=False,
            preferred_spacing=85.0,
        )
        SquadTokenManager.get_instance().register_enemy(id(self), "boss" if tier == "boss" else "elite")

        # Audio setup
        self._init_entity_audio_config(audio_manager, "skeleton")

    def apply_corruption_scaling(self, corruption_value: float) -> None:
        """Scale HP and speed when player corruption is high (>66)."""
        if not getattr(self, "is_boss", False) and self.tier != "boss":
            return
        if corruption_value > 66:
            self._max_health *= 1.10
            self._health = self._max_health
            self.move_speed *= 1.05

    @property
    def is_dead(self) -> bool:
        return self._state == DarkRoninState.DEATH or self._health <= 0.0

    @property
    def is_invincible(self) -> bool:
        return self._is_invincible

    @property
    def health(self) -> float:
        return self._health

    @property
    def max_health(self) -> float:
        return self._max_health

    @property
    def direction(self) -> int:
        return self._direction

    def _load_animations(self) -> None:
        """Load animation frames from assets/graphics/Ronin."""
        import re
        base_dir = os.path.join("assets", "graphics", "Ronin")
        file_mapping = {
            DarkRoninState.IDLE: "spr_RoninIdle_strip8.png",
            DarkRoninState.CHASE: "spr_RoninRun_strip10.png",
            DarkRoninState.ATTACK: "spr_RoninAttack_strip33.png",
            DarkRoninState.DASH_STRIKE: "spr_RoninDash_strip10.png",
            DarkRoninState.HURT: "spr_RoninGetHit_strip7.png",
            DarkRoninState.DEATH: "spr_RoninDeath_strip16.png",
        }

        scale = self._scale_override if self._scale_override is not None else self.margins.scale
        for state, file_name in file_mapping.items():
            file_path = os.path.join(base_dir, file_name)
            raw_frames: list[pg.Surface] = []
            # Load directly from the source strip PNG so we never pick up stale
            # pre-sliced *_frames folders (e.g. spr_RoninAttack_strip33_frames was
            # mis-sliced into 33 drifting frames instead of 25 clean 128x96 frames).
            if os.path.exists(file_path):
                try:
                    raw_frames = [pg.image.load(file_path).convert_alpha()]
                except Exception:
                    raw_frames = []
            if not raw_frames:
                raw_frames = AssetManager.get_animation_frames(file_path)
            m = re.search(r"_strip(\d+)\.png$", file_name, re.IGNORECASE)
            if len(raw_frames) == 1:
                sheet = raw_frames[0]
                sw, sh = sheet.get_width(), sheet.get_height()
                n_frames = max(1, int(m.group(1))) if m else 1
                # Validate that strip width divides evenly by n_frames; some Ronin
                # attack strips (e.g. spr_RoninAttack_strip33.png, 3200x96) actually
                # contain 25 frames of 128x96. Slicing by 33 causes 32px/frame drift
                # that cuts the character in half at frame boundaries.
                if sw % n_frames != 0:
                    std_fw = 128 if sh >= 96 else 64
                    if sw % std_fw == 0:
                        n_frames = sw // std_fw
                fw = sw // n_frames
                fh = sh
                if fw > 0 and fh > 0 and n_frames > 1:
                    raw_frames = [
                        sheet.subsurface(pg.Rect(i * fw, 0, fw, fh)).copy()
                        for i in range(n_frames)
                    ]
            # Anchor horizontally on frame 0's standing spine so transition into lunge/slash never snaps backward,
            # while cropping vertically to union bottom so feet stay flush with y_ground.
            non_empty = [f for f in raw_frames if f.get_bounding_rect(min_alpha=10).width > 0]
            if non_empty:
                root_br = non_empty[0].get_bounding_rect(min_alpha=10)
                ubox = root_br.copy()
                for fr in non_empty[1:]:
                    br = fr.get_bounding_rect(min_alpha=10)
                    if br.width > 0 and br.height > 0:
                        ubox = ubox.union(br)
                pad_x = 4
                cx_orig = root_br.centerx
                half_w = max(cx_orig - ubox.left, ubox.right - cx_orig, 12) + pad_x
                crop_y0 = max(0, ubox.top - 4)
                crop_y1 = min(raw_frames[0].get_height(), ubox.bottom)
                crop_h = max(1, crop_y1 - crop_y0)
                src_w = raw_frames[0].get_width()
                x0 = cx_orig - half_w
                x1 = cx_orig + half_w
                if x0 >= 0 and x1 <= src_w:
                    crop_rect = pg.Rect(x0, crop_y0, x1 - x0, crop_h)
                    pad_canvas = None
                else:
                    crop_rect = pg.Rect(0, crop_y0, src_w, crop_h)
                    pad_canvas = (2 * half_w, crop_h, half_w - cx_orig)
            else:
                crop_rect = None
                pad_canvas = None

            scaled_frames = []
            for frame in raw_frames:
                trimmed = frame.subsurface(crop_rect).copy() if crop_rect is not None else frame
                if pad_canvas is not None:
                    cw, ch, bx = pad_canvas
                    padded = pg.Surface((cw, ch), pg.SRCALPHA)
                    padded.blit(trimmed, (bx, 0))
                    trimmed = padded
                w = max(1, int(trimmed.get_width() * scale))
                h = max(1, int(trimmed.get_height() * scale))
                scaled_frames.append(pg.transform.scale(trimmed, (w, h)))
            self.animations[state] = scaled_frames if scaled_frames else [pg.Surface((32, 32))]
            if state == DarkRoninState.IDLE and self.animations[state]:
                idle0 = self.animations[state][0]
                self._body_size = (max(48, int(idle0.get_width() * 0.85)), max(64, idle0.get_height()))

    def set_ground_y(self, ground_y: Optional[int]) -> None:
        """Set ground level height."""
        if ground_y is not None:
            self.y_ground = ground_y
            self.rect.bottom = ground_y

    def set_state(self, new_state: Enum, force: bool = False) -> None:
        """Transition to a new behavioral state."""
        if self._state == DarkRoninState.DEATH and not force:
            return

        current_config = self.STATE_CONFIGS.get(self._state, StateConfig())
        if not current_config.interruptible and not force and self._state != new_state:
            return

        if self._state != new_state:
            self._state = new_state
            self.state = new_state
            self.animation_index = 0.0
            self._hit_targets.clear()
            if new_state == DarkRoninState.DASH_STRIKE:
                self._dash_phase_out_fired = False
                self._dash_phase_in_fired = False
                self._afterimage_accum = 0.0
            super().set_state(new_state, force=force)

    def update(self, dt: float = 16.67, bg_scroll_speed: float = 0.0) -> None:
        """Update DarkRonin AI, movement, and animation frames."""
        current_time = pg.time.get_ticks()
        dt_sec = dt / 1000.0 if dt > 0.5 else dt

        # Adjust position for background scrolling
        if self.rect.x != self._last_rect_x:
            self._pos_x = float(self.rect.x)
        self._pos_x -= float(bg_scroll_speed)
        self.rect.x = int(round(self._pos_x))
        self._last_rect_x = self.rect.x

        # Update active phase-out / transport VFX particles even during death or dialogue
        self._update_phase_vfx(dt_sec, float(bg_scroll_speed))

        # Handle Death State
        if self._state == DarkRoninState.DEATH:
            SquadTokenManager.get_instance().unregister_enemy(id(self))
            self._update_animation()
            return

        # Handle Phase 2 Shadow-Transport sequence (boss vanishes into void rift & warps across arena)
        if self._is_phase_transporting:
            self._update_phase_transport(dt_sec)
            return

        # Freeze AI during pre-fight boss encounter dialogue
        if getattr(self, "ai_frozen", False):
            # Walk onto screen if spawned off-screen right so the player can see Kaelen during dialogue
            surf = pg.display.get_surface()
            screen_w = surf.get_width() if surf else 1280
            if self.rect.centerx > screen_w - 220:
                self._direction = -1
                self.facing_left = True
                self.set_state(DarkRoninState.CHASE)
                self._pos_x -= max(3.5, self.move_speed)
                self.rect.x = int(round(self._pos_x))
            else:
                self.set_state(DarkRoninState.IDLE)
            self._update_animation()
            return

        # AI Behavior with Perception and Utility Engine
        target_vx = 0.0
        player_sprite = getattr(self._player, "sprite", self._player)
        if player_sprite and hasattr(player_sprite, "rect"):
            facing_left = (self._direction == -1)
            self.facing_left = facing_left
            alert = self.perception.update(dt_sec, self.rect, facing_left, player_sprite)

            if alert == AlertLevel.UNAWARE:
                self.set_state(DarkRoninState.IDLE)
            else:
                dist_x = player_sprite.rect.centerx - self.rect.centerx
                abs_dist = abs(dist_x)

                if abs_dist > 10 and self._state in (DarkRoninState.IDLE, DarkRoninState.CHASE):
                    self._direction = 1 if dist_x > 0 else -1
                    self.facing_left = (self._direction == -1)

                has_token = SquadTokenManager.get_instance().request_attack_token(id(self))
                melee_reach = 115 if getattr(self, "is_boss", False) else 72
                can_attack = (abs_dist <= melee_reach)

                action = self.utility_engine.evaluate_action(
                    enemy_rect=self.rect,
                    player=player_sprite,
                    can_attack=can_attack,
                    has_attack_token=has_token,
                    dt_sec=dt_sec,
                )

                # Melee attack takes precedence when in range
                if (action in (TacticalAction.PUNISH_WHIFF, TacticalAction.ATTACK) or abs_dist <= melee_reach) and self._state in (DarkRoninState.IDLE, DarkRoninState.CHASE):
                    self.set_state(DarkRoninState.ATTACK)
                elif (
                    (action == TacticalAction.DASH_EVADE or (melee_reach + 35) <= abs_dist <= 340)
                    and current_time - self.last_dash_time >= self.dash_cooldown_ms
                    and self._state in (DarkRoninState.IDLE, DarkRoninState.CHASE)
                ):
                    self.last_dash_time = current_time
                    self.set_state(DarkRoninState.DASH_STRIKE)
                elif action == TacticalAction.RETRACT_SPACING and self._state in (DarkRoninState.IDLE, DarkRoninState.CHASE):
                    # Turn and retreat cleanly rather than moonwalking backward
                    retreat_dir = -1 if dist_x > 0 else 1
                    self._direction = retreat_dir
                    self.facing_left = (self._direction == -1)
                    target_vx = retreat_dir * self.move_speed * 0.85
                    self.set_state(DarkRoninState.CHASE)
                elif action == TacticalAction.CHASE and self._state in (DarkRoninState.IDLE, DarkRoninState.CHASE):
                    self.set_state(DarkRoninState.CHASE)
                    target_x = SquadCoordinator.get_instance().get_target_offset_x(
                        id(self), player_sprite.rect, getattr(player_sprite, "facing_left", False), 65.0
                    )
                    dx = target_x - self.rect.centerx
                    if abs(dx) > 8:
                        move_dir = 1 if dx > 0 else -1
                        self._direction = move_dir
                        self.facing_left = (self._direction == -1)
                        target_vx = move_dir * self.move_speed

        # Release token if not in an attacking state
        if self._state not in (DarkRoninState.ATTACK, DarkRoninState.DASH_STRIKE):
            SquadTokenManager.get_instance().release_attack_token(id(self))

        # Handle Dash / Chase Movement (stop residual slide on state change or reversal to prevent moonwalking)
        if self._state == DarkRoninState.DASH_STRIKE:
            idx = int(self.animation_index)
            # Trigger departure rift at frame 4 (phase-out start) and arrival rift at frame 7 (reform)
            if idx >= 4 and not self._dash_phase_out_fired:
                self._dash_phase_out_fired = True
                self._spawn_phase_rift(self.rect.centerx, self.rect.centery, color=(255, 210, 90), is_arrival=False)
                self._spawn_transport_sparks(self.rect.centerx, self.rect.centery, count=14, direction=self._direction)
            if idx >= 7 and not self._dash_phase_in_fired:
                self._dash_phase_in_fired = True
                self._spawn_phase_rift(self.rect.centerx, self.rect.centery, color=(190, 120, 255), is_arrival=True)
                self._spawn_transport_sparks(self.rect.centerx, self.rect.centery, count=16, direction=-self._direction)

            # High-speed burst while phased out (frames 4-6), leaving golden-violet ghost afterimages & sparks
            dash_velocity = 12.5 if 4 <= idx <= 6 else 7.0
            self._vel_x = self._direction * dash_velocity
            self._pos_x += self._vel_x * dt_sec * 60.0

            if 3 <= idx <= 7:
                self._afterimage_accum += dt_sec
                if self._afterimage_accum >= 0.032:
                    self._afterimage_accum = 0.0
                    self._record_afterimage(tint=(240, 185, 75) if idx <= 5 else (175, 110, 255))
                    self._spawn_transport_sparks(self.rect.centerx, self.rect.centery, count=3, direction=self._direction)
        elif self._state == DarkRoninState.CHASE:
            if target_vx * self._vel_x < 0.0:
                self._vel_x = 0.0
            accel = min(1.0, dt_sec * 14.0)
            self._vel_x += (target_vx - self._vel_x) * accel
            if abs(self._vel_x) < 0.08 and target_vx == 0.0:
                self._vel_x = 0.0
            elif abs(self._vel_x) > 0.15:
                self._direction = 1 if self._vel_x > 0.0 else -1
                self.facing_left = (self._direction == -1)
            self._pos_x += self._vel_x * dt_sec * 60.0
        else:
            self._vel_x = 0.0
        self.rect.x = int(round(self._pos_x))

        # Keep boss inside arena bounds once engaged
        if getattr(self, "is_boss", False):
            surf = pg.display.get_surface()
            screen_w = surf.get_width() if surf else 1280
            if self.rect.left < 20:
                self.rect.left = 20
                self._pos_x = float(self.rect.x)
            if self.rect.right > screen_w - 20 and not getattr(self, "ai_frozen", False):
                self.rect.right = min(self.rect.right, screen_w + 180)
                self._pos_x = float(self.rect.x)
        self._last_rect_x = self.rect.x

        self._update_animation()

    def _update_animation(self) -> None:
        """Advance animation frame and update sprite image."""
        frames = self.animations.get(self._state, self.animations[DarkRoninState.IDLE])
        config = self.STATE_CONFIGS.get(self._state, StateConfig())

        self.animation_index += config.animation_speed
        if self.animation_index >= len(frames):
            if config.loops:
                self.animation_index = 0.0
            else:
                self.animation_index = float(len(frames) - 1)
                if config.next_state:
                    self.set_state(config.next_state, force=True)

        idx = int(self.animation_index) % len(frames)
        raw_image = frames[idx]

        # Ronin source strips natively face right (+1), so mirror when facing left (-1)
        if self._direction == -1:
            self.image = pg.transform.flip(raw_image, True, False)
        else:
            self.image = raw_image

    def take_damage(self, amount: float, knockback: object = None) -> bool:
        """Apply damage unless dead."""
        if self._is_invincible or self._state == DarkRoninState.DEATH:
            return False

        self._health = max(0.0, self._health - amount)
        if self._health <= 0.0:
            self.set_state(DarkRoninState.DEATH, force=True)
            if self._audio_manager:
                try:
                    self._audio_manager.play_sound("skeleton_death")
                except Exception:
                    pass
        else:
            # Trigger Phase 2 Shadow-Transport at <= 50% HP for the Final Boss!
            if (
                getattr(self, "is_boss", False)
                and not self._phase2_triggered
                and self._health <= self._max_health * 0.50
            ):
                self._start_phase2_transport()
            else:
                self.set_state(DarkRoninState.HURT, force=True)
            if self._audio_manager:
                try:
                    self._audio_manager.play_sound("skeleton_hurt")
                except Exception:
                    pass
        return True

    def _start_phase2_transport(self) -> None:
        """Initiate dramatic Phase 2 shadow-phase disappearance & transport across the arena."""
        self._phase2_triggered = True
        self._is_phase_transporting = True
        self._is_invincible = True
        self._phase_transport_timer = 0.85  # seconds spent in void-transport
        self._phase_transport_origin = (float(self.rect.centerx), float(self.rect.centery))

        surf = pg.display.get_surface()
        screen_w = surf.get_width() if surf else 1280
        # Transport to the opposite side of the arena from current position
        self._phase_transport_target_x = 220.0 if self.rect.centerx > screen_w * 0.5 else float(screen_w - 220)

        # Enrage buffs for Phase 2
        self.move_speed = max(self.move_speed * 1.18, 4.8)
        self.dash_cooldown_ms = max(1800, int(self.dash_cooldown_ms * 0.7))

        # Departure rift + burst of void/star-fire sparks + ghost silhouette
        self._record_afterimage(tint=(255, 200, 80), duration=0.45)
        self._spawn_phase_rift(self.rect.centerx, self.rect.centery, color=(255, 195, 70), is_arrival=False, max_radius=95.0)
        self._spawn_transport_sparks(self.rect.centerx, self.rect.centery, count=26, direction=self._direction)
        if self._audio_manager:
            try:
                self._audio_manager.play_sound("dash")
            except Exception:
                pass

    def _update_phase_transport(self, dt_sec: float) -> None:
        """Animate the void-energy transport streak while Commander Kaelen is vanished between phases."""
        self._phase_transport_timer -= dt_sec
        progress = max(0.0, min(1.0, 1.0 - (self._phase_transport_timer / 0.85)))
        ox, oy = self._phase_transport_origin
        cur_x = ox + (self._phase_transport_target_x - ox) * progress

        # Continuously emit transport energy trail along the travel path
        self._spawn_transport_sparks(cur_x, oy, count=4, direction=1 if self._phase_transport_target_x > ox else -1)

        # Telegraph arrival rift slightly before re-materializing
        if progress >= 0.72 and not any(r.get("is_phase2_arrival") for r in self._phase_rifts):
            self._spawn_phase_rift(
                self._phase_transport_target_x,
                oy,
                color=(200, 110, 255),
                is_arrival=True,
                max_radius=105.0,
                extra={"is_phase2_arrival": True},
            )

        if self._phase_transport_timer <= 0.0:
            self._is_phase_transporting = False
            self._is_invincible = False
            self.rect.centerx = int(round(self._phase_transport_target_x))
            self.rect.bottom = self.y_ground
            self._pos_x = float(self.rect.x)
            self._last_rect_x = self.rect.x
            # Face player upon re-materializing
            player_sprite = getattr(self._player, "sprite", self._player)
            if player_sprite and hasattr(player_sprite, "rect"):
                self._direction = 1 if player_sprite.rect.centerx > self.rect.centerx else -1
                self.facing_left = (self._direction == -1)
            self._spawn_transport_sparks(self.rect.centerx, self.rect.centery, count=24, direction=self._direction)
            self.set_state(DarkRoninState.IDLE, force=True)
            self._update_animation()

    def _record_afterimage(self, tint: tuple[int, int, int] = (230, 175, 70), duration: float = 0.28) -> None:
        """Store a tinted ghost silhouette at the current render position."""
        if self.image is None:
            return
        ghost = self.image.copy()
        tint_surf = pg.Surface(ghost.get_size(), pg.SRCALPHA)
        tint_surf.fill((*tint, 255))
        ghost.blit(tint_surf, (0, 0), special_flags=pg.BLEND_RGBA_MULT)
        rx, ry = self.get_render_position()
        self._afterimages.append({
            "surf": ghost,
            "x": float(rx),
            "y": float(ry),
            "timer": duration,
            "max_timer": duration,
        })

    def _spawn_phase_rift(
        self,
        cx: float,
        cy: float,
        color: tuple[int, int, int] = (240, 185, 75),
        is_arrival: bool = False,
        max_radius: float = 68.0,
        extra: Optional[dict] = None,
    ) -> None:
        """Spawn an expanding/collapsing vertical shadow-portal rift at (cx, cy)."""
        rift = {
            "x": float(cx),
            "y": float(cy),
            "color": color,
            "is_arrival": is_arrival,
            "timer": 0.36,
            "max_timer": 0.36,
            "max_radius": max_radius,
        }
        if extra:
            rift.update(extra)
        self._phase_rifts.append(rift)

    def _spawn_transport_sparks(self, cx: float, cy: float, count: int = 8, direction: int = -1) -> None:
        """Spawn streaking star-fire / void-shadow particles during phase-out and transport."""
        palette = [(255, 225, 110), (240, 170, 55), (180, 105, 255), (110, 60, 190)]
        for _ in range(count):
            vx = -direction * random.uniform(70.0, 220.0) + random.uniform(-45.0, 45.0)
            vy = random.uniform(-90.0, 90.0)
            life = random.uniform(0.18, 0.42)
            self._transport_sparks.append({
                "x": float(cx) + random.uniform(-24.0, 24.0),
                "y": float(cy) + random.uniform(-55.0, 45.0),
                "vx": vx,
                "vy": vy,
                "length": random.uniform(12.0, 32.0),
                "color": random.choice(palette),
                "timer": life,
                "max_timer": life,
            })

    def _update_phase_vfx(self, dt_sec: float, bg_scroll_speed: float = 0.0) -> None:
        """Advance timers and positions for afterimages, phase rifts, and transport sparks."""
        for g in self._afterimages:
            g["timer"] -= dt_sec
            g["x"] -= bg_scroll_speed
        self._afterimages = [g for g in self._afterimages if g["timer"] > 0.0]

        for r in self._phase_rifts:
            r["timer"] -= dt_sec
            r["x"] -= bg_scroll_speed
        self._phase_rifts = [r for r in self._phase_rifts if r["timer"] > 0.0]

        for s in self._transport_sparks:
            s["timer"] -= dt_sec
            s["x"] += s["vx"] * dt_sec - bg_scroll_speed
            s["y"] += s["vy"] * dt_sec
        self._transport_sparks = [s for s in self._transport_sparks if s["timer"] > 0.0]

    def _draw_phase_vfx(self, surface: pg.Surface) -> None:
        """Render shadow afterimages, void phase rifts, and transport energy streaks."""
        # 1. Fading ghost afterimages
        for g in self._afterimages:
            alpha = int(175 * max(0.0, g["timer"] / g["max_timer"]))
            if alpha > 4:
                g["surf"].set_alpha(alpha)
                surface.blit(g["surf"], (int(g["x"]), int(g["y"])))

        # 2. Vertical void-portal rifts (departure / arrival rings)
        for r in self._phase_rifts:
            t = 1.0 - max(0.0, r["timer"] / r["max_timer"])
            alpha = int(225 * (1.0 - t))
            if alpha <= 4:
                continue
            rad = int(r["max_radius"] * (1.0 - 0.55 * t) if r["is_arrival"] else r["max_radius"] * (0.35 + 0.85 * t))
            rw = max(8, int(rad * 0.52))
            rh = max(16, int(rad * 1.45))
            rift_surf = pg.Surface((rw * 2 + 12, rh * 2 + 12), pg.SRCALPHA)
            cx, cy = rw + 6, rh + 6
            # Outer soft void glow + crisp inner star-fire ring
            pg.draw.ellipse(rift_surf, (25, 10, 45, int(alpha * 0.55)), (6, 6, rw * 2, rh * 2))
            pg.draw.ellipse(rift_surf, (*r["color"], alpha), (6, 6, rw * 2, rh * 2), 3)
            inner_w = max(4, int(rw * 0.55))
            inner_h = max(8, int(rh * 0.65))
            pg.draw.ellipse(
                rift_surf,
                (255, 245, 200, int(alpha * 0.85)),
                (cx - inner_w, cy - inner_h, inner_w * 2, inner_h * 2),
                2,
            )
            surface.blit(rift_surf, (int(r["x"] - cx), int(r["y"] - cy)))

        # 3. Horizontal streaking void-transport sparks
        for s in self._transport_sparks:
            frac = max(0.0, s["timer"] / s["max_timer"])
            alpha = int(240 * frac)
            if alpha <= 4:
                continue
            x0, y0 = int(s["x"]), int(s["y"])
            dx = int(math.copysign(s["length"] * frac, s["vx"] if s["vx"] != 0 else 1.0))
            line_w = abs(dx) + 6
            streak = pg.Surface((line_w, 8), pg.SRCALPHA)
            sy = 4
            sx0 = 3 if dx >= 0 else line_w - 3
            sx1 = sx0 + dx
            pg.draw.line(streak, (*s["color"], alpha), (sx0, sy), (sx1, sy), 3)
            pg.draw.circle(streak, (255, 250, 225, alpha), (sx1, sy), 2)
            surface.blit(streak, (min(x0, x0 + dx) - 3, y0 - 4))

    def get_attack_hitbox(self) -> Optional[pg.Rect]:
        """Get current attack hitbox if on an active hit frame."""
        config = None
        if self._state == DarkRoninState.ATTACK:
            config = self.SLASH_CONFIG
        elif self._state == DarkRoninState.DASH_STRIKE:
            config = self.DASH_STRIKE_CONFIG

        if not config:
            return None

        idx = int(self.animation_index)
        if idx in config.hit_frames:
            hitbox_w = 155 if getattr(self, "is_boss", False) else 90
            hitbox_h = 112 if getattr(self, "is_boss", False) else 68
            if self._direction == -1:
                hx = self.rect.left - hitbox_w + 22
            else:
                hx = self.rect.right - 22
            hy = self.rect.centery - hitbox_h // 2
            return pg.Rect(hx, hy, hitbox_w, hitbox_h)
        return None

    def should_deal_damage(self) -> bool:
        """Return True if on an active attack hit frame."""
        return self.get_attack_hitbox() is not None

    def register_hit(self, target_id: int) -> bool:
        """Register hit target ID to prevent multi-hitting in a single swing cycle."""
        if target_id in self._hit_targets:
            return False
        self._hit_targets.add(target_id)
        return True

    def get_current_attack_damage(self) -> float:
        """Return current attack damage."""
        if self._state == DarkRoninState.DASH_STRIKE:
            return self.DASH_STRIKE_CONFIG.base_damage
        return self.SLASH_CONFIG.base_damage

    def get_current_attack_knockback(self) -> float:
        """Return current attack knockback."""
        if self._state == DarkRoninState.DASH_STRIKE:
            return self.DASH_STRIKE_CONFIG.knockback_force
        return self.SLASH_CONFIG.knockback_force

    def get_render_position(self) -> tuple[int, int]:
        """Anchor sprite midbottom directly onto self.rect.midbottom across all strip sizes."""
        img = self.image
        if img is None:
            return self.rect.topleft
        return (
            self.rect.centerx - img.get_width() // 2,
            self.rect.bottom - img.get_height(),
        )

    def draw(self, surface: pg.Surface) -> None:
        """Render DarkRonin along with phase-out afterimages, rifts, and transport streaks."""
        # Always draw phase-out / transport VFX behind & around the boss
        self._draw_phase_vfx(surface)

        # While vanished in Phase 2 shadow-transport, draw only the transport energy core
        if self._is_phase_transporting:
            progress = max(0.0, min(1.0, 1.0 - (self._phase_transport_timer / 0.85)))
            ox, oy = self._phase_transport_origin
            cur_x = ox + (self._phase_transport_target_x - ox) * progress
            orb = pg.Surface((96, 64), pg.SRCALPHA)
            pg.draw.ellipse(orb, (140, 70, 235, 110), (4, 12, 88, 40))
            pg.draw.ellipse(orb, (255, 215, 100, 190), (20, 20, 56, 24))
            pg.draw.ellipse(orb, (255, 250, 235, 240), (34, 25, 28, 14))
            surface.blit(orb, (int(cur_x - 48), int(oy - 32)))
            return

        # Smooth alpha dissolve during DASH_STRIKE phase-out/re-materialization frames
        img = self.image
        if self._state == DarkRoninState.DASH_STRIKE and img is not None:
            idx = int(self.animation_index)
            phase_alphas = {4: 200, 5: 120, 6: 120, 7: 195}
            alpha = phase_alphas.get(idx)
            if alpha is not None:
                img = img.copy()
                img.set_alpha(alpha)

        surface.blit(img, self.get_render_position())
        if not getattr(self, "is_boss", False) and self._health < self._max_health and self._state != DarkRoninState.DEATH:
            self._draw_health_bar(surface)

    def _draw_health_bar(self, surface: pg.Surface) -> None:
        """Render the health bar above DarkRonin when spawned as a minion."""
        bar_width: int = 50
        bar_height: int = 6
        bar_x: int = self.rect.centerx - bar_width // 2
        bar_y: int = self.rect.top - 12
        pg.draw.rect(surface, (40, 40, 40), (bar_x, bar_y, bar_width, bar_height))
        ratio = self._health / self._max_health
        pg.draw.rect(surface, (220, 20, 20), (bar_x, bar_y, int(bar_width * ratio), bar_height))
