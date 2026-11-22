"""ControlsState - Player-friendly Controls screen reading live from controls_config.json."""

from __future__ import annotations

import json
import os
import pygame as pg
from v3x_zulfiqar_gideon import State, AssetManager


_ACTION_LABELS = [
    ("MOVE", "Move Left / Right"),
    ("JUMP", "Jump / Double Jump"),
    ("ATTACK_THRUST", "Light Attack"),
    ("ATTACK_SMASH", "Heavy Smash"),
    ("ATTACK_POWER", "Power Strike"),
    ("SPECIAL_ATTACK", "Special Attack"),
    ("DEFEND", "Block / Parry"),
    ("ROLL", "Dodge Roll"),
    ("DASH", "Dash"),
    ("TRANSFORM", "Demon Form"),
]

_EXTRA_ROWS = [
    ("Demon Time", "V", "L3  /  R3"),
    ("Heal (Ruby Elixir)", "H", "-"),
    ("Toggle Fullscreen", "F11 / Alt+Enter", "-"),
]

_KEY_FRIENDLY = {
    "left": "Left Arrow",
    "right": "Right Arrow",
    "up": "Up Arrow",
    "down": "Down Arrow",
    "space": "Spacebar",
    "left shift": "Left Shift",
    "right shift": "Right Shift",
    "left ctrl": "Left Ctrl",
    "right ctrl": "Right Ctrl",
    "return": "Enter",
}

_PAD_FRIENDLY = {
    "AXIS_0_MINUS": "Left Stick",
    "AXIS_0_PLUS": "Left Stick",
    "BUTTON_0": "A  /  Cross",
    "BUTTON_1": "B  /  Circle",
    "BUTTON_2": "X  /  Square",
    "BUTTON_3": "Y  /  Triangle",
    "BUTTON_4": "LB  /  L1",
    "BUTTON_5": "RB  /  R1",
    "BUTTON_6": "Back  /  Share",
    "BUTTON_7": "Start  /  Options",
    "BUTTON_8": "L3 (Click Stick)",
    "BUTTON_9": "R3 (Click Stick)",
    "BUTTON_10": "LB  /  L1",
    "BUTTON_11": "RB  /  R1",
}


def _fmt_key(raw: str) -> str:
    low = str(raw).strip().lower()
    return _KEY_FRIENDLY.get(low, low.upper() if len(low) <= 2 else low.title())


def _fmt_pad(raw: str) -> str:
    code = str(raw).strip().upper()
    return _PAD_FRIENDLY.get(code, code.replace("BUTTON_", "Btn "))


