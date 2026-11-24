"""
Green Monster ("The Gatekeeper") boss module.

A winged elite that hovers a short distance off the ground, alternating
between diving melee ground-slams when the player closes in and lobbed
toxic globs when kept at range.
"""

from __future__ import annotations

from src.game.audio.entity_audio_mixin import EntityAudioMixin
from .base_enemy import BaseEnemy

import math
import random
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Final, Optional

import pygame as pg

from v3x_zulfiqar_gideon import AssetManager, Actor, AttackConfig
from .hitbox_registry import HitboxRegistry
from ..services import ConfigClient
from src.game.ai import PerceptionSystem, AlertLevel, SquadTokenManager, UtilityCombatEngine, TacticalAction

if TYPE_CHECKING:
    from src.game.entities.player import Player


class ToxicGlob(pg.sprite.Sprite):
    """Animated Emerald Ectoplasm plasma-bolt fired straight from the Gatekeeper's
    outstretched tentacle-arm. Flies in a fast straight line with writhing ectoplasm
    tendrils and trailing toxic droplets (no gravity curve)."""

    def __init__(
        self,
        x: int,
        y: int,
        direction: int,
        scale: float,
        damage: float,
        knockback: float,
        player: Player,
    ) -> None:
        super().__init__()
        self._player = player
        self.direction = direction
        self.speed = 9.5
        self.damage = damage
        self.knockback = knockback
        self._scale = max(1.0, float(scale))
        self._elapsed: float = 0.0
        self._pos_x: float = float(x)
        self._pos_y: float = float(y)

        # Compact hitbox centered on the glowing ectoplasm head
        self._radius = max(14, int(11 * self._scale))
        self._tail_len = max(46, int(34 * self._scale))
        self._trail_droplets: list[dict] = []
        self._droplet_accum: float = 0.0

        self.image = pg.Surface((self._radius * 2, self._radius * 2), pg.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))

        self.is_projectile = True
        self.is_boss = False

    def update(self, dt: Optional[float] = None, scroll_speed: int = 0) -> None:
        dt_sec = (dt / 1000.0 if dt > 0.5 else dt) if dt is not None else (1.0 / 60.0)
        self._elapsed += dt_sec
        step = self.speed * (dt_sec * 60.0)

        # Straight linear flight (zero gravity curve)
        self._pos_x += self.direction * step - float(scroll_speed)
        self.rect.centerx = int(round(self._pos_x))
        self.rect.centery = int(round(self._pos_y))

        # Emit glowing ectoplasm droplets trailing behind the bolt
        self._droplet_accum += dt_sec
        if self._droplet_accum >= 0.025:
            self._droplet_accum = 0.0
            self._trail_droplets.append({
                "x": self._pos_x - self.direction * random.uniform(6.0, self._radius * 1.1),
                "y": self._pos_y + random.uniform(-self._radius * 0.55, self._radius * 0.55),
                "vx": -self.direction * random.uniform(18.0, 55.0),
                "vy": random.uniform(-22.0, 28.0),
                "r": random.uniform(3.0, max(4.5, self._radius * 0.28)),
                "life": random.uniform(0.18, 0.34),
                "max_life": 0.34,
            })

        for d in self._trail_droplets:
            d["life"] -= dt_sec
            d["x"] += d["vx"] * dt_sec - float(scroll_speed)
            d["y"] += d["vy"] * dt_sec
        self._trail_droplets = [d for d in self._trail_droplets if d["life"] > 0.0]

        if self.rect.right < -200 or self.rect.left > 2200:
            self.kill()
            return

        if self.rect.colliderect(self._player.rect):
            if not self._player.is_invincible:
                damage_applied = self._player.take_damage(self.damage)
                if damage_applied and self.knockback > 0:
                    apply_kb = getattr(self._player, "apply_knockback", None)
                    if apply_kb:
                        kb_dir = -1 if self.rect.centerx > self._player.rect.centerx else 1
                        apply_kb(self.knockback * kb_dir)
                try:
                    from src.game.effects.vfx_manager import VisualEffectManager
                    VisualEffectManager.spawn_hit_vfx(
                        self.rect.centerx, self.rect.centery, vfx_type="toxic_splatter"
                    )
                except Exception:
                    pass
            self.kill()

    def draw(self, surface: pg.Surface) -> None:
        cx, cy = self.rect.centerx, self.rect.centery
        r = self._radius
        t = self._elapsed
        d = self.direction

        # 1. Trailing glowing ectoplasm droplets
        for drop in self._trail_droplets:
            frac = max(0.0, drop["life"] / drop["max_life"])
            dr = max(2, int(drop["r"] * frac))
            alpha = int(210 * frac)
            ds = pg.Surface((dr * 2 + 4, dr * 2 + 4), pg.SRCALPHA)
            pg.draw.circle(ds, (45, 195, 70, int(alpha * 0.65)), (dr + 2, dr + 2), dr + 1)
            pg.draw.circle(ds, (165, 255, 120, alpha), (dr + 2, dr + 2), max(1, int(dr * 0.65)))
            surface.blit(ds, (int(drop["x"] - dr - 2), int(drop["y"] - dr - 2)))

        # 2. Writhing emerald ectoplasm plasma tail + pulsing core
        canvas_w = self._tail_len + r * 3 + 16
        canvas_h = r * 4 + 16
        surf = pg.Surface((canvas_w, canvas_h), pg.SRCALPHA)
        # Head sits near the front edge of the canvas based on flight direction
        head_x = (canvas_w - r - 8) if d > 0 else (r + 8)
        head_y = canvas_h // 2

        # Draw 3 sinusoidal ectoplasm tendrils streaming behind the orb
        for strand_idx, (phase, amp, thickness, col) in enumerate((
            (0.0, r * 0.42, max(4, int(r * 0.36)), (35, 175, 65, 150)),
            (2.1, r * 0.30, max(3, int(r * 0.26)), (95, 235, 85, 195)),
            (4.2, r * 0.18, max(2, int(r * 0.16)), (195, 255, 145, 225)),
        )):
            pts = []
            steps = 8
            for i in range(steps + 1):
                frac = i / steps
                px = head_x - d * (frac * self._tail_len)
                wobble = math.sin(t * 22.0 - frac * 5.5 + phase) * amp * (0.25 + 0.75 * frac)
                py = head_y + wobble
                pts.append((int(px), int(py)))
            for i in range(len(pts) - 1):
                seg_w = max(1, int(thickness * (1.0 - (i / len(pts)) * 0.78)))
                pg.draw.line(surf, col, pts[i], pts[i + 1], seg_w)

        # Pulsing ectoplasm orb layers (outer abyssal haze -> emerald plasma -> toxic lime -> hot nucleus)
        pulse = 1.0 + 0.12 * math.sin(t * 26.0)
        r_outer = int(r * 1.38 * pulse)
        r_mid = int(r * 0.98 * pulse)
        r_inner = int(r * 0.62)
        r_core = max(3, int(r * 0.32))

        pg.draw.circle(surf, (25, 130, 55, 85), (head_x, head_y), r_outer)
        pg.draw.circle(surf, (55, 205, 65, 175), (head_x, head_y), r_mid)
        pg.draw.circle(surf, (135, 255, 95, 235), (head_x, head_y), r_inner)
        pg.draw.circle(surf, (235, 255, 210, 255), (head_x, head_y), r_core)

        # Orbiting goo bubbles around the ectoplasm head
        for b_idx in range(3):
            ang = t * 14.0 + b_idx * 2.094
            bx = int(head_x + math.cos(ang) * r * 0.78)
            by = int(head_y + math.sin(ang) * r * 0.62)
            br = max(2, int(r * 0.20))
            pg.draw.circle(surf, (175, 255, 130, 220), (bx, by), br)

        surface.blit(surf, (cx - head_x, cy - head_y))


