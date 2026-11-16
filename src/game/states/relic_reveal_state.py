"""
RelicRevealState  -  Atmospheric memory-flashback & relic lore overlay State.

Pushed onto the state stack (or displayed as an in-game overlay) when a relic is
collected; pops/dismisses itself when the player presses any key or clicks.
"""

from __future__ import annotations

import os
import math
import pygame as pg

from v3x_zulfiqar_gideon import State, AssetManager
from src.game.ui.animated_dialogue_renderer import AnimatedDialogueRenderer

# Panel dimensions (centred on screen).
_PANEL_W = 880
_PANEL_H = 450

# Colours
_OVERLAY_COLOUR = (4, 2, 10, 205)
_PANEL_BG = (14, 8, 24)
_PANEL_BORDER = (215, 165, 65)
_PANEL_INNER_BORDER = (95, 60, 130)
_NAME_COLOUR = (255, 215, 95)
_SUBTITLE_COLOUR = (185, 150, 220)
_MEMORY_COLOUR = (245, 205, 135)
_LORE_COLOUR = (225, 215, 240)
_RESONANCE_LOW = (130, 215, 255)
_RESONANCE_MID = (235, 175, 85)
_RESONANCE_HIGH = (245, 90, 105)
_PROMPT_COLOUR = (195, 170, 225)

# Blink rate for "[ Press any key ]" prompt.
_BLINK_HZ = 1.0


def _load_pixel_font(size: int, bold: bool = False) -> pg.font.Font:
    font_path = "assets/font/Abaddon Bold.ttf"
    if os.path.exists(font_path):
        try:
            return AssetManager.get_font(font_path, size)
        except Exception:
            pass
    return pg.font.SysFont("Arial", size, bold=bold)