class ControlsState(State):
    """Displays player-friendly keyboard and Xbox/PlayStation controller bindings."""

    def __init__(self, manager) -> None:
        super().__init__(manager)
        surf = pg.display.get_surface()
        self.width = surf.get_width() if surf else 1280
        self.height = surf.get_height() if surf else 720

        self.title_font = AssetManager.get_font("assets/font/Abaddon Bold.ttf", 40)
        self.head_font = AssetManager.get_font("assets/font/Abaddon Bold.ttf", 20)
        self.row_font = AssetManager.get_font("assets/font/Abaddon Bold.ttf", 18)

        self.panel_w = int(self.width * 0.78)
        self.panel_h = int(self.height * 0.84)
        self.panel_rect = pg.Rect(
            (self.width - self.panel_w) // 2,
            (self.height - self.panel_h) // 2,
            self.panel_w,
            self.panel_h,
        )

        self.bindings = self._load_bindings()
        self.back_rect = pg.Rect(self.width // 2 - 110, self.panel_rect.bottom - 66, 220, 42)
        self.back_hovered = False

    def _load_bindings(self) -> list[tuple[str, str, str]]:
        cfg_path = "game_data/controls_config.json"
        kb_map: dict = {}
        joy_map: dict = {}
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                kb_map = data.get("keyboard_bindings", {}) or {}
                joy_map = data.get("joystick_bindings", {}) or {}
            except Exception:
                pass

        rows: list[tuple[str, str, str]] = []
        # Combine MOVE_LEFT + MOVE_RIGHT into one clean row
        left_k = _fmt_key(kb_map.get("MOVE_LEFT", "left"))
        right_k = _fmt_key(kb_map.get("MOVE_RIGHT", "right"))
        rows.append(("Move Left / Right", f"{left_k} / {right_k}", "Left Stick"))

        for key_id, label in _ACTION_LABELS[1:]:
            k_str = _fmt_key(kb_map.get(key_id, "-")) if key_id in kb_map else "-"
            j_str = _fmt_pad(joy_map.get(key_id, "-")) if key_id in joy_map else "-"
            rows.append((label, k_str, j_str))

        rows.extend(_EXTRA_ROWS)
        return rows

    def _on_back(self) -> None:
        self.manager.pop()

    def handle_event(self, event) -> None:
        if event.type == pg.MOUSEMOTION:
            self.back_hovered = self.back_rect.collidepoint(event.pos)
        elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_rect.collidepoint(event.pos):
                self._on_back()
                return
        if event.type == pg.KEYDOWN and event.key in (pg.K_ESCAPE, pg.K_RETURN, pg.K_SPACE, pg.K_BACKSPACE):
            self._on_back()
        elif event.type == pg.JOYBUTTONDOWN and event.button in (0, 1):
            self._on_back()

    def update(self, dt) -> None:
        pass

    def draw(self, surface) -> None:
        overlay = pg.Surface((self.width, self.height), pg.SRCALPHA)
        overlay.fill((8, 6, 14, 225))
        surface.blit(overlay, (0, 0))

        panel = pg.Surface((self.panel_w, self.panel_h), pg.SRCALPHA)
        panel.fill((18, 14, 26, 245))
        pg.draw.rect(panel, (215, 175, 75, 220), (0, 0, self.panel_w, self.panel_h), width=2, border_radius=12)
        surface.blit(panel, self.panel_rect.topleft)

        title = self.title_font.render("CONTROLS", True, (255, 215, 80))
        surface.blit(title, title.get_rect(center=(self.width // 2, self.panel_rect.top + 42)))

        col1_x = self.panel_rect.left + 48
        col2_x = self.panel_rect.left + int(self.panel_w * 0.40)
        col3_x = self.panel_rect.left + int(self.panel_w * 0.70)
        header_y = self.panel_rect.top + 86

        for hx, htxt in [(col1_x, "ACTION"), (col2_x, "KEYBOARD"), (col3_x, "XBOX / PLAYSTATION")]:
            hs = self.head_font.render(htxt, True, (215, 175, 75))
            surface.blit(hs, (hx, header_y))

        pg.draw.line(
            surface,
            (215, 175, 75),
            (col1_x, header_y + 28),
            (self.panel_rect.right - 48, header_y + 28),
            1,
        )

        y = header_y + 42
        row_h = min(30, max(22, (self.panel_rect.height - 200) // max(1, len(self.bindings))))
        for idx, (act, kb, pad) in enumerate(self.bindings):
            if idx % 2 == 0:
                stripe = pg.Surface((self.panel_w - 84, row_h - 2), pg.SRCALPHA)
                stripe.fill((255, 255, 255, 12))
                surface.blit(stripe, (col1_x - 6, y - 2))
            surface.blit(self.row_font.render(act, True, (235, 225, 200)), (col1_x, y))
            surface.blit(self.row_font.render(kb, True, (180, 215, 245)), (col2_x, y))
            surface.blit(self.row_font.render(pad, True, (200, 190, 170)), (col3_x, y))
            y += row_h

        btn_surf = pg.Surface((self.back_rect.w, self.back_rect.h), pg.SRCALPHA)
        btn_surf.fill((28, 20, 42, 230) if self.back_hovered else (14, 10, 24, 210))
        pg.draw.rect(
            btn_surf,
            (255, 215, 80, 240) if self.back_hovered else (180, 145, 70, 190),
            (0, 0, self.back_rect.w, self.back_rect.h),
            width=2,
            border_radius=8,
        )
        surface.blit(btn_surf, self.back_rect.topleft)
        b_txt = self.head_font.render("BACK  [ESC]", True, (255, 225, 115) if self.back_hovered else (225, 205, 165))
        surface.blit(b_txt, b_txt.get_rect(center=self.back_rect.center))