class MagicShotProjectile(pg.sprite.Sprite):
    """An animated magic projectile fired during Gatekeeper's Enraged phase."""

    def __init__(
        self,
        x: int,
        y: int,
        direction: int,
        scale: float,
        damage: float,
        knockback: float,
        player: Player,
    ) -> None:
        super().__init__()
        self._player = player
        self.direction = direction
        self.speed = 8.5
        self.damage = damage
        self.knockback = knockback

        raw_frames = AssetManager.get_animation_frames("assets/graphics/Magic shots/1")
        if not raw_frames:
            surf = pg.Surface((28, 28), pg.SRCALPHA)
            pg.draw.circle(surf, (200, 50, 255), (14, 14), 12)
            raw_frames = [surf]

        self.frames: list[pg.Surface] = []
        for frame in raw_frames:
            w = int(frame.get_width() * scale * 1.5)
            h = int(frame.get_height() * scale * 1.5)
            self.frames.append(pg.transform.scale(frame, (w, h)))

        self.frame_index: float = 0.0
        self.image = self.frames[0]
        self.rect = self.image.get_rect(center=(x, y))
        self.is_projectile = True
        self.is_boss = False

    def update(self, dt: Optional[float] = None, scroll_speed: int = 0) -> None:
        delta = dt if dt is not None else 0.016
        self.rect.x -= scroll_speed
        self.rect.x += int(self.direction * self.speed)

        self.frame_index = (self.frame_index + delta * 25) % len(self.frames)
        self.image = self.frames[int(self.frame_index)]

        if self.rect.right < -200 or self.rect.left > 2200:
            self.kill()
            return

        if self.rect.colliderect(self._player.rect):
            if not self._player.is_invincible:
                damage_applied = self._player.take_damage(self.damage)
                if damage_applied and self.knockback > 0:
                    apply_kb = getattr(self._player, "apply_knockback", None)
                    if apply_kb:
                        kb_dir = -1 if self.rect.centerx > self._player.rect.centerx else 1
                        apply_kb(self.knockback * kb_dir)
                try:
                    from src.game.effects.vfx_manager import VisualEffectManager
                    VisualEffectManager.spawn_hit_vfx(self.rect.centerx, self.rect.centery, entity=self._player)
                except Exception:
                    pass
            self.kill()

    def draw(self, surface: pg.Surface) -> None:
        surface.blit(self.image, self.rect)


class GatekeeperState(Enum):
    """Enumeration of all possible Gatekeeper behavioral states."""

    DEATH = 0
    HURT = 10
    ATTACK = 20
    CHASE = 30
    IDLE = 40