class RelicRevealState(State):
    """Overlay state that shows relic icon, memory flashback, lore, and soul resonance."""

    is_overlay: bool = True

    def __init__(self, manager, relic_id: str, relic_data: dict, on_dismiss=None) -> None:
        super().__init__(manager)
        self._relic_id = relic_id
        self._relic_data = relic_data or {}
        self._on_dismiss = on_dismiss
        self.is_active: bool = True

        self._renderer = AnimatedDialogueRenderer(
            typing_speed=140.0,
            scale_duration=0.12,
            max_scale=1.12,
        )

        # Fonts  -  created lazily in on_enter to ensure pygame display is up.
        self._font_name: pg.font.Font | None = None
        self._font_subtitle: pg.font.Font | None = None
        self._font_memory: pg.font.Font | None = None
        self._font_lore: pg.font.Font | None = None
        self._font_prompt: pg.font.Font | None = None
        self._icon_surf: pg.Surface | None = None

        # Semi-transparent overlay surface (created once in on_enter).
        self._overlay: pg.Surface | None = None

        # Elapsed time used for blink and aura animation.
        self._elapsed: float = 0.0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_enter(self) -> None:
        """Start typewriter animation, play reveal chime, and prepare surfaces."""
        self.is_active = True
        display = pg.display.get_surface()
        sw = display.get_width() if display else 1280
        sh = display.get_height() if display else 720

        self._overlay = pg.Surface((sw, sh), pg.SRCALPHA)
        self._overlay.fill(_OVERLAY_COLOUR)

        self._font_name = _load_pixel_font(34, bold=True)
        self._font_subtitle = _load_pixel_font(20)
        self._font_memory = _load_pixel_font(22)
        self._font_lore = _load_pixel_font(22)
        self._font_prompt = _load_pixel_font(18)

        icon_path = self._relic_data.get("icon_path", "")
        self._icon_surf = None
        if icon_path and os.path.exists(icon_path):
            try:
                raw_icon = AssetManager.get_texture(icon_path)
                self._icon_surf = pg.transform.smoothscale(raw_icon, (64, 64))
            except Exception:
                self._icon_surf = None

        lore = self._relic_data.get("lore") or self._relic_data.get("memory_text") or ""
        self._renderer.set_text(lore)
        self._elapsed = 0.0

        if self.manager is not None and hasattr(self.manager, "audio_manager") and self.manager.audio_manager:
            try:
                self.manager.audio_manager.play_sound("reveal", volume=0.55)
            except Exception:
                pass

    def on_exit(self) -> None:
        """Mark overlay inactive upon exit."""
        self.is_active = False

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        dt_sec = dt / 1000.0 if dt > 1.0 else dt
        self._elapsed += dt_sec
        self._renderer.update(dt_sec)

    def _wrap_text(self, font: pg.font.Font, text: str, max_w: int) -> list[str]:
        words = text.split(" ")
        lines: list[str] = []
        curr = ""
        for w in words:
            cand = f"{curr} {w}".strip() if curr else w
            if font.size(cand)[0] <= max_w:
                curr = cand
            else:
                if curr:
                    lines.append(curr)
                curr = w
        if curr:
            lines.append(curr)
        return lines

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface: pg.Surface) -> None:
        sw, sh = surface.get_size()

        # 1. Dark semi-transparent full-screen overlay.
        if self._overlay is None or self._overlay.get_size() != (sw, sh):
            self._overlay = pg.Surface((sw, sh), pg.SRCALPHA)
            self._overlay.fill(_OVERLAY_COLOUR)
        surface.blit(self._overlay, (0, 0))

        # 2. Centre panel with pulsing aura.
        px = (sw - _PANEL_W) // 2
        py = (sh - _PANEL_H) // 2
        panel_rect = pg.Rect(px, py, _PANEL_W, _PANEL_H)

        pulse = (math.sin(self._elapsed * 2.8) + 1.0) * 0.5
        glow_rect = panel_rect.inflate(12, 12)
        glow_surf = pg.Surface((glow_rect.width, glow_rect.height), pg.SRCALPHA)
        pg.draw.rect(
            glow_surf,
            (180, 120, 255, int(35 + 35 * pulse)),
            glow_surf.get_rect(),
            border_radius=12,
        )
        surface.blit(glow_surf, glow_rect.topleft)

        pg.draw.rect(surface, _PANEL_BG, panel_rect, border_radius=10)
        pg.draw.rect(surface, _PANEL_BORDER, panel_rect, width=2, border_radius=10)
        pg.draw.rect(surface, _PANEL_INNER_BORDER, panel_rect.inflate(-8, -8), width=1, border_radius=8)

        padding = 26
        header_left = panel_rect.left + padding

        # 3. Relic Icon Badge (top-left of panel)
        if self._icon_surf is not None:
            icon_box = pg.Rect(panel_rect.left + padding, panel_rect.top + 22, 76, 76)
            pg.draw.rect(surface, (24, 14, 38), icon_box, border_radius=8)
            pg.draw.rect(surface, _PANEL_BORDER, icon_box, width=1, border_radius=8)
            icon_rect = self._icon_surf.get_rect(center=icon_box.center)
            surface.blit(self._icon_surf, icon_rect)
            header_left = icon_box.right + 18

        # 4. Relic Name & Subtitle
        text_top = panel_rect.top + 22
        if self._font_name:
            name = self._relic_data.get("name") or self._relic_data.get("title") or self._relic_id
            name_surf = self._font_name.render(f"MEMORY RELIC: {name.upper()}", True, _NAME_COLOUR)
            surface.blit(name_surf, (header_left, text_top))
            text_top += name_surf.get_height() + 4

        if self._font_subtitle:
            subtitle = self._relic_data.get("subtitle") or self._relic_data.get("category") or "Vessel Fragment"
            delta = self._relic_data.get("_corruption_delta", 0.0)
            if delta < 0:
                sub_str = f"{subtitle}  |  Candora's Grace ({delta:+.0f}% Corruption)"
            elif delta > 0:
                sub_str = f"{subtitle}  |  Andras's Toll ({delta:+.0f}% Corruption)"
            else:
                sub_str = subtitle
            sub_surf = self._font_subtitle.render(sub_str, True, _SUBTITLE_COLOUR)
            surface.blit(sub_surf, (header_left, text_top))
            text_top += sub_surf.get_height() + 18
        else:
            text_top += 28

        if self._icon_surf is not None:
            text_top = max(text_top, panel_rect.top + 108)

        # Divider line
        pg.draw.line(
            surface,
            (95, 65, 130),
            (panel_rect.left + padding, text_top),
            (panel_rect.right - padding, text_top),
            1,
        )
        text_top += 12

        # 5. Memory Flashback quote (if distinct from lore)
        memory_text = self._relic_data.get("memory_text", "")
        lore_text = self._relic_data.get("lore", "")
        if self._font_memory and memory_text and memory_text != lore_text:
            mem_lines = self._wrap_text(self._font_memory, f'"{memory_text}"', _PANEL_W - padding * 2)
            for mline in mem_lines[:3]:
                m_surf = self._font_memory.render(mline, True, _MEMORY_COLOUR)
                surface.blit(m_surf, (panel_rect.left + padding, text_top))
                text_top += m_surf.get_height() + 3
            text_top += 8

        # 6. Typewriter Lore Text (middle section)
        if self._font_lore:
            lore_rect = pg.Rect(
                panel_rect.left + padding,
                text_top,
                _PANEL_W - padding * 2,
                panel_rect.bottom - text_top - 78,
            )
            self._renderer.render(
                surface,
                self._font_lore,
                lore_rect,
                color=_LORE_COLOUR,
                shadow_color=(0, 0, 0),
                align="left",
                line_spacing=5,
            )

        # 7. Corruption Resonance Footer
        variants = self._relic_data.get("corruption_variants", {})
        if variants and self._font_subtitle:
            corr_val = float(self._relic_data.get("_corruption_value", 0.0))
            if corr_val <= 33.0:
                res_text = variants.get("low", "")
                res_col = _RESONANCE_LOW
                res_tag = "SOUL RESONANCE [PURE]: "
            elif corr_val <= 66.0:
                res_text = variants.get("mid", "")
                res_col = _RESONANCE_MID
                res_tag = "SOUL RESONANCE [FRACTURED]: "
            else:
                res_text = variants.get("high", "")
                res_col = _RESONANCE_HIGH
                res_tag = "SOUL RESONANCE [HOLLOWING]: "

            if res_text:
                full_res = f"{res_tag}{res_text}"
                res_lines = self._wrap_text(self._font_subtitle, full_res, _PANEL_W - padding * 2)
                base_bottom = panel_rect.bottom - 42
                for idx_r, rline in enumerate(reversed(res_lines[:2])):
                    res_surf = self._font_subtitle.render(rline, True, res_col)
                    res_rect = res_surf.get_rect(
                        centerx=panel_rect.centerx,
                        bottom=base_bottom - idx_r * (res_surf.get_height() + 2),
                    )
                    surface.blit(res_surf, res_rect)

        # 8. Blinking prompt at the bottom
        if self._font_prompt:
            if self._elapsed < 0.85:
                prompt_surf = self._font_prompt.render(
                    "[ AWAKENING MEMORY... ]",
                    True,
                    (145, 125, 175),
                )
                prompt_rect = prompt_surf.get_rect(
                    centerx=panel_rect.centerx,
                    bottom=panel_rect.bottom - 14,
                )
                surface.blit(prompt_surf, prompt_rect)
            else:
                blink_visible = math.sin(self._elapsed * _BLINK_HZ * math.pi * 2) >= -0.2
                if blink_visible:
                    prompt_surf = self._font_prompt.render(
                        "[ PRESS SPACE, ENTER, OR CLICK TO CONTINUE ]",
                        True,
                        _PROMPT_COLOUR,
                    )
                    prompt_rect = prompt_surf.get_rect(
                        centerx=panel_rect.centerx,
                        bottom=panel_rect.bottom - 14,
                    )
                    surface.blit(prompt_surf, prompt_rect)

    # ── Input ─────────────────────────────────────────────────────────────────

    def dismiss(self) -> None:
        """Dismiss the relic reveal cutscene and invoke any callbacks."""
        self.is_active = False
        if callable(self._on_dismiss):
            try:
                self._on_dismiss()
            except Exception as e:
                print(f"[RelicRevealState] on_dismiss error: {e}")
        if (
            self.manager is not None
            and hasattr(self.manager, "stack")
            and self.manager.stack
            and self.manager.stack[-1] is self
        ):
            self.manager.pop()

    def handle_event(self, event: pg.event.Event) -> bool:
        """Deliberate confirm keys, click, or controller button advance/dismiss after a short grace window."""
        if not self.is_active:
            return False

        # Ignore lingering combat/movement inputs for the first 0.85s so players can actually read it
        if self._elapsed < 0.85:
            return event.type in (pg.KEYDOWN, pg.MOUSEBUTTONDOWN, pg.JOYBUTTONDOWN)

        is_confirm = (
            (event.type == pg.KEYDOWN and event.key in (pg.K_SPACE, pg.K_RETURN, pg.K_KP_ENTER, pg.K_ESCAPE))
            or (event.type == pg.MOUSEBUTTONDOWN and event.button == 1)
            or (event.type == pg.JOYBUTTONDOWN and event.button in (0, 1, 7))
        )
        if is_confirm:
            if not self._renderer.is_complete:
                self._renderer.skip_to_end()
                return True
            self.dismiss()
            return True
        return False
