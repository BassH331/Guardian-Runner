"""
HUDOverlay — Unified manager for heads-up display overlays, player UI, boss health bars,
notification banners, objective popups, and tutorial prompts.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, Optional, TYPE_CHECKING
import pygame as pg

from v3x_zulfiqar_gideon import AssetManager, NotificationBanner
from src.game.ui.player_ui import PlayerUI
from src.game.ui.objective_display import ObjectiveDisplay
from src.game.ui.tutorial_overlay import TutorialOverlay
from src.game.ui.side_notification import SideNotification
from src.game.entities.boss_manager import BossManager

if TYPE_CHECKING:
    from src.game.systems.corruption_manager import CorruptionManager
    from src.game.systems.relic_manager import RelicManager

# Relic strip layout constants (top-right 6 visible 34x34 framed icon slots).
_RELIC_SLOT_SIZE = 34
_RELIC_SLOT_GAP = 6
_RELIC_SLOT_COUNT = 6
_RELIC_STRIP_MARGIN = 10   # distance from right / top screen edge
_RELIC_EMPTY_COLOUR = (20, 18, 30)
_RELIC_BORDER_COLOUR = (78, 66, 98)

_HEALTH_RELIC_ICON_PATH = "assets/free-undead-loot-pixel-art-icons/PNG/Transperent/Icon29.png"

_RELIC_SLOT_ORDER = [
    "the_eye",
    "bark_of_the_great_one",
    "shattered_gauntlet",
    "candoras_tear",
    "amalgam_core",
]

# Theme colours: (border/primary RGB, wind ribbon RGB, sparkle highlight RGB)
_RELIC_THEMES: Dict[str, tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]] = {
    "ruby_elixir": ((240, 55, 85), (255, 110, 145), (255, 225, 235)),
    "the_eye": ((190, 85, 255), (150, 115, 255), (240, 215, 255)),
    "bark_of_the_great_one": ((235, 100, 60), (255, 155, 75), (255, 225, 165)),
    "shattered_gauntlet": ((110, 185, 255), (170, 225, 255), (245, 250, 255)),
    "tainted_sigil": ((220, 65, 105), (185, 55, 145), (255, 195, 215)),
    "candoras_tear": ((100, 225, 255), (175, 245, 255), (255, 255, 255)),
    "amalgam_core": ((255, 195, 65), (255, 225, 125), (255, 250, 215)),
}
_DEFAULT_RELIC_ICON_PATHS: Dict[str, str] = {
    "ruby_elixir": _HEALTH_RELIC_ICON_PATH,
    "the_eye": "assets/graphics/eye monster single frame.png",
    "bark_of_the_great_one": "assets/Free-Undead-Skill-Pixel-Art-Icons/PNG/Icon24.png",
    "shattered_gauntlet": "assets/free-undead-loot-pixel-art-icons/PNG/Transperent/Icon1.png",
    "tainted_sigil": "assets/graphics/ui/relic_icon.png",
    "candoras_tear": "assets/graphics/ui/powerup_invincible.png",
    "amalgam_core": "assets/graphics/ui/powerup_speed.png",
}


class HUDOverlay:
    """Consolidated heads-up display and overlay system."""

    def __init__(self, screen_width: int, screen_height: int,
                 corruption_manager: Optional["CorruptionManager"] = None,
                 relic_manager: Optional["RelicManager"] = None) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.corruption_manager: Optional["CorruptionManager"] = corruption_manager
        self.relic_manager: Optional["RelicManager"] = relic_manager

        self.player_ui = PlayerUI()
        self.player_ui.corruption_manager = corruption_manager
        self.objective_display = ObjectiveDisplay()
        self.notification_banner = NotificationBanner(scale=1.0, banner_width_frac=0.55, icon_scale=0.7, hold=3.0)
        self.side_notification = SideNotification(self.screen_width, self.screen_height)
        self.tutorial_overlay = TutorialOverlay()

        # Top-right Relic Strip & Permanent 3-Charge Ruby Elixir state
        self._anim_clock: float = 0.0
        self._relic_config: Dict[str, Any] = {}
        self._icon_cache: Dict[tuple[str, int], pg.Surface] = {}
        self._known_collected: set[str] = set()
        self._active_showcase: Optional[Dict[str, Any]] = None
        self._heal_flash_timer: float = 0.0
        self.health_relic_charges: int = 3
        self.health_relic_max_charges: int = 3
        self.health_relic_low_hp_ratio: float = 0.30
        self.health_relic_slot_rect: Optional[pg.Rect] = None
        self.health_relic_popup_rect: Optional[pg.Rect] = None

        try:
            self._badge_font = AssetManager.get_font("assets/font/Abaddon Bold.ttf", 14)
            self._showcase_title_font = AssetManager.get_font("assets/font/Abaddon Bold.ttf", 18)
            self._showcase_body_font = AssetManager.get_font("assets/font/Abaddon Bold.ttf", 15)
        except Exception:
            self._badge_font = pg.font.SysFont("Arial", 13, bold=True)
            self._showcase_title_font = pg.font.SysFont("Arial", 16, bold=True)
            self._showcase_body_font = pg.font.SysFont("Arial", 13)

    def set_relic_config(self, relics_cfg: Dict[str, Any]) -> None:
        """Supply storyline relic metadata so HUD slots load configured icons & titles."""
        self._relic_config = dict(relics_cfg or {})

    def trigger_relic_showcase(self, relic_id: str, duration: float = 4.5) -> None:
        """Showcase a newly acquired relic on the main HUD screen with wind & sparkles."""
        meta = self._relic_config.get(relic_id, {})
        self._active_showcase = {
            "id": relic_id,
            "title": meta.get("title") or meta.get("name") or relic_id.replace("_", " ").title(),
            "subtitle": meta.get("subtitle") or "Relic Awakened",
            "timer": float(duration),
            "duration": float(duration),
        }

    def trigger_heal_showcase(self) -> None:
        """Trigger a visible crimson heal shimmer after using Ruby Elixir."""
        self._heal_flash_timer = 1.6

    def update(self, dt: float = 0.0) -> None:
        """Update active UI timers and animations."""
        dt_sec = dt / 1000.0 if dt > 0.5 else dt
        self._anim_clock += max(0.0, dt_sec)
        if self._heal_flash_timer > 0.0:
            self._heal_flash_timer = max(0.0, self._heal_flash_timer - dt_sec)
        if self._active_showcase is not None:
            self._active_showcase["timer"] -= dt_sec
            if self._active_showcase["timer"] <= 0.0:
                self._active_showcase = None

        if self.relic_manager is not None:
            current = set(self.relic_manager.collected_ids())
            newly = [rid for rid in self.relic_manager.collected_ids() if rid not in self._known_collected]
            if newly:
                self._known_collected = current
                self.trigger_relic_showcase(newly[-1])

        self.player_ui.update()
        self.side_notification.update(dt)

    def _get_relic_icon(self, relic_id: str, size: int) -> Optional[pg.Surface]:
        key = (relic_id, size)
        if key in self._icon_cache:
            return self._icon_cache[key]
        meta = self._relic_config.get(relic_id, {})
        path = meta.get("icon_path") or _DEFAULT_RELIC_ICON_PATHS.get(relic_id, "assets/graphics/ui/relic_icon.png")
        if not path or not os.path.exists(path):
            fallback = _DEFAULT_RELIC_ICON_PATHS.get(relic_id)
            path = fallback if (fallback and os.path.exists(fallback)) else ""
        if not path:
            return None
        try:
            raw = AssetManager.get_texture(path)
            scaled = pg.transform.scale(raw, (size, size))
            self._icon_cache[key] = scaled
            return scaled
        except Exception:
            return None

    def _draw_theme_wind_and_sparkles(
        self,
        surface: pg.Surface,
        rect: pg.Rect,
        theme_key: str,
        seed: float = 0.0,
        intensity: float = 1.0,
    ) -> None:
        """Render animated theme-colored glow halo, sweeping wind ribbons, and orbiting sparkles."""
        primary, wind_col, sparkle_col = _RELIC_THEMES.get(
            theme_key, ((215, 165, 70), (245, 200, 110), (255, 250, 220))
        )
        t = self._anim_clock + seed
        pulse = (math.sin(t * 3.8) + 1.0) * 0.5

        # 1. Soft radial glow halo behind frame
        pad = int(14 * intensity)
        glow_w = rect.width + pad * 2
        glow_h = rect.height + pad * 2
        glow_surf = pg.Surface((glow_w, glow_h), pg.SRCALPHA)
        gx, gy = glow_w // 2, glow_h // 2
        r_outer = min(glow_w, glow_h) // 2
        outer_alpha = int(min(140, (35 + 45 * pulse) * intensity))
        inner_alpha = int(min(180, (55 + 55 * pulse) * intensity))
        pg.draw.circle(glow_surf, (*primary, outer_alpha), (gx, gy), r_outer)
        pg.draw.circle(glow_surf, (*wind_col, inner_alpha), (gx, gy), max(4, int(r_outer * 0.65)))
        surface.blit(glow_surf, (rect.centerx - gx, rect.centery - gy))

        # 2. Animated theme-colored wind streaks sweeping past the icon
        wind_surf = pg.Surface((glow_w + 24, glow_h + 12), pg.SRCALPHA)
        wcx = wind_surf.get_width() // 2
        wcy = wind_surf.get_height() // 2
        for w_idx in range(3):
            phase = (t * (1.5 + w_idx * 0.35) + w_idx * 2.1) % 3.14159
            travel = math.sin(phase) * (rect.width * 0.55)
            y_off = int((w_idx - 1) * (rect.height * 0.26) + math.sin(t * 4.5 + w_idx) * 2.5)
            alpha_w = int(min(210, (90 + 90 * math.sin(phase)) * intensity))
            pts = []
            span = max(16, int(rect.width * 0.85))
            for step in range(5):
                frac = step / 4.0
                px = int(wcx - span // 2 + frac * span + travel * 0.25)
                py = int(wcy + y_off + math.sin(t * 6.0 + frac * 4.2 + w_idx) * 3.0)
                pts.append((px, py))
            if len(pts) >= 2:
                pg.draw.lines(wind_surf, (*wind_col, alpha_w), False, pts, 2)
        surface.blit(wind_surf, (rect.centerx - wcx, rect.centery - wcy))

        # 3. Twinkling 4-point star sparkles orbiting around the frame
        for sp_idx in range(4):
            ang = t * 1.9 + sp_idx * (math.pi * 0.5)
            orbit_r = max(rect.width, rect.height) * 0.54 + math.sin(t * 4.0 + sp_idx) * 2.0
            sx = int(rect.centerx + math.cos(ang) * orbit_r)
            sy = int(rect.centery + math.sin(ang) * (orbit_r * 0.82))
            twinkle = (math.sin(t * 7.2 + sp_idx * 1.7) + 1.0) * 0.5
            arm = max(2, int((2 + 3 * twinkle) * min(1.3, intensity)))
            sp_alpha = int(120 + 135 * twinkle)
            sp_s = pg.Surface((arm * 2 + 3, arm * 2 + 3), pg.SRCALPHA)
            mc = arm + 1
            pg.draw.line(sp_s, (*sparkle_col, sp_alpha), (mc - arm, mc), (mc + arm, mc), 1)
            pg.draw.line(sp_s, (*sparkle_col, sp_alpha), (mc, mc - arm), (mc, mc + arm), 1)
            pg.draw.circle(sp_s, (*sparkle_col, sp_alpha), (mc, mc), 1)
            surface.blit(sp_s, (sx - mc, sy - mc))

    def draw_world_ui(self, target_surface: pg.Surface) -> None:
        """Render player HUD elements drawn directly in world surface."""
        self.player_ui.draw(target_surface)

    def draw_boss_health_bar(self, target_surface: pg.Surface, obstacle_group: pg.sprite.Group) -> None:
        """Render active boss health bar overlay."""
        BossManager.draw_boss_health_bar(target_surface, obstacle_group, self.screen_width)

    def _get_display_slots(self) -> list[tuple[str, bool]]:
        """Return 6 top-right slot descriptors: Slot 0 = Ruby Elixir, Slots 1..5 = Relics."""
        collected_ordered = (
            list(self.relic_manager.collected_ids())
            if self.relic_manager is not None
            else []
        )
        collected_set = set(collected_ordered)
        slots: list[tuple[str, bool]] = [("ruby_elixir", self.health_relic_charges > 0)]

        # Include canonical ordered relics + any extras (e.g. tainted_sigil) so nothing collected stays hidden
        candidates = list(_RELIC_SLOT_ORDER)
        for cid in collected_ordered:
            if cid not in candidates:
                # Replace an uncollected placeholder slot if needed, preserving 5 relic slots total
                uncollected = [c for c in candidates if c not in collected_set]
                if uncollected:
                    candidates.remove(uncollected[-1])
                candidates.append(cid)

        for rid in candidates[: _RELIC_SLOT_COUNT - 1]:
            slots.append((rid, rid in collected_set))
        while len(slots) < _RELIC_SLOT_COUNT:
            slots.append(("", False))
        return slots

    def draw_relic_strip(self, screen_surface: pg.Surface) -> None:
        """Render 6 visible top-right HUD slots (Ruby Elixir + Boss Relics) with theme wind & sparkles."""
        slots = self._get_display_slots()
        sw = screen_surface.get_width()
        strip_w = _RELIC_SLOT_COUNT * (_RELIC_SLOT_SIZE + _RELIC_SLOT_GAP) - _RELIC_SLOT_GAP
        start_x = sw - _RELIC_STRIP_MARGIN - strip_w
        start_y = _RELIC_STRIP_MARGIN

        cur_hp = float(getattr(self.player_ui, "current_health", 100.0))
        max_hp = float(getattr(self.player_ui, "max_health", 100.0)) or 100.0
        is_low_hp = 0.0 < cur_hp <= max_hp * self.health_relic_low_hp_ratio and self.health_relic_charges > 0

        self.health_relic_slot_rect = None
        for i, (relic_id, is_active) in enumerate(slots):
            slot_x = start_x + i * (_RELIC_SLOT_SIZE + _RELIC_SLOT_GAP)
            slot_rect = pg.Rect(slot_x, start_y, _RELIC_SLOT_SIZE, _RELIC_SLOT_SIZE)

            if i == 0:
                self.health_relic_slot_rect = slot_rect

            if is_active and relic_id:
                intensity = 1.55 if (relic_id == "ruby_elixir" and is_low_hp) else 1.0
                self._draw_theme_wind_and_sparkles(
                    screen_surface, slot_rect, relic_id, seed=i * 0.9, intensity=intensity
                )

            # Dark obsidian slot background + theme border
            theme_col = _RELIC_THEMES.get(relic_id, (_RELIC_BORDER_COLOUR,))[0]
            border_col = theme_col if is_active else _RELIC_BORDER_COLOUR
            pg.draw.rect(screen_surface, _RELIC_EMPTY_COLOUR, slot_rect, border_radius=6)
            pg.draw.rect(screen_surface, border_col, slot_rect, width=2 if is_active else 1, border_radius=6)

            if relic_id:
                icon_surf = self._get_relic_icon(relic_id, _RELIC_SLOT_SIZE - 8)
                if icon_surf is not None:
                    draw_icon = icon_surf if is_active else icon_surf.copy()
                    if not is_active:
                        draw_icon.set_alpha(45)
                    screen_surface.blit(
                        draw_icon,
                        icon_surf.get_rect(center=slot_rect.center),
                    )

            # Charge counter badge for Ruby Elixir (always shows 3 -> 2 -> 1 -> 0)
            if relic_id == "ruby_elixir":
                cnt_str = str(max(0, int(self.health_relic_charges)))
                cnt_col = (255, 235, 140) if self.health_relic_charges > 0 else (150, 90, 95)
                badge_r = pg.Rect(slot_rect.right - 13, slot_rect.bottom - 13, 14, 14)
                pg.draw.rect(screen_surface, (18, 8, 16), badge_r, border_radius=4)
                pg.draw.rect(screen_surface, border_col, badge_r, width=1, border_radius=4)
                cnt_surf = self._badge_font.render(cnt_str, True, cnt_col)
                screen_surface.blit(cnt_surf, cnt_surf.get_rect(center=badge_r.center))

        # Low-HP Showcase Hint Box (visible in upper-right main game screen when HP <= 30%)
        self.health_relic_popup_rect = None
        if is_low_hp:
            pop_w, pop_h = 376, 78
            pop_x = sw - pop_w - 14
            pop_y = 250 if self.side_notification.is_active else 108
            pop_rect = pg.Rect(pop_x, pop_y, pop_w, pop_h)
            self.health_relic_popup_rect = pop_rect

            self._draw_theme_wind_and_sparkles(
                screen_surface, pop_rect, "ruby_elixir", seed=0.3, intensity=1.45
            )
            pg.draw.rect(screen_surface, (24, 8, 18), pop_rect, border_radius=10)
            pulse_border = 255 if int(self._anim_clock * 5) % 2 == 0 else 195
            pg.draw.rect(screen_surface, (pulse_border, 70, 105), pop_rect, width=2, border_radius=10)

            big_icon = self._get_relic_icon("ruby_elixir", 48)
            if big_icon is not None:
                icon_box = pg.Rect(pop_x + 12, pop_y + 15, 48, 48)
                pg.draw.rect(screen_surface, (36, 12, 26), icon_box, border_radius=7)
                pg.draw.rect(screen_surface, (255, 110, 145), icon_box, width=1, border_radius=7)
                screen_surface.blit(big_icon, icon_box.topleft)

            t1 = self._showcase_title_font.render("CRITICAL HEALTH! RUBY ELIXIR", True, (255, 195, 110))
            t2 = self._showcase_body_font.render(
                f"Press [H] or CLICK to Heal +60 HP ({self.health_relic_charges} left)",
                True,
                (255, 240, 245),
            )
            screen_surface.blit(t1, (pop_x + 70, pop_y + 16))
            screen_surface.blit(t2, (pop_x + 70, pop_y + 44))

        # Newly Acquired Relic Main-Screen Showcase Banner (visible when an item like The Eye arrives)
        if self._active_showcase is not None and not is_low_hp:
            rid = self._active_showcase["id"]
            sc_w, sc_h = 376, 78
            sc_x = sw - sc_w - 14
            sc_y = 250 if self.side_notification.is_active else 108
            sc_rect = pg.Rect(sc_x, sc_y, sc_w, sc_h)
            primary, wind_col, _ = _RELIC_THEMES.get(rid, ((220, 175, 75), (255, 220, 130), (255, 255, 230)))
            self._draw_theme_wind_and_sparkles(screen_surface, sc_rect, rid, seed=1.2, intensity=1.4)
            pg.draw.rect(screen_surface, (16, 12, 28), sc_rect, border_radius=10)
            pg.draw.rect(screen_surface, primary, sc_rect, width=2, border_radius=10)

            big_icon = self._get_relic_icon(rid, 48)
            if big_icon is not None:
                icon_box = pg.Rect(sc_x + 12, sc_y + 15, 48, 48)
                pg.draw.rect(screen_surface, (28, 20, 44), icon_box, border_radius=7)
                pg.draw.rect(screen_surface, wind_col, icon_box, width=1, border_radius=7)
                screen_surface.blit(big_icon, icon_box.topleft)

            t1 = self._showcase_title_font.render(str(self._active_showcase["title"])[:28], True, wind_col)
            t2 = self._showcase_body_font.render("Relic Bound to Top-Right HUD", True, (235, 230, 245))
            screen_surface.blit(t1, (sc_x + 70, sc_y + 16))
            screen_surface.blit(t2, (sc_x + 70, sc_y + 44))

        if self._heal_flash_timer > 0.0:
            msg = self._showcase_title_font.render("+60 HP  RUBY ELIXIR RESTORED", True, (255, 165, 195))
            screen_surface.blit(msg, msg.get_rect(topright=(sw - 16, 106)))

    def draw_screen_overlays(self, screen_surface: pg.Surface) -> None:
        """Render screen-space overlays (objective display, notification banner, tutorial, side notification)."""
        self.objective_display.draw(screen_surface)
        self.notification_banner.draw(screen_surface)
        self.tutorial_overlay.draw(screen_surface)
        self.side_notification.draw(screen_surface)

        # Relic icon strip — drawn before the vignette so it's visible through the darkness
        self.draw_relic_strip(screen_surface)

        # Corruption vignette — drawn last so it composites over all other HUD elements
        if self.corruption_manager is not None and self.corruption_manager.value > 0:
            self.player_ui.render_corruption_vignette(
                screen_surface,
                self.corruption_manager.value / 100.0,
            )