@dataclass(slots=True)
class StateConfig:
    animation_speed: float = 0.12
    loops: bool = True
    next_state: Optional[GatekeeperState] = None
    interruptible: bool = True


class GreenMonster(BaseEnemy):
    """
    The Gatekeeper -- a hovering elite enemy. Keeps just out of easy reach,
    diving down for a ground-slam when the player gets close and lobbing
    toxic globs when kept at a distance.
    """

    # Ground-slam impact window: frames 2-4 of the 7-frame "1atk" clip.
    ATTACK_CONFIG: Final[AttackConfig] = AttackConfig(
        hit_frames=frozenset({2, 3, 4}),
        base_damage=3.0,
        knockback_force=9.0,
        max_hits_per_target=1,
    )

    STATE_CONFIGS: Final[dict[Enum, StateConfig]] = {
        GatekeeperState.IDLE: StateConfig(0.1),
        GatekeeperState.CHASE: StateConfig(0.15),
        GatekeeperState.ATTACK: StateConfig(0.15, loops=False, next_state=GatekeeperState.IDLE, interruptible=False),
        GatekeeperState.HURT: StateConfig(0.15, loops=False, next_state=GatekeeperState.IDLE, interruptible=False),
        GatekeeperState.DEATH: StateConfig(0.12, loops=False, interruptible=False),
    }

    # Frame (within the 9-frame "2atk" clip) at which the ectoplasm bolt is released
    # right as the tentacle-arm reaches full forward extension (f03).
    _SPIT_RELEASE_FRAME: Final[int] = 3

    hit_vfx_type: str = "toxic_splatter"

    def __init__(
        self,
        x: int,
        y: int,
        player: Player,
        tier: str = "elite",
        sprite_root: Optional[str] = None,
        behaviour_map: Optional[dict[str, str]] = None,
        custom_scale: Optional[float] = None,
        custom_health: Optional[float] = None,
        audio_manager=None,
    ) -> None:
        super().__init__(x, y)

        self._player: Player = player
        self.state_configs = self.STATE_CONFIGS
        self.tier = tier
        self.is_enraged: bool = False
        self._base_path: str = (sprite_root or "assets/graphics/green_monster").rstrip("/")

        # AI tuning -- overridden below by enemy_green_monster config if available
        self._speed: float = 2.2
        self._melee_range: int = 110
        self._ranged_range: int = 420
        self._detection_range: int = 900
        self._vertical_tolerance: int = 260
        self._attack_cooldown_min: float = 1.0
        self._attack_cooldown_max: float = 1.8
        self._chase_cooldown_duration: float = 1.0
        self._attack_hitbox_width: int = 90
        self._attack_hitbox_height: int = 70

        self.perception = PerceptionSystem(
            vision_range=float(self._detection_range),
            hearing_range=900.0,
            reaction_delay_sec=0.14,
        )
        self.utility_engine = UtilityCombatEngine(
            has_dash_evasion=True,
            has_block_anim=False,
            preferred_spacing=200.0,
        )
        SquadTokenManager.get_instance().register_enemy(id(self), self.tier)

        # Mana and charging system properties (mirrors Fire Wizard rules)
        self._max_mana: float = 100.0
        self._spell_mana_cost: float = 35.0
        self._stagnant_duration: float = 3.0
        self._teleport_dist_min: int = 380
        self._teleport_dist_max: int = 450
        self._mana_recharge_rate: float = 50.0
        self._chase_delay_duration: float = 0.8
        self._spidey_sense: float = 0.0

        # Ectoplasm muzzle-launch burst & spray VFX particles
        self._muzzle_bursts: list[dict] = []
        self._muzzle_sparks: list[dict] = []

        # Cooldowns and states
        self._chase_cooldown: float = 0.0
        self._attack_cooldown: float = 0.0
        self._attack_kind: str = "slam"  # "slam" (melee) or "spit" (ranged)
        self._has_spawned_attack_effect: bool = False

        self._mana: float = self._max_mana
        self._is_recharging: bool = False
        self._is_stagnant: bool = False
        self._stagnant_timer: float = 0.0
        self._chase_delay_timer: float = 0.0
        self._chase_delay_active: bool = False
        self._teleport_flash_timer: float = 0.0
        self._teleport_after_hurt: bool = False

        # Load margins/scale via the shared "boss:<folder>" registry convention
        key = f"boss:{self._base_path.rsplit('/', 1)[-1].lower()}"
        margins = HitboxRegistry.get_margins(key)
        registry_scale = None
        try:
            if HitboxRegistry.has_custom_margins(key):
                registry_scale = margins.scale
        except Exception:
            pass

        self.scale = registry_scale if registry_scale is not None else (
            custom_scale if custom_scale is not None else margins.scale
        )

        # 1. Load animations (Walk instead of fly)
        self.animations[GatekeeperState.IDLE] = self._load_scaled(f"{self._base_path}/idle")
        self.animations[GatekeeperState.CHASE] = self._load_scaled(f"{self._base_path}/walk")
        self._attack_slam_frames = self._load_scaled(f"{self._base_path}/1atk")
        self._attack_spit_frames = self._load_scaled(f"{self._base_path}/2atk")
        self.animations[GatekeeperState.ATTACK] = self._attack_slam_frames
        self.animations[GatekeeperState.HURT] = self._load_scaled(f"{self._base_path}/hurt")
        self.animations[GatekeeperState.DEATH] = self._load_scaled(f"{self._base_path}/death")

        # 2. Tier-based stat scaling (mirrors Skeleton/FireWizard conventions)
        damage_scale = 1.0
        knockback_scale = 1.0
        if self.tier == "boss":
            self._max_health = custom_health if custom_health is not None else 100.0
            damage_scale, knockback_scale = 2.2, 1.6
        elif self.tier == "elite":
            self._max_health = custom_health if custom_health is not None else 60.0
            damage_scale, knockback_scale = 1.4, 1.2
        else:
            self._max_health = custom_health if custom_health is not None else 35.0

        try:
            config = ConfigClient.fetch_config("enemy_green_monster")
            if config:
                self.apply_config(config)
                if custom_health is None:
                    self._max_health = float(config.get("max_health", self._max_health))
                self._speed = float(config.get("speed", self._speed))
                damage_scale = float(config.get("damage_scale", damage_scale))
                knockback_scale = float(config.get("knockback_scale", knockback_scale))
                self._detection_range = int(config.get("detection_range", self._detection_range))
                self._melee_range = int(config.get("attack_range", self._melee_range))
                self._attack_hitbox_width = int(config.get("attack_hitbox_width", self._attack_hitbox_width))
                self._attack_hitbox_height = int(config.get("attack_hitbox_height", self._attack_hitbox_height))
        except Exception as e:
            print(f"[WARNING] Error loading green_monster config: {e}")

        self._health: float = self._max_health

        self.current_attack_config = AttackConfig(
            hit_frames=self.ATTACK_CONFIG.hit_frames,
            base_damage=self.ATTACK_CONFIG.base_damage * damage_scale,
            knockback_force=self.ATTACK_CONFIG.knockback_force * knockback_scale,
        )

        # Initial state/frame
        self.set_state(GatekeeperState.IDLE)
        if self.state in self.animations:
            self.image = self.animations[self.state][0]

        # Audio trigger system (non-fatal; gracefully skipped if audio_manager is None)
        self._init_entity_audio_config(audio_manager, "green_monster")
        self.rect: pg.Rect = self.image.get_rect(midbottom=(x, y))

        # Hitbox adjustment from margins registry
        self.adjust_hitbox_sides(left=margins.left, right=margins.right, top=margins.top, bottom=margins.bottom)

        # Ground positioning and gravity physics (no hover)
        self._gravity: float = 0.0
        surf = pg.display.get_surface()
        height = surf.get_height() if surf else 720
        ground_y = height - margins.ground_offset
        self._ground_y: Optional[int] = ground_y
        self.rect.bottom = ground_y

        self.spawn_zone: Optional[dict] = None

        # Precalculate scaled hitbox dimensions for the melee slam reach
        self._scaled_hitbox_w: int = int(self._attack_hitbox_width * self.scale)
        self._scaled_hitbox_h: int = int(self._attack_hitbox_height * self.scale)

    def apply_config(self, config: dict) -> None:
        """Apply a (possibly partial) config dict to the Green Monster."""
        try:
            self._max_mana = float(config.get("max_mana", self._max_mana))
            self._spell_mana_cost = float(config.get("spell_mana_cost", self._spell_mana_cost))
            self._stagnant_duration = float(config.get("stagnant_duration", self._stagnant_duration))
            self._teleport_dist_min = int(config.get("teleport_dist_min", self._teleport_dist_min))
            self._teleport_dist_max = int(config.get("teleport_dist_max", self._teleport_dist_max))
            self._mana_recharge_rate = float(config.get("mana_recharge_rate", self._mana_recharge_rate))
            self._chase_delay_duration = float(config.get("chase_delay_duration", self._chase_delay_duration))
            self._attack_cooldown_min = float(config.get("attack_cooldown_min", self._attack_cooldown_min))
            self._attack_cooldown_max = float(config.get("attack_cooldown_max", self._attack_cooldown_max))
            self._spidey_sense = float(config.get("spidey_sense", self._spidey_sense))
        except Exception as e:
            print(f"[WARNING] Error applying green_monster config overrides: {e}")

    def _load_scaled(self, folder: str) -> list[pg.Surface]:
        """Load every frame in a folder (natural-sorted) and scale it."""
        frames = AssetManager.get_animation_frames(folder)
        if not frames:
            raise RuntimeError(f"Failed to load any frames from '{folder}'")
        if self.scale == 1.0:
            return list(frames)
        scaled = []
        for frame in frames:
            w = int(frame.get_width() * self.scale)
            h = int(frame.get_height() * self.scale)
            scaled.append(pg.transform.scale(frame, (w, h)))
        return scaled

    # ── Combat interface (mirrors Skeleton/FireWizard) ─────────────────────
    @property
    def health(self) -> float: return self._health
    @property
    def max_health(self) -> float: return self._max_health
    @property
    def entity_id(self) -> int: return id(self)
    @property
    def is_dead(self) -> bool: return self.state == GatekeeperState.DEATH

    def is_in_hit_frame(self) -> bool:
        if self.state != GatekeeperState.ATTACK:
            return False
        return self.attack_state.is_hit_frame_active()

    def should_deal_damage(self) -> bool:
        if self.state != GatekeeperState.ATTACK:
            return False
        return self.attack_state.is_hit_frame_active()

    def register_hit(self, target_id: int = 0) -> bool:
        return self.attack_state.try_register_hit(target_id)

    def try_register_hit(self, target_id: int) -> bool:
        return self.attack_state.try_register_hit(target_id)

    def get_current_attack_damage(self) -> float:
        return self.attack_state.get_current_damage()

    def get_current_attack_knockback(self) -> float:
        return self.attack_state.config.knockback_force if self.attack_state.config else 0.0

    def get_attack_hitbox(self) -> Optional[pg.Rect]:
        """Melee reach in front of the Gatekeeper -- only active during the
        ground-slam. The ranged toxic-spit deals damage via its own
        projectile, not through this hitbox."""
        if not self.should_deal_damage() or self._attack_kind != "slam":
            return None
        hitbox_w = self._scaled_hitbox_w
        hitbox_h = self._scaled_hitbox_h
        if self.facing_left:
            hitbox_x = self.rect.left - hitbox_w
        else:
            hitbox_x = self.rect.right
        hitbox_y = self.rect.centery - hitbox_h // 2
        return pg.Rect(hitbox_x, hitbox_y, hitbox_w, hitbox_h)

    def set_state(self, new_state: Enum, force: bool = False) -> None:
        old_state = self.state
        super().set_state(new_state, force=force)

        if old_state == GatekeeperState.ATTACK and self.state != GatekeeperState.ATTACK:
            self.attack_state.end()
            self._chase_cooldown = self._chase_cooldown_duration

        if new_state == GatekeeperState.ATTACK:
            self._has_spawned_attack_effect = False

        if new_state not in (GatekeeperState.IDLE, GatekeeperState.CHASE):
            self._chase_delay_timer = 0.0
            self._chase_delay_active = False

    def set_ground_y(self, ground_y: Optional[int]) -> None:
        """Update physics ground floor level from environment manager (None = freefall)."""
        self._ground_y = ground_y

    def _apply_gravity(self) -> None:
        self._gravity += 1.0
        self.rect.y += int(self._gravity)
        if self._ground_y is not None and self.rect.bottom >= self._ground_y:
            self.rect.bottom = self._ground_y
            self._gravity = 0.0

    def update(self, dt: Optional[float] = None, scroll_speed: int = 0) -> None:
        if dt is None:
            dt_sec = 1.0 / 60.0
        elif dt > 0.5:
            dt_sec = dt / 1000.0
        else:
            dt_sec = dt

        self.rect.x -= scroll_speed

        self._apply_gravity()

        if self._chase_cooldown > 0.0:
            self._chase_cooldown = max(0.0, self._chase_cooldown - dt_sec)
        if self._attack_cooldown > 0.0:
            self._attack_cooldown = max(0.0, self._attack_cooldown - dt_sec)
        if self._chase_delay_timer > 0.0:
            self._chase_delay_timer = max(0.0, self._chase_delay_timer - dt_sec)
        if self._teleport_flash_timer > 0.0:
            self._teleport_flash_timer = max(0.0, self._teleport_flash_timer - dt_sec)
        if self._stagnant_timer > 0.0:
            self._stagnant_timer = max(0.0, self._stagnant_timer - dt_sec)
            if self._stagnant_timer <= 0.0:
                if self._is_stagnant:
                    self._trigger_teleport_recharge()

        # Mana recovery
        if self._is_recharging:
            self._mana = min(self._max_mana, self._mana + self._mana_recharge_rate * dt_sec)
            if self._mana >= self._max_mana:
                self._is_recharging = False

        # Update ectoplasm launch muzzle bursts & spray droplets
        for b in self._muzzle_bursts:
            b["timer"] -= dt_sec
            b["x"] -= float(scroll_speed)
        self._muzzle_bursts = [b for b in self._muzzle_bursts if b["timer"] > 0.0]

        for s in self._muzzle_sparks:
            s["timer"] -= dt_sec
            s["x"] += s["vx"] * dt_sec - float(scroll_speed)
            s["y"] += s["vy"] * dt_sec
        self._muzzle_sparks = [s for s in self._muzzle_sparks if s["timer"] > 0.0]

        # Spawn the emerald ectoplasm bolt right as the tentacle-arm extends
        if (
            self.state == GatekeeperState.ATTACK
            and self._attack_kind == "spit"
            and not self._has_spawned_attack_effect
            and int(self.animation_index) >= self._SPIT_RELEASE_FRAME
        ):
            self._has_spawned_attack_effect = True
            self._spawn_toxic_glob()
            self._mana = max(0.0, self._mana - self._spell_mana_cost)

        self._update_ai()
        self._update_vertical_position()

        super().update(dt_sec)
        self._update_animation_audio()

        if self._teleport_after_hurt and self.state == GatekeeperState.IDLE:
            self._teleport_after_hurt = False
            self._trigger_teleport_recharge()

        # Apply teleport transparency/glow effect
        if self._teleport_flash_timer > 0.0:
            alpha = 100 if int(self._teleport_flash_timer * 30) % 2 == 0 else 200
            self.image.set_alpha(alpha)
        else:
            self.image.set_alpha(255)

        # Clean up once death animation is fully finished
        if (
            self.state == GatekeeperState.DEATH
            and int(self.animation_index) >= len(self.animations[GatekeeperState.DEATH]) - 1
        ):
            SquadTokenManager.get_instance().unregister_enemy(id(self))
            self.kill()

    def kill(self) -> None:
        SquadTokenManager.get_instance().unregister_enemy(id(self))
        super().kill()

    def _update_vertical_position(self) -> None:
        """Manage vertical positioning: jump-slam attack lunge, else ground alignment."""
        if self.state == GatekeeperState.ATTACK and self._attack_kind == "slam":
            frames = self._attack_slam_frames
            progress = self.animation_index / max(1, len(frames) - 1)
            # sin wave: 0 -> 1 -> 0
            dive = math.sin(min(1.0, progress) * math.pi)
            # Scale the jump height based on his size/scale
            if self._ground_y is not None:
                jump_height = int(90 * self.scale)
                self.rect.bottom = int(self._ground_y - dive * jump_height)
        else:
            if self._ground_y is not None and self.rect.bottom > self._ground_y:
                self.rect.bottom = self._ground_y

    def _get_tentacle_tip_pos(self, progress: float = 1.0) -> tuple[int, int]:
        """Compute screen position at the tip of the Gatekeeper's outstretched tentacle-arm."""
        direction = -1 if self.facing_left else 1
        # During windup (progress 0..1), the energy travels outward from his claw to the full tendril tip
        reach = int((18.0 + 48.0 * max(0.0, min(1.0, progress))) * self.scale)
        tip_x = (self.rect.left - reach) if self.facing_left else (self.rect.right + reach)
        tip_y = self.rect.centery - int(6 * self.scale)
        return tip_x, tip_y

    def _spawn_toxic_glob(self) -> None:
        direction = -1 if self.facing_left else 1
        spawn_x, spawn_y = self._get_tentacle_tip_pos(1.0)

        # Spawn an emerald ectoplasm muzzle-flash ring + directional spray burst right at the tendril tip
        self._muzzle_bursts.append({
            "x": float(spawn_x),
            "y": float(spawn_y),
            "timer": 0.28,
            "max_timer": 0.28,
            "max_r": max(28.0, 22.0 * self.scale),
        })
        for _ in range(14):
            ang = random.uniform(-0.85, 0.85)
            spd = random.uniform(90.0, 260.0)
            self._muzzle_sparks.append({
                "x": float(spawn_x),
                "y": float(spawn_y),
                "vx": direction * math.cos(ang) * spd,
                "vy": math.sin(ang) * spd,
                "r": random.uniform(3.0, max(5.0, 3.2 * self.scale)),
                "timer": random.uniform(0.16, 0.32),
                "max_timer": 0.32,
            })

        damage = self.current_attack_config.base_damage if self.current_attack_config else 3.0
        knockback = self.current_attack_config.knockback_force if self.current_attack_config else 6.0

        glob = ToxicGlob(
            x=spawn_x,
            y=spawn_y,
            direction=direction,
            scale=self.scale,
            damage=damage,
            knockback=knockback,
            player=self._player,
        )
        for group in self.groups():
            group.add(glob)  # type: ignore

        if self.is_enraged:
            magic_shot = MagicShotProjectile(
                x=spawn_x,
                y=spawn_y - 12,
                direction=direction,
                scale=self.scale,
                damage=damage * 1.3,
                knockback=knockback,
                player=self._player,
            )
            for group in self.groups():
                group.add(magic_shot)  # type: ignore

    def _trigger_teleport_recharge(self) -> None:
        """Instantly teleport away from the player to recharge mana."""
        if self._player is None:
            return

        player_rect = getattr(self._player, "rect", None)
        if player_rect is None:
            return

        dist_offset = random.randint(self._teleport_dist_min, self._teleport_dist_max)

        # Teleport to the opposite side of the player
        if self.rect.centerx > player_rect.centerx:
            target_x = player_rect.centerx + dist_offset
        else:
            target_x = player_rect.centerx - dist_offset

        # Clamp to screen boundaries
        target_x = max(50, min(1200, target_x))

        self.rect.centerx = target_x
        if self._ground_y is not None:
            self.rect.bottom = self._ground_y
        self._gravity = 0.0

        self._is_recharging = True
        self._is_stagnant = False
        self._stagnant_timer = 0.0
        self._teleport_flash_timer = 0.6
        self._chase_cooldown = 2.0
        self.set_state(GatekeeperState.IDLE, force=True)

    def take_damage(self, amount: float = 0.5, knockback: tuple[float, float] | None = None) -> None:
        if self.state in (GatekeeperState.HURT, GatekeeperState.DEATH):
            return

        # Check Spidey Sense dodge probability
        if self._spidey_sense > 0.0 and random.random() < self._spidey_sense:
            if self._spidey_sense >= 0.8:
                # GOD MODE: teleport behind player and counter-attack immediately
                if self._player is not None:
                    player_rect = getattr(self._player, "rect", None)
                    if player_rect:
                        if getattr(self._player, "facing_left", False):
                            target_x = player_rect.centerx + 180
                            self.facing_left = True
                        else:
                            target_x = player_rect.centerx - 180
                            self.facing_left = False

                        target_x = max(50, min(1200, target_x))
                        self.rect.centerx = target_x
                        if self._ground_y is not None:
                            self.rect.bottom = self._ground_y
                        self._gravity = 0.0

                        self._mana = max(self._mana, self._spell_mana_cost)
                        self._teleport_flash_timer = 0.6
                        self._chase_cooldown = 1.0

                        self._has_spawned_attack_effect = False
                        self._begin_attack("spit")
                        return
            else:
                # Standard spidey sense: teleport away to safety
                self._trigger_teleport_recharge()
                return

        self._health = max(0, self._health - amount)
        self.attack_state.end()

        # Check for Phase 2 Enrage transition (< 50% HP)
        if self._health <= self._max_health * 0.5 and not self.is_enraged and self._health > 0:
            self.is_enraged = True
            self._speed *= 1.4
            self._attack_cooldown_min = 0.5
            self._attack_cooldown_max = 1.0

        # If stagnant, taking damage triggers hurt animation, then teleport retreat to recharge
        if self._is_stagnant and self._health > 0:
            self.set_state(GatekeeperState.HURT, force=True)
            self._teleport_after_hurt = True
            return

        if self._health <= 0:
            SquadTokenManager.get_instance().unregister_enemy(id(self))
            self.set_state(GatekeeperState.DEATH, force=True)
        else:
            self.set_state(GatekeeperState.HURT, force=True)

    def _chase_player(self, player_rect: pg.Rect) -> None:
        dist_x = self.rect.centerx - player_rect.centerx
        abs_dist_x = abs(dist_x)

        # Smart retreating: turn away to run out of melee range rather than moonwalking backward
        if abs_dist_x < 120:
            retreat_speed = self._speed * 1.3
            if dist_x > 0:
                self.rect.x += int(retreat_speed)
                self.facing_left = False
            else:
                self.rect.x -= int(retreat_speed)
                self.facing_left = True
        # If player is too far, advance to get into range
        elif abs_dist_x > 320:
            if dist_x > 0:
                self.rect.x -= int(self._speed)
                self.facing_left = True
            else:
                self.rect.x += int(self._speed)
                self.facing_left = False
        # If in sweet spot but attack is on cooldown, stand ground & face player
        else:
            self.facing_left = (dist_x > 0)
            self.set_state(GatekeeperState.IDLE)

    def _update_ai(self) -> None:
        if self._player is None or self.state in (GatekeeperState.HURT, GatekeeperState.DEATH):
            return
        if self.state == GatekeeperState.ATTACK:
            return

        # 1. Update perception
        alert = self.perception.update(0.016, self.rect, self.facing_left, self._player)
        if alert == AlertLevel.UNAWARE:
            self.set_state(GatekeeperState.IDLE)
            return

        # If mana is low, trigger stagnant/exhausted phase
        if self._mana < self._spell_mana_cost and not self._is_recharging and not self._is_stagnant:
            self._is_stagnant = True
            self._stagnant_timer = self._stagnant_duration
            self.set_state(GatekeeperState.IDLE, force=True)
            return

        # If stagnant, remain in IDLE
        if self._is_stagnant:
            self.set_state(GatekeeperState.IDLE)
            return

        # If in chase cooldown or actively recharging, keep idling
        if self._chase_cooldown > 0.0 or self._is_recharging:
            self.set_state(GatekeeperState.IDLE)
            return

        player_rect = self._player.rect
        dist_x = self.rect.centerx - player_rect.centerx
        abs_dist_x = abs(dist_x)
        dist_y = abs(self.rect.centery - player_rect.centery)

        # Check if in attack zones and attack is off cooldown
        if dist_y < self._vertical_tolerance and self._attack_cooldown <= 0.0:
            # 1. Close-range: melee jump-slam (no mana cost)
            if abs_dist_x <= self._melee_range:
                self._chase_delay_timer = 0.0
                self._chase_delay_active = False
                self._begin_attack("slam")
                return
            # 2. Mid-to-long range: toxic glob spit (requires mana)
            if self._melee_range < abs_dist_x <= self._ranged_range and self._mana >= self._spell_mana_cost:
                self._chase_delay_timer = 0.0
                self._chase_delay_active = False
                self._begin_attack("spit")
                return

        # If player runs away, allow a brief window to run before pursuing
        if abs_dist_x > 320:
            if self.state == GatekeeperState.IDLE and not self._chase_delay_active:
                self._chase_delay_timer = self._chase_delay_duration
                self._chase_delay_active = True

        if self._chase_delay_active:
            if self._chase_delay_timer > 0.0:
                self.set_state(GatekeeperState.IDLE)
                return
            else:
                self._chase_delay_active = False

        # Handle movement updates
        self.set_state(GatekeeperState.CHASE)
        self._chase_player(player_rect)

    def _begin_attack(self, kind: str) -> None:
        self._attack_kind = kind
        self.animations[GatekeeperState.ATTACK] = (
            self._attack_slam_frames if kind == "slam" else self._attack_spit_frames
        )
        self.facing_left = (self.rect.centerx > self._player.rect.centerx)
        self.set_state(GatekeeperState.ATTACK, force=True)
        self._attack_cooldown = random.uniform(self._attack_cooldown_min, self._attack_cooldown_max)

    def draw(self, surface: pg.Surface) -> None:
        super().draw(surface)
        self._draw_spit_vfx(surface)
        if (self._health < self._max_health or self._mana < self._max_mana) and self.state != GatekeeperState.DEATH:
            self._draw_health_bar(surface)

    def _draw_spit_vfx(self, surface: pg.Surface) -> None:
        """Draw emerald ectoplasm charge-up along the extending tentacle-arm and launch burst."""
        # 1. Windup charge-up glow & converging ectoplasm wisps (frames 0..release_frame)
        if (
            self.state == GatekeeperState.ATTACK
            and self._attack_kind == "spit"
            and self.animation_index <= self._SPIT_RELEASE_FRAME + 0.5
        ):
            prog = max(0.0, min(1.0, self.animation_index / max(1.0, float(self._SPIT_RELEASE_FRAME))))
            cx, cy = self._get_tentacle_tip_pos(prog)
            rad = max(10, int((8.0 + 14.0 * prog) * self.scale))
            charge = pg.Surface((rad * 2 + 12, rad * 2 + 12), pg.SRCALPHA)
            c = rad + 6
            alpha = int(140 + 110 * prog)
            pg.draw.circle(charge, (35, 165, 60, int(alpha * 0.45)), (c, c), rad)
            pg.draw.circle(charge, (120, 250, 90, int(alpha * 0.85)), (c, c), int(rad * 0.62))
            pg.draw.circle(charge, (235, 255, 210, alpha), (c, c), max(3, int(rad * 0.30)))
            # Swirling converging ectoplasm arcs
            t = pg.time.get_ticks() * 0.015
            for i in range(4):
                ang = t + i * (math.pi * 0.5)
                dist = rad * (1.25 - 0.65 * prog)
                px = int(c + math.cos(ang) * dist)
                py = int(c + math.sin(ang) * dist)
                pg.draw.line(charge, (175, 255, 130, alpha), (px, py), (c, c), 2)
            surface.blit(charge, (cx - c, cy - c))

        # 2. Expanding emerald muzzle-burst rings on launch
        for b in self._muzzle_bursts:
            t = 1.0 - max(0.0, b["timer"] / b["max_timer"])
            alpha = int(235 * (1.0 - t))
            if alpha <= 4:
                continue
            rad = max(8, int(b["max_r"] * (0.35 + 0.95 * t)))
            rw = max(6, int(rad * 0.55))
            rh = rad
            bs = pg.Surface((rw * 2 + 10, rh * 2 + 10), pg.SRCALPHA)
            pg.draw.ellipse(bs, (90, 245, 95, alpha), (5, 5, rw * 2, rh * 2), 3)
            pg.draw.ellipse(bs, (220, 255, 190, int(alpha * 0.8)), (5 + rw // 3, 5 + rh // 4, max(4, rw * 4 // 3), max(6, rh * 3 // 2)), 2)
            surface.blit(bs, (int(b["x"] - rw - 5), int(b["y"] - rh - 5)))

        # 3. Directional ectoplasm spray droplets
        for s in self._muzzle_sparks:
            frac = max(0.0, s["timer"] / s["max_timer"])
            alpha = int(230 * frac)
            sr = max(2, int(s["r"] * frac))
            ss = pg.Surface((sr * 2 + 4, sr * 2 + 4), pg.SRCALPHA)
            pg.draw.circle(ss, (65, 225, 85, int(alpha * 0.7)), (sr + 2, sr + 2), sr + 1)
            pg.draw.circle(ss, (205, 255, 160, alpha), (sr + 2, sr + 2), max(1, sr - 1))
            surface.blit(ss, (int(s["x"] - sr - 2), int(s["y"] - sr - 2)))

    def _draw_health_bar(self, surface: pg.Surface) -> None:
        bar_width = 40
        bar_height = 5
        bar_x = self.rect.centerx - bar_width // 2
        bar_y = self.rect.top - 15

        # Red health bar
        pg.draw.rect(surface, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height))
        health_ratio = max(0.0, self._health / self._max_health)
        pg.draw.rect(surface, (255, 0, 0), (bar_x, bar_y, int(bar_width * health_ratio), bar_height))

        # Blue/Green mana bar
        mana_y = bar_y + bar_height + 2
        pg.draw.rect(surface, (50, 50, 50), (bar_x, mana_y, bar_width, 3))
        mana_ratio = max(0.0, self._mana / self._max_mana)
        pg.draw.rect(surface, (50, 205, 50), (bar_x, mana_y, int(bar_width * mana_ratio), 3))

        # Draw charging green aura if actively recharging
        if self._is_recharging:
            glow_radius = int(24 * self.scale + 6 * random.random())
            pg.draw.circle(surface, (50, 205, 50), self.rect.center, glow_radius, 2)
