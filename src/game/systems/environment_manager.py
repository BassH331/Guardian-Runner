"""
Environment Manager  -  Data-driven manager for game backgrounds, sky layers, ground,
animated props, environmental storytelling landmarks, and audio themes.
"""

from __future__ import annotations

import os
import math
from typing import List, Dict, Any, Optional, Tuple
import pygame as pg

from v3x_zulfiqar_gideon import AssetManager, Sky


class ParallaxLayer:
    """Represents a single parallax background layer with flexible stretch, scale, and offset controls."""

    def __init__(
        self,
        texture_path: str,
        screen_width: int,
        screen_height: int,
        scroll_ratio: float = 0.2,
        repeat_x: bool = True,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        stretch_fill: bool = False,
        pos_y_offset: int = 0,
    ) -> None:
        self.texture_path = texture_path
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.scroll_ratio = scroll_ratio
        self.repeat_x = repeat_x
        self.scale_x = scale_x
        self.scale_y = scale_y
        self.stretch_fill = stretch_fill
        self.pos_y_offset = pos_y_offset

        raw_texture = AssetManager.get_texture(texture_path)
        if stretch_fill:
            target_width = max(1, int(screen_width * scale_x))
            target_height = max(1, int(screen_height * scale_y))
        else:
            aspect_ratio = raw_texture.get_width() / float(raw_texture.get_height())
            target_height = max(1, int(screen_height * scale_y))
            target_width = max(screen_width, int(target_height * aspect_ratio * scale_x))

        self.image = pg.transform.smoothscale(raw_texture, (target_width, target_height))
        self.width = self.image.get_width()
        self.height = self.image.get_height()

        self.x1: float = 0.0
        self.x2: float = float(self.width)

    def update(self, player_speed: float, dt: float) -> None:
        speed = player_speed * self.scroll_ratio
        self.x1 -= speed * dt
        self.x2 -= speed * dt

        if speed >= 0:
            if self.x1 <= -self.width:
                self.x1 = self.x2 + self.width
            if self.x2 <= -self.width:
                self.x2 = self.x1 + self.width
        else:
            if self.x1 >= self.width:
                self.x1 = self.x2 - self.width
            if self.x2 >= self.width:
                self.x2 = self.x1 - self.width

    def draw(self, surface: pg.Surface, cam_x: Optional[float] = None, cam_y: float = 0.0) -> None:
        if self.stretch_fill:
            y_pos = int(self.pos_y_offset - cam_y * self.scroll_ratio)
        else:
            y_pos = (self.screen_height - self.height) + int(self.pos_y_offset - cam_y * self.scroll_ratio)

        # Synchronize parallax position with camera distance if cam_x is provided
        if cam_x is not None and self.width > 0:
            offset = (cam_x * self.scroll_ratio) % self.width
            self.x1 = -offset
            self.x2 = self.x1 + self.width

        surface.blit(self.image, (int(self.x1), y_pos))
        if self.repeat_x:
            surface.blit(self.image, (int(self.x2), y_pos))
            leftmost = min(self.x1, self.x2)
            rightmost = max(self.x1, self.x2) + self.width
            if leftmost > 0:
                surface.blit(self.image, (int(leftmost - self.width), y_pos))
            if rightmost < self.screen_width:
                surface.blit(self.image, (int(rightmost), y_pos))


class EnvironmentProp:
    """Represents a sliced prop, animated landmark, or tileset object placed into the environment."""

    # Known multi-frame grid sprite sheets: lowercase filename -> (cols, rows)
    SPRITESHEET_GRIDS: Dict[str, Tuple[int, int]] = {
        "large skull.png": (10, 4),
        "memento mori skeleton.png": (4, 4),
    }

    def __init__(
        self,
        texture_path: str,
        slice_rect: Optional[List[int]] = None,  # [x, y, w, h]
        pos_x: float = 0.0,
        pos_y: float = 0.0,
        scale: float = 1.0,
        layer_index: int = 4,  # Layer Depth Index
        parallax_ratio: float = 1.0,
        flip_x: bool = False,
        flip_y: bool = False,
        is_ground: Optional[bool] = None,
        collision_type: str = "deco",  # "solid", "platform", "deco", "hazard"
        collision_offset_y: float = 0.0,
        in_front: Optional[bool] = None,
        anim_speed: float = 0.1,
        anim_grid: Optional[List[int]] = None,  # [cols, rows] or [cols, rows, frame_count]
        trap_hp: float = 0.0,
        trap_loop_frames: int = 0,
        trap_hazard_range: Optional[List[int]] = None,
        trap_telegraph_range: Optional[List[int]] = None,
        trap_reward_souls: int = 0,
        lore_id: Optional[str] = None,
        lore_title: Optional[str] = None,
        lore_text: Optional[str] = None,
        corruption_low: Optional[str] = None,
        corruption_high: Optional[str] = None,
        glow_color: Optional[List[int]] = None,
        proximity_radius: float = 0.0,
        ambient_sfx: Optional[str] = None,
    ) -> None:
        self.texture_path = texture_path
        self.slice_rect = slice_rect
        self.pos_x = pos_x
        self.pos_y = pos_y
        self.scale = scale
        self.layer_index = layer_index
        self.parallax_ratio = parallax_ratio
        self.flip_x = flip_x
        self.flip_y = flip_y
        self.collision_type = collision_type
        self.is_ground = (collision_type in ("solid", "platform")) if is_ground is None else bool(is_ground)
        self.collision_offset_y = collision_offset_y
        self.in_front = in_front
        self.anim_speed = float(anim_speed) if anim_speed else 0.1
        self.anim_grid = list(anim_grid) if anim_grid else None
        self.trap_max_hp = float(trap_hp) if trap_hp else 0.0
        self.trap_hp = self.trap_max_hp
        self.trap_loop_frames = int(trap_loop_frames) if trap_loop_frames else 0
        self.trap_hazard_range = list(trap_hazard_range) if trap_hazard_range else None
        self.trap_telegraph_range = list(trap_telegraph_range) if trap_telegraph_range else None
        self.trap_reward_souls = int(trap_reward_souls) if trap_reward_souls else 0
        self.trap_state: str = "active"  # "active" -> "dissolving" -> "destroyed"
        self._trap_hurt_flash: float = 0.0
        self._ground_scorch_heat: float = 0.0
        self._fire_sparks: List[Dict[str, float]] = []
        self._spark_spawn_accum: float = 0.0
        self.anim_timer = 0.0
        self.frame_idx = 0
        self.frames: List[pg.Surface] = []
        self._frame_paths: List[str] = []

        # Environmental storytelling & atmosphere metadata
        self.lore_id = lore_id
        self.lore_title = lore_title
        self.lore_text = lore_text
        self.corruption_low = corruption_low
        self.corruption_high = corruption_high
        self.glow_color = glow_color
        self.proximity_radius = float(proximity_radius) if proximity_radius else 0.0
        self.ambient_sfx = ambient_sfx
        self._lore_triggered: bool = False
        self._pulse_clock: float = float((int(pos_x) % 100) * 0.07)

        tex_lower = (texture_path or "").lower()
        self._is_fire_prop: bool = ("fireplace" in tex_lower or "torch" in tex_lower or "fire" in tex_lower)

        # Automatic frame sequence detection for animated props (e.g. fire/torch frames)
        if texture_path:
            parent_dir = os.path.dirname(texture_path)
            base_name = os.path.basename(texture_path)
            if parent_dir and os.path.isdir(parent_dir):
                candidates = sorted([
                    os.path.join(parent_dir, f).replace("\\", "/")
                    for f in os.listdir(parent_dir)
                    if f.lower().endswith(".png")
                ])
                if len(candidates) > 1 and ("frame_" in base_name.lower() or parent_dir.endswith("_frames")):
                    self._frame_paths = candidates

        self.rebuild_frames()

    def _transform_surface(self, sub_surf: pg.Surface) -> pg.Surface:
        """Apply configured flip and scale transformations to a frame surface."""
        if self.flip_x or self.flip_y:
            sub_surf = pg.transform.flip(sub_surf, self.flip_x, self.flip_y)

        if self.scale != 1.0:
            target_w = max(1, int(sub_surf.get_width() * self.scale))
            target_h = max(1, int(sub_surf.get_height() * self.scale))
            return pg.transform.smoothscale(sub_surf, (target_w, target_h))
        return sub_surf

    def _slice_single_surface(self, raw_tex: pg.Surface, rect_spec: Optional[List[int]]) -> pg.Surface:
        """Subsurface and transform a region of raw_tex."""
        if rect_spec and len(rect_spec) == 4:
            rx, ry, rw, rh = rect_spec
            rx = max(0, min(rx, raw_tex.get_width() - 1))
            ry = max(0, min(ry, raw_tex.get_height() - 1))
            rw = max(1, min(rw, raw_tex.get_width() - rx))
            rh = max(1, min(rh, raw_tex.get_height() - ry))
            sub_surf = raw_tex.subsurface(pg.Rect(rx, ry, rw, rh))
        else:
            sub_surf = raw_tex
        return self._transform_surface(sub_surf)

    def _resolve_spritesheet_grid(self, raw_tex: pg.Surface) -> Optional[Tuple[int, int, int]]:
        """Return (cols, rows, max_frames) if this prop is an animated grid spritesheet."""
        rw, rh = raw_tex.get_size()
        grid = self.anim_grid
        if grid and len(grid) >= 2:
            cols, rows = int(grid[0]), int(grid[1])
            max_frames = int(grid[2]) if len(grid) >= 3 else cols * rows
            if cols >= 1 and rows >= 1 and cols * rows > 1:
                return cols, rows, max_frames

        fname = os.path.basename(self.texture_path or "").lower()
        if fname in self.SPRITESHEET_GRIDS:
            cols, rows = self.SPRITESHEET_GRIDS[fname]
            cell_w = rw // cols
            cell_h = rh // rows
            if cell_w > 0 and cell_h > 0:
                # Only treat as animated sheet if slice_rect fits inside a single cell (or is unset)
                if not self.slice_rect or (
                    len(self.slice_rect) == 4
                    and self.slice_rect[0] + self.slice_rect[2] <= cell_w
                    and self.slice_rect[1] + self.slice_rect[3] <= cell_h
                ):
                    return cols, rows, cols * rows
        return None

    def rebuild_frames(self) -> None:
        """Build or rebuild scaled animation frames and current display surface."""
        self.frames = []
        if self._frame_paths:
            for fp in self._frame_paths:
                try:
                    tex = AssetManager.get_texture(fp)
                    if tex and tex.get_width() > 0 and tex.get_height() > 0:
                        self.frames.append(self._slice_single_surface(tex, self.slice_rect))
                except Exception:
                    pass

        if not self.frames:
            raw_texture = AssetManager.get_texture(self.texture_path)
            grid_info = self._resolve_spritesheet_grid(raw_texture)
            if grid_info is not None:
                cols, rows, max_frames = grid_info
                tw, th = raw_texture.get_size()
                cell_w = max(1, tw // cols)
                cell_h = max(1, th // rows)
                sub_rx, sub_ry, sub_rw, sub_rh = 0, 0, cell_w, cell_h
                if self.slice_rect and len(self.slice_rect) == 4:
                    rx, ry, rw_s, rh_s = self.slice_rect
                    if 0 <= rx and 0 <= ry and rx + rw_s <= cell_w and ry + rh_s <= cell_h:
                        sub_rx, sub_ry, sub_rw, sub_rh = rx, ry, rw_s, rh_s

                count = 0
                for r in range(rows):
                    for c in range(cols):
                        if count >= max_frames:
                            break
                        fx = c * cell_w + sub_rx
                        fy = r * cell_h + sub_ry
                        cell_rect = pg.Rect(fx, fy, min(sub_rw, tw - fx), min(sub_rh, th - fy))
                        cell_sub = raw_texture.subsurface(cell_rect)
                        if cell_sub.get_bounding_rect().width > 0:
                            self.frames.append(self._transform_surface(cell_sub))
                        count += 1

        if self.frames:
            self.frame_idx = self.frame_idx % len(self.frames)
            self.image = self.frames[self.frame_idx]
        else:
            raw_texture = AssetManager.get_texture(self.texture_path)
            self.image = self._slice_single_surface(raw_texture, self.slice_rect)

        self.width = self.image.get_width()
        self.height = self.image.get_height()

    def set_scale(self, new_scale: float) -> None:
        """Update prop scale and rebuild all animation frames cleanly."""
        self.scale = max(0.2, float(new_scale))
        self.rebuild_frames()

    def is_destructible_trap(self) -> bool:
        """Return True if this prop can currently be struck and banished in combat."""
        return self.trap_max_hp > 0.0 and self.trap_state == "active"

    def is_hazard_active(self) -> bool:
        """Return True when this hazard prop's damaging window is active."""
        if self.collision_type != "hazard" or self.trap_state != "active":
            return False
        if self.trap_hazard_range and len(self.trap_hazard_range) >= 2:
            return int(self.trap_hazard_range[0]) <= self.frame_idx <= int(self.trap_hazard_range[1])
        return True

    def is_telegraph_active(self) -> bool:
        """Return True right before the hazard eruption fires."""
        if self.trap_state != "active":
            return False
        if self.trap_telegraph_range and len(self.trap_telegraph_range) >= 2:
            return int(self.trap_telegraph_range[0]) <= self.frame_idx <= int(self.trap_telegraph_range[1])
        return False

    def get_world_hitbox(self, cam_x: float = 0.0) -> pg.Rect:
        """Return screen-space hitbox tightened around the visible core of the prop."""
        draw_x = int(self.pos_x - cam_x * self.parallax_ratio)
        draw_y = int(self.pos_y)
        if self.anim_grid or os.path.basename(self.texture_path or "").lower() in self.SPRITESHEET_GRIDS:
            pad_x = int(self.width * 0.22)
            pad_top = int(self.height * 0.08)
            pad_bot = int(self.height * 0.06)
            return pg.Rect(
                draw_x + pad_x,
                draw_y + pad_top,
                max(12, self.width - pad_x * 2),
                max(12, self.height - pad_top - pad_bot),
            )
        return pg.Rect(draw_x, draw_y, self.width, self.height)

    def take_trap_damage(self, amount: float) -> bool:
        """Apply damage to a destructible trap prop. Returns True if newly banished."""
        if not self.is_destructible_trap() or amount <= 0:
            return False
        self.trap_hp = max(0.0, self.trap_hp - float(amount))
        self._trap_hurt_flash = 0.16
        if self.trap_hp <= 0.0:
            self.trap_state = "dissolving"
            if self.trap_loop_frames > 0 and self.trap_loop_frames < len(self.frames):
                self.frame_idx = self.trap_loop_frames
            else:
                self.frame_idx = 0
            self.anim_timer = 0.0
            if self.frames:
                self.image = self.frames[self.frame_idx]
            return True
        return False

    def update(self, dt: float = 0.0) -> None:
        """Advance animated prop frame sequence, trap state machine, and pulse timer."""
        if dt > 0:
            self._pulse_clock += dt
        if self._trap_hurt_flash > 0.0 and dt > 0:
            self._trap_hurt_flash = max(0.0, self._trap_hurt_flash - dt)

        if self.trap_state == "destroyed":
            return

        # Simulate ground-impact fire heat, lateral bouncing sparks, and rising ash wisps
        is_eruption = self.is_hazard_active()
        is_telegraph = self.is_telegraph_active()
        if dt > 0 and self.trap_max_hp > 0:
            target_heat = 1.0 if is_eruption else (0.45 if is_telegraph else 0.12)
            lerp_rate = 8.0 if target_heat > self._ground_scorch_heat else 1.8
            self._ground_scorch_heat += (target_heat - self._ground_scorch_heat) * min(1.0, dt * lerp_rate)

            if is_eruption or is_telegraph:
                spawn_hz = 48.0 if is_eruption else 14.0
                self._spark_spawn_accum += dt * spawn_hz
                while self._spark_spawn_accum >= 1.0 and len(self._fire_sparks) < 70:
                    self._spark_spawn_accum -= 1.0
                    seed = math.sin(self._pulse_clock * 31.7 + len(self._fire_sparks) * 1.91)
                    seed2 = math.cos(self._pulse_clock * 19.3 + len(self._fire_sparks) * 2.37)
                    is_smoke = (len(self._fire_sparks) % 5 == 0)
                    spread = self.width * (0.34 if is_eruption else 0.18)
                    dir_sign = 1.0 if seed >= 0 else -1.0
                    self._fire_sparks.append({
                        "ox": seed * spread * 0.45,
                        "oy": -4.0 + abs(seed2) * 10.0,
                        "vx": dir_sign * (45.0 + abs(seed2) * (170.0 if is_eruption else 65.0)),
                        "vy": -(55.0 + abs(seed) * (135.0 if is_eruption else 60.0)),
                        "life": 0.0,
                        "max_life": 0.45 + abs(seed2) * 0.55,
                        "size": 2.0 + abs(seed) * (4.0 if is_smoke else 2.5),
                        "smoke": 1.0 if is_smoke else 0.0,
                    })

            if self._fire_sparks:
                alive_sparks: List[Dict[str, float]] = []
                for sp in self._fire_sparks:
                    sp["life"] += dt
                    if sp["life"] >= sp["max_life"]:
                        continue
                    if sp["smoke"] > 0.5:
                        sp["vx"] *= max(0.0, 1.0 - 1.5 * dt)
                        sp["vy"] -= 25.0 * dt  # smoke rises softly
                    else:
                        sp["vy"] += 380.0 * dt  # sparks arc & bounce off dirt
                    sp["ox"] += sp["vx"] * dt
                    sp["oy"] += sp["vy"] * dt
                    if sp["smoke"] < 0.5 and sp["oy"] > 12.0:
                        sp["oy"] = 12.0
                        sp["vy"] = -abs(sp["vy"]) * 0.42
                        sp["vx"] *= 0.72
                    alive_sparks.append(sp)
                self._fire_sparks = alive_sparks

        if len(self.frames) > 1 and dt > 0:
            self.anim_timer += dt
            if self.anim_timer >= self.anim_speed:
                steps = int(self.anim_timer / self.anim_speed)
                self.anim_timer -= steps * self.anim_speed
                if self.trap_state == "dissolving":
                    next_idx = self.frame_idx + steps
                    if next_idx >= len(self.frames):
                        self.trap_state = "destroyed"
                        return
                    self.frame_idx = next_idx
                else:
                    loop_len = (
                        self.trap_loop_frames
                        if (0 < self.trap_loop_frames <= len(self.frames))
                        else len(self.frames)
                    )
                    self.frame_idx = (self.frame_idx + steps) % loop_len
                self.image = self.frames[self.frame_idx]

    def is_in_front(self) -> bool:
        """Determines if prop renders in foreground in front of player and entities."""
        if self.in_front is not None:
            return bool(self.in_front)
        return self.layer_index >= 7

    def draw(self, surface: pg.Surface, cam_x: float = 0.0, cam_y: float = 0.0) -> None:
        if self.trap_state == "destroyed":
            return

        draw_x = int(self.pos_x - cam_x * self.parallax_ratio)
        draw_y = int(self.pos_y - cam_y)
        sw, sh = surface.get_size()
        if draw_x + self.width < -60 or draw_x > sw + 60 or draw_y + self.height < -60 or draw_y > sh + 60:
            return

        # Render subtle atmospheric glow around interactive lore landmarks, traps, & fire/shrine props
        is_hazard_eruption = self.is_hazard_active()
        is_telegraph = self.is_telegraph_active()
        has_aura = (self.glow_color is not None) or bool(self.lore_text) or self._is_fire_prop or is_telegraph or is_hazard_eruption
        if has_aura:
            pulse = (math.sin(self._pulse_clock * 3.2) + 1.0) * 0.5
            if is_hazard_eruption:
                gr, gg, gb = 255, 95, 25
            elif is_telegraph:
                gr, gg, gb = 255, 175, 50
            elif self.glow_color and len(self.glow_color) >= 3:
                gr, gg, gb = int(self.glow_color[0]), int(self.glow_color[1]), int(self.glow_color[2])
            elif self._is_fire_prop:
                gr, gg, gb = 255, 165, 55
            else:
                gr, gg, gb = 140, 195, 255

            radius = max(28, min(125, int(max(self.width, self.height) * (0.58 if is_hazard_eruption else 0.52))))
            aura_size = radius * 2
            aura_surf = pg.Surface((aura_size, aura_size), pg.SRCALPHA)
            outer_alpha = int((45 if is_hazard_eruption else 22) + (35 if is_hazard_eruption else 26) * pulse)
            inner_alpha = int((70 if is_hazard_eruption else 42) + (45 if is_hazard_eruption else 38) * pulse)
            pg.draw.circle(aura_surf, (gr, gg, gb, outer_alpha), (radius, radius), radius)
            pg.draw.circle(aura_surf, (min(255, gr + 30), min(255, gg + 30), min(255, gb + 30), inner_alpha), (radius, radius), int(radius * 0.55))

            cx = draw_x + self.width // 2
            cy = (draw_y + int(self.height * 0.25)) if "torch" in (self.texture_path or "").lower() else (draw_y + int(self.height * 0.58))
            surface.blit(aura_surf, (cx - radius, cy - radius))

        # ── AAA Ground-Impact Fire FX (behind sprite: charred crater + additive floor light) ──
        has_ground_fire = self.trap_max_hp > 0 and (
            self._ground_scorch_heat > 0.02 or is_hazard_eruption or is_telegraph
        )
        if has_ground_fire:
            self._draw_ground_impact_base(surface, draw_x, draw_y, is_hazard_eruption, is_telegraph)

        surface.blit(self.image, (draw_x, draw_y))

        # ── AAA Ground-Impact Fire FX (over seam: rolling ground flame licks & splash sparks) ──
        if has_ground_fire:
            self._draw_ground_impact_foreground(surface, draw_x, draw_y, is_hazard_eruption, is_telegraph)

        # Strike hit flash for destructible traps
        if self._trap_hurt_flash > 0.0:
            flash_surf = self.image.copy()
            flash_surf.fill((255, 200, 160, 120), special_flags=pg.BLEND_RGBA_ADD)
            surface.blit(flash_surf, (draw_x, draw_y))

        # Compact HP bar above damaged destructible trap
        if self.trap_state == "active" and self.trap_max_hp > 0 and self.trap_hp < self.trap_max_hp:
            bar_w = min(140, max(64, self.width // 2))
            bar_h = 7
            bx = draw_x + (self.width - bar_w) // 2
            by = draw_y + max(0, int(self.height * 0.04)) - 12
            pg.draw.rect(surface, (20, 12, 24), (bx - 1, by - 1, bar_w + 2, bar_h + 2), border_radius=3)
            ratio = max(0.0, min(1.0, self.trap_hp / self.trap_max_hp))
            pg.draw.rect(surface, (235, 65, 45), (bx, by, int(bar_w * ratio), bar_h), border_radius=2)

        # Procedural flickering flame crown for Standing Torches that only have a static post sprite
        if "standing torch" in (self.texture_path or "").lower() and len(self.frames) <= 1:
            flicker = math.sin(self._pulse_clock * 9.5) * 2.5
            flame_x = draw_x + self.width // 2 + int(flicker * 0.4)
            flame_y = draw_y + max(4, int(self.height * 0.08))
            flame_surf = pg.Surface((28, 28), pg.SRCALPHA)
            pg.draw.circle(flame_surf, (255, 120, 20, 150), (14, 14), int(10 + abs(flicker)))
            pg.draw.circle(flame_surf, (255, 210, 70, 220), (14, 14), 6)
            pg.draw.circle(flame_surf, (255, 250, 200, 245), (14, 14), 3)
            surface.blit(flame_surf, (flame_x - 14, flame_y - 14))

    def _draw_ground_impact_base(
        self,
        surface: pg.Surface,
        draw_x: int,
        draw_y: int,
        is_eruption: bool,
        is_telegraph: bool,
    ) -> None:
        """Render pixel-matched charred ash bed, cracked embers, and soft additive light on dirt."""
        cx = draw_x + self.width // 2
        gy = draw_y + self.height
        heat = max(self._ground_scorch_heat, 0.9 if is_eruption else (0.45 if is_telegraph else 0.12))
        pulse = (math.sin(self._pulse_clock * 11.0) + 1.0) * 0.5

        # 1. Soft quadratic radial additive light spill (feathers smoothly to 0 at edge -> zero hard ellipse rim)
        if heat > 0.18:
            lw_g = 64
            lh_g = 18
            low_glow = pg.Surface((lw_g, lh_g), pg.SRCALPHA)
            gcx, gcy = lw_g * 0.5, lh_g * 0.5
            for y in range(lh_g):
                dy = (y - gcy) / max(1.0, lh_g * 0.48)
                for x in range(lw_g):
                    dx = (x - gcx) / max(1.0, lw_g * 0.48)
                    d2 = dx * dx + dy * dy
                    if d2 >= 1.0:
                        continue
                    falloff = (1.0 - d2) ** 2.2
                    a = int(min(130, 125 * falloff * heat * (0.85 + 0.15 * pulse)))
                    if a > 1:
                        low_glow.set_at((x, y), (245, int(90 + 95 * falloff), int(15 + 30 * falloff), a))
            target_glow_w = int(self.width * 1.45)
            target_glow_h = 88
            scaled_glow = pg.transform.smoothscale(low_glow, (target_glow_w, target_glow_h))
            surface.blit(scaled_glow, (cx - target_glow_w // 2, gy - target_glow_h // 2 + 2), special_flags=pg.BLEND_RGBA_ADD)

        # 2. Pixel-grid (1/3 scale -> 3x upscale) irregular charred dirt crater & glowing ember veins
        px_scale = max(2, int(round(self.scale)))
        lw = max(32, int(self.width * 1.08) // px_scale)
        lh = 14
        low_bed = pg.Surface((lw, lh), pg.SRCALPHA)
        cy_l = lh // 2
        cx_l = lw // 2
        for x in range(lw):
            nx = (x - cx_l) / float(max(1, lw * 0.48))
            if abs(nx) > 1.0:
                continue
            noise = math.sin(x * 0.75 + 1.3) * 0.18 + math.cos(x * 1.9) * 0.12
            span_y = max(1, int((1.0 - nx * nx + noise) * (lh * 0.42)))
            for y in range(max(0, cy_l - span_y), min(lh, cy_l + span_y + 1)):
                dy_n = abs(y - cy_l) / float(max(1, span_y))
                edge_fade = max(0.0, 1.0 - (nx * nx * 0.7 + dy_n * dy_n * 0.7))
                if edge_fade <= 0.05:
                    continue
                # Dark soot footprint on dirt
                soot_a = int(min(185, (45 + 115 * heat) * edge_fade))
                low_bed.set_at((x, y), (18, 11, 10, soot_a))
                # Glowing magma cracks inside core of scorched dirt
                if heat > 0.25 and edge_fade > 0.38 and ((x * 7 + y * 13) % 11 in (0, 3)):
                    glow_a = int(min(220, 190 * heat * edge_fade * (0.7 + 0.3 * pulse)))
                    low_bed.set_at((x, y), (245, 105 + int(85 * pulse), 25, glow_a))

        scaled_bed = pg.transform.scale(low_bed, (lw * px_scale, lh * px_scale))
        surface.blit(scaled_bed, (cx - (lw * px_scale) // 2, gy - (lh * px_scale) // 2 + 4))

    def _draw_ground_impact_foreground(
        self,
        surface: pg.Surface,
        draw_x: int,
        draw_y: int,
        is_eruption: bool,
        is_telegraph: bool,
    ) -> None:
        """Mask flat tile seam with pixel-matched flame splashes, ground-crawling embers & sparks."""
        cx = draw_x + self.width // 2
        gy = draw_y + self.height
        px_scale = max(2, int(round(self.scale)))

        # 1. Pixel-art asymmetric flame splash skirt (3x nearest-neighbor scaled to match sprite!)
        if is_eruption or is_telegraph or self._ground_scorch_heat > 0.28:
            strength = 1.0 if is_eruption else max(0.32, self._ground_scorch_heat)
            lw = max(36, int(self.width * 0.96) // px_scale)
            lh = 16
            skirt = pg.Surface((lw, lh), pg.SRCALPHA)
            base_row = 7
            t = self._pulse_clock
            for x in range(lw):
                nx = (x - lw * 0.5) / float(max(1, lw * 0.46))
                if abs(nx) > 1.02:
                    continue
                envelope = max(0.0, 1.0 - nx * nx * 0.85)
                # Multi-frequency asymmetric turbulence so flame heights never repeat uniformly
                w1 = math.sin(x * 0.42 + t * 13.5)
                w2 = math.cos(x * 0.95 - t * 18.0)
                w3 = math.sin(x * 1.73 + t * 9.0)
                up_h = int(max(0, (envelope * 5.2 + w1 * 1.6 + w2 * 1.1) * strength))
                down_h = int(max(1, (envelope * 3.0 + abs(w3) * 1.8) * strength))
                for y in range(max(0, base_row - up_h), min(lh, base_row + down_h + 1)):
                    rel_h = (base_row + down_h - y) / float(max(1, up_h + down_h))
                    edge_dist = min(y - (base_row - up_h), (base_row + down_h) - y)
                    if edge_dist == 0 and ((x + int(t * 24)) % 3 == 0):
                        continue  # ragged pixel edge dissolve
                    if rel_h < 0.28 and envelope > 0.45 and is_eruption:
                        col = (255, 245, 165, int(215 * strength))
                    elif rel_h < 0.58:
                        col = (255, 175, 40, int(195 * strength))
                    else:
                        col = (225, 72, 18, int(155 * strength))
                    skirt.set_at((x, y), col)

            scaled_skirt = pg.transform.scale(skirt, (lw * px_scale, lh * px_scale))
            surface.blit(scaled_skirt, (cx - (lw * px_scale) // 2, gy - base_row * px_scale))

        # 2. Pixel-crisp bouncing sparks and soft rising ash/smoke puffs
        for sp in self._fire_sparks:
            life_ratio = max(0.0, min(1.0, sp["life"] / sp["max_life"]))
            sx = int(cx + sp["ox"])
            sy = int(gy + sp["oy"])
            alpha = int(235 * (1.0 - life_ratio))
            if alpha <= 8:
                continue
            if sp["smoke"] > 0.5:
                rad = max(3, int(sp["size"] * (1.2 + life_ratio * 1.4)))
                sm_s = pg.Surface((rad * 2 + 2, rad * 2 + 2), pg.SRCALPHA)
                pg.draw.circle(sm_s, (28, 18, 16, int(alpha * 0.42)), (rad + 1, rad + 1), rad)
                surface.blit(sm_s, (sx - rad - 1, sy - rad - 1))
            else:
                sz = max(2, int(sp["size"] * (1.0 - life_ratio * 0.45)))
                col = (255, 240, 155, alpha) if life_ratio < 0.35 else (255, 115, 25, alpha)
                sp_s = pg.Surface((sz + 4, sz + 4), pg.SRCALPHA)
                sp_s.fill((255, 85, 15, int(alpha * 0.35)))
                pg.draw.rect(sp_s, col, (2, 2, sz, sz))
                surface.blit(sp_s, (sx - 2, sy - 2))

    @staticmethod
    def auto_detect_offset_y(surface: pg.Surface) -> float:
        """Scan surface rows top to bottom for the first row with solid alpha pixel density."""
        w, h = surface.get_size()
        for y in range(h):
            solid_count = sum(1 for x in range(w) if surface.get_at((x, y)).a > 50)
            if solid_count >= max(3, int(w * 0.35)):
                return float(y)
        return 0.0

    def auto_detect_collision_offset(self) -> float:
        """Auto-detect top solid surface row for this prop's image."""
        if hasattr(self, "image") and self.image:
            self.collision_offset_y = EnvironmentProp.auto_detect_offset_y(self.image)
        return self.collision_offset_y

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "texture_path": self.texture_path,
            "slice_rect": self.slice_rect,
            "pos_x": self.pos_x,
            "pos_y": self.pos_y,
            "scale": self.scale,
            "layer_index": self.layer_index,
            "parallax_ratio": self.parallax_ratio,
            "flip_x": self.flip_x,
            "flip_y": self.flip_y,
            "is_ground": self.is_ground,
            "collision_type": self.collision_type,
            "collision_offset_y": self.collision_offset_y,
            "in_front": self.is_in_front(),
        }
        if self.anim_grid:
            data["anim_grid"] = list(self.anim_grid)
        if self.anim_speed != 0.1 or self.anim_grid:
            data["anim_speed"] = self.anim_speed
        if self.trap_max_hp > 0:
            data["trap_hp"] = self.trap_max_hp
        if self.trap_loop_frames > 0:
            data["trap_loop_frames"] = self.trap_loop_frames
        if self.trap_hazard_range:
            data["trap_hazard_range"] = list(self.trap_hazard_range)
        if self.trap_telegraph_range:
            data["trap_telegraph_range"] = list(self.trap_telegraph_range)
        if self.trap_reward_souls > 0:
            data["trap_reward_souls"] = self.trap_reward_souls
        if self.lore_id:
            data["lore_id"] = self.lore_id
        if self.lore_title:
            data["lore_title"] = self.lore_title
        if self.lore_text:
            data["lore_text"] = self.lore_text
        if self.corruption_low:
            data["corruption_low"] = self.corruption_low
        if self.corruption_high:
            data["corruption_high"] = self.corruption_high
        if self.glow_color:
            data["glow_color"] = self.glow_color
        if self.proximity_radius > 0:
            data["proximity_radius"] = self.proximity_radius
        if self.ambient_sfx:
            data["ambient_sfx"] = self.ambient_sfx
        return data


DEFAULT_LAYER_NAMES = {
    1: "L1: Sky & Far Parallax",
    2: "L2: Mid-Background",
    3: "L3: Ground & Terrain",
    4: "L4: Props & Objects",
    5: "L5: Foreground Foliage"
}

DEFAULT_SCROLL_RATIOS = {
    1: 0.05,
    2: 0.20,
    3: 1.00,
    4: 1.00,
    5: 1.20
}


class EnvironmentManager:
    """Manages dynamic environment layers, sky, parallax backgrounds, stretch modes, and depth-ordered props."""

    def __init__(self, screen_width: int = 1280, screen_height: int = 720, env_config: Optional[Dict[str, Any]] = None) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.parallax_layers: List[ParallaxLayer] = []
        self.layer_stacks: Dict[int, Dict[str, Any]] = {}
        self.props: List[EnvironmentProp] = []
        self.sky: Optional[Sky] = None
        self.bg_music_track: str = "game_loop"
        self.ground_y: int = 686
        self.config: Dict[str, Any] = {}

        # Per-frame ground Y cache: quantized X range -> computed ground Y
        self._ground_y_cache: Dict[Tuple[int, int, bool], Optional[float]] = {}

        self._init_empty_layer_stacks()

        if env_config:
            self.load_config(env_config)
        else:
            self._load_defaults()

    def _init_empty_layer_stacks(self) -> None:
        """Initialize 5 default layer stacks with default ratios."""
        self.layer_stacks = {}
        for l_idx in range(1, 6):
            self.layer_stacks[l_idx] = {
                "name": DEFAULT_LAYER_NAMES[l_idx],
                "texture_path": "",
                "parallax_layer": None,
                "scroll_ratio": DEFAULT_SCROLL_RATIOS[l_idx],
                "repeat_x": True,
                "scale_x": 1.0,
                "scale_y": 1.0,
                "stretch_fill": False,
                "pos_y_offset": 0,
                "visible": True
            }

    def add_layer(self) -> int:
        """Appends a new dynamic layer stack and returns the new layer index."""
        max_idx = max(self.layer_stacks.keys(), default=0)
        new_idx = max_idx + 1
        default_ratio = 1.00
        self.layer_stacks[new_idx] = {
            "name": f"L{new_idx}: Ground & Objects L{new_idx}",
            "texture_path": "",
            "parallax_layer": None,
            "scroll_ratio": default_ratio,
            "repeat_x": True,
            "scale_x": 1.0,
            "scale_y": 1.0,
            "stretch_fill": False,
            "pos_y_offset": 0,
            "visible": True
        }
        return new_idx

    def delete_layer(self, layer_idx: int) -> bool:
        """Deletes a layer stack and removes props on that layer if more than 1 layer exists."""
        if len(self.layer_stacks) <= 1 or layer_idx not in self.layer_stacks:
            return False
        del self.layer_stacks[layer_idx]
        self.props = [p for p in self.props if p.layer_index != layer_idx]
        return True

    def set_layer_texture(
        self,
        layer_idx: int,
        texture_path: str,
        scroll_ratio: Optional[float] = None,
        scale_x: Optional[float] = None,
        scale_y: Optional[float] = None,
        stretch_fill: Optional[bool] = None,
        pos_y_offset: Optional[int] = None,
    ) -> None:
        """Assigns or updates a parallax background texture for a specific layer index."""
        if layer_idx not in self.layer_stacks:
            self.layer_stacks[layer_idx] = {
                "name": f"L{layer_idx}: Layer {layer_idx}",
                "texture_path": "",
                "parallax_layer": None,
                "scroll_ratio": scroll_ratio if scroll_ratio is not None else 0.5,
                "repeat_x": True,
                "scale_x": 1.0,
                "scale_y": 1.0,
                "stretch_fill": False,
                "pos_y_offset": 0,
                "visible": True
            }

        stack = self.layer_stacks[layer_idx]
        stack["texture_path"] = texture_path
        if scroll_ratio is not None:
            stack["scroll_ratio"] = scroll_ratio
        if scale_x is not None:
            stack["scale_x"] = scale_x
        if scale_y is not None:
            stack["scale_y"] = scale_y
        if stretch_fill is not None:
            stack["stretch_fill"] = stretch_fill
        if pos_y_offset is not None:
            stack["pos_y_offset"] = pos_y_offset

        if texture_path and os.path.exists(texture_path):
            stack["parallax_layer"] = ParallaxLayer(
                texture_path,
                self.screen_width,
                self.screen_height,
                scroll_ratio=stack["scroll_ratio"],
                repeat_x=stack.get("repeat_x", True),
                scale_x=stack.get("scale_x", 1.0),
                scale_y=stack.get("scale_y", 1.0),
                stretch_fill=stack.get("stretch_fill", False),
                pos_y_offset=stack.get("pos_y_offset", 0)
            )
        else:
            stack["parallax_layer"] = None

    def clear_layer_texture(self, layer_idx: int) -> None:
        """Clears the background texture for a specific layer index."""
        if layer_idx in self.layer_stacks:
            self.layer_stacks[layer_idx]["texture_path"] = ""
            self.layer_stacks[layer_idx]["parallax_layer"] = None
        if layer_idx == 1:
            self.sky = None

    def toggle_sky(self, enable: Optional[bool] = None) -> None:
        """Toggles or sets the sky/moon background overlay on/off."""
        if enable is None:
            enable = (self.sky is None)
        if enable:
            self._load_default_sky()
        else:
            self.sky = None

    def _load_default_sky(self) -> None:
        sky_paths = [f"assets/graphics/Clouds 3/{i}.png" for i in range(1, 5)]
        sky_speeds = [0, 0, 20, 40]
        valid_paths = [p for p in sky_paths if os.path.exists(p)]
        if valid_paths:
            self.sky = Sky(self.screen_width, self.screen_height, layer_paths=valid_paths, speeds=sky_speeds[:len(valid_paths)])

    def _load_defaults(self) -> None:
        self._load_default_sky()
        bg_path = "assets/graphics/background images/new_bg_images/bg_image.png"
        if os.path.exists(bg_path):
            self.set_layer_texture(1, bg_path, scroll_ratio=0.10)

    def load_config(self, env_config: Dict[str, Any]) -> None:
        """Parses level JSON environment configuration dictionary."""
        self.config = env_config
        self.parallax_layers.clear()
        self.props.clear()
        self._init_empty_layer_stacks()

        self.bg_music_track = env_config.get("bg_music_track", "game_loop")
        self.ground_y = env_config.get("ground_y", 686)

        # 1. Sky Configuration
        sky_cfg = env_config.get("sky")
        if sky_cfg is not None:
            if isinstance(sky_cfg, dict) and not sky_cfg.get("enabled", True):
                self.sky = None
            else:
                layers = sky_cfg.get("layers", []) if isinstance(sky_cfg, dict) else []
                if layers:
                    valid_paths = []
                    speeds = []
                    for item in layers:
                        path = item.get("path") if isinstance(item, dict) else item
                        speed = item.get("speed", 20) if isinstance(item, dict) else 20
                        if path and os.path.exists(path):
                            valid_paths.append(path)
                            speeds.append(speed)
                    if valid_paths:
                        self.sky = Sky(self.screen_width, self.screen_height, layer_paths=valid_paths, speeds=speeds)
                    else:
                        self.sky = None
                else:
                    self.sky = None
        else:
            if not env_config:
                self._load_default_sky()
            else:
                self.sky = None

        # 2. Layer Stacks Configuration
        saved_stacks = env_config.get("layer_stacks", {})
        if saved_stacks:
            for str_k, sdata in saved_stacks.items():
                try:
                    l_idx = int(str_k)
                    if l_idx not in self.layer_stacks:
                        self.layer_stacks[l_idx] = {
                            "name": sdata.get("name", f"L{l_idx}: Layer {l_idx}"),
                            "texture_path": "",
                            "parallax_layer": None,
                            "scroll_ratio": DEFAULT_SCROLL_RATIOS.get(l_idx, 0.5),
                            "repeat_x": True,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                            "stretch_fill": False,
                            "pos_y_offset": 0,
                            "visible": True
                        }
                    
                    tpath = sdata.get("texture_path", "")
                    sratio = sdata.get("scroll_ratio", DEFAULT_SCROLL_RATIOS.get(l_idx, 0.5))
                    rx = sdata.get("repeat_x", True)
                    sx = sdata.get("scale_x", 1.0)
                    sy = sdata.get("scale_y", 1.0)
                    sf = sdata.get("stretch_fill", False)
                    pyo = sdata.get("pos_y_offset", 0)
                    vis = sdata.get("visible", True)

                    self.layer_stacks[l_idx]["scroll_ratio"] = sratio
                    self.layer_stacks[l_idx]["repeat_x"] = rx
                    self.layer_stacks[l_idx]["scale_x"] = sx
                    self.layer_stacks[l_idx]["scale_y"] = sy
                    self.layer_stacks[l_idx]["stretch_fill"] = sf
                    self.layer_stacks[l_idx]["pos_y_offset"] = pyo
                    self.layer_stacks[l_idx]["visible"] = vis
                    if tpath:
                        self.set_layer_texture(l_idx, tpath, scroll_ratio=sratio, scale_x=sx, scale_y=sy, stretch_fill=sf, pos_y_offset=pyo)
                except Exception:
                    pass
        else:
            parallax_cfg = env_config.get("parallax_layers", [])
            for idx, layer_info in enumerate(parallax_cfg):
                path = layer_info.get("path")
                if path and os.path.exists(path):
                    ratio = layer_info.get("scroll_ratio", 0.1)
                    l_target = idx + 1
                    self.set_layer_texture(l_target, path, scroll_ratio=ratio)

        # 3. Environment Props
        for pdata in env_config.get("props", []):
            try:
                col_type = pdata.get("collision_type", "deco")
                is_grd = pdata.get("is_ground")
                if is_grd is None:
                    is_grd = (col_type in ("solid", "platform"))
                self.props.append(EnvironmentProp(
                    texture_path=pdata["texture_path"],
                    slice_rect=pdata.get("slice_rect"),
                    pos_x=pdata.get("pos_x", 0.0),
                    pos_y=pdata.get("pos_y", 0.0),
                    scale=pdata.get("scale", 1.0),
                    layer_index=pdata.get("layer_index", 4),
                    parallax_ratio=pdata.get("parallax_ratio", 1.0),
                    flip_x=pdata.get("flip_x", False),
                    flip_y=pdata.get("flip_y", False),
                    is_ground=is_grd,
                    collision_type=col_type,
                    collision_offset_y=pdata.get("collision_offset_y", 0.0),
                    in_front=pdata.get("in_front", pdata.get("is_foreground", None)),
                    anim_speed=pdata.get("anim_speed", 0.1),
                    anim_grid=pdata.get("anim_grid"),
                    trap_hp=pdata.get("trap_hp", 0.0),
                    trap_loop_frames=pdata.get("trap_loop_frames", 0),
                    trap_hazard_range=pdata.get("trap_hazard_range"),
                    trap_telegraph_range=pdata.get("trap_telegraph_range"),
                    trap_reward_souls=pdata.get("trap_reward_souls", 0),
                    lore_id=pdata.get("lore_id"),
                    lore_title=pdata.get("lore_title"),
                    lore_text=pdata.get("lore_text"),
                    corruption_low=pdata.get("corruption_low"),
                    corruption_high=pdata.get("corruption_high"),
                    glow_color=pdata.get("glow_color"),
                    proximity_radius=pdata.get("proximity_radius", 0.0),
                    ambient_sfx=pdata.get("ambient_sfx"),
                ))
            except Exception:
                pass

    def check_prop_story_triggers(self, player_world_x: float, corruption: float = 0.0) -> List[Dict[str, Any]]:
        """Evaluate proximity of player_world_x against untriggered story props.

        Returns a list of triggered lore payload dicts so GameState can display
        memory whispers and play spatial audio cues.
        """
        triggered: List[Dict[str, Any]] = []
        for prop in self.props:
            if prop._lore_triggered or not prop.lore_text:
                continue
            radius = prop.proximity_radius if prop.proximity_radius > 0 else 180.0
            # Convert prop's pos_x into world distance space using its parallax_ratio
            effective_ratio = prop.parallax_ratio if prop.parallax_ratio > 0 else 1.0
            prop_world_center = (prop.pos_x + prop.width * 0.5) / effective_ratio
            if abs(player_world_x - prop_world_center) <= radius:
                prop._lore_triggered = True
                base_text = prop.lore_text
                if corruption >= 50.0 and prop.corruption_high:
                    full_text = f"{base_text} {prop.corruption_high}"
                elif corruption < 50.0 and prop.corruption_low:
                    full_text = f"{base_text} {prop.corruption_low}"
                else:
                    full_text = base_text

                triggered.append({
                    "lore_id": prop.lore_id or f"prop_{int(prop.pos_x)}",
                    "title": prop.lore_title or "Echo of the Fallen",
                    "text": full_text,
                    "ambient_sfx": prop.ambient_sfx,
                    "is_fire": prop._is_fire_prop,
                })
        return triggered

    def get_ground_y_at(
        self,
        x: float | tuple[float, float] | list[float],
        fallback_to_default: bool = True,
        current_y: Optional[float] = None,
    ) -> Optional[float]:
        """Returns the top Y of the highest solid ground prop at world position x."""
        if isinstance(x, (tuple, list)):
            x_min, x_max = float(x[0]), float(x[1])
        else:
            x_min, x_max = float(x), float(x)

        cy_bucket = int(current_y) // 32 if current_y is not None else -1
        cache_key = (int(x_min) // 32, int(x_max) // 32, fallback_to_default, cy_bucket)
        if cache_key in self._ground_y_cache:
            return self._ground_y_cache[cache_key]

        solid_ys = []
        for prop in self.props:
            if getattr(prop, "is_ground", False) and getattr(prop, "collision_type", "deco") in ("solid", "platform"):
                if getattr(prop, "parallax_ratio", 1.0) != 1.0 or prop.layer_index not in (3, 4, 6):
                    continue
                px = prop.pos_x
                pw = prop.width
                if max(px, x_min) <= min(px + pw, x_max):
                    offset_y = getattr(prop, "collision_offset_y", 0.0)
                    surf_y = prop.pos_y + offset_y
                    if current_y is not None:
                        if surf_y >= current_y - 32.0:
                            solid_ys.append(surf_y)
                    else:
                        solid_ys.append(surf_y)

        res: Optional[float] = float(min(solid_ys)) if solid_ys else (float(self.ground_y) if fallback_to_default else None)
        self._ground_y_cache[cache_key] = res
        return res

    def update(self, dt: float, player_speed: float = 0.0) -> None:
        """Update sky and background parallax layers across all layer stacks."""
        self._ground_y_cache.clear()
        if self.sky:
            self.sky.update(dt)
        for stack in self.layer_stacks.values():
            player_layer = stack.get("parallax_layer")
            if player_layer and stack.get("visible", True):
                player_layer.update(player_speed, dt)
        for prop in self.props:
            prop.update(dt)

    def draw(
        self,
        surface: pg.Surface,
        cam_x: float = 0.0,
        cam_y: float = 0.0,
        min_layer: Optional[int] = None,
        max_layer: Optional[int] = None,
        clear_bg: bool = True,
        foreground_pass: Optional[bool] = None,
    ) -> None:
        """Draw sky followed by explicit layers in strict back-to-front depth order."""
        if foreground_pass is True:
            clear_bg = False
            if min_layer is None:
                min_layer = 7
        elif foreground_pass is False:
            if max_layer is None:
                max_layer = 6

        if clear_bg and (min_layer is None or min_layer <= 1):
            surface.fill((20, 20, 32))
            if self.sky:
                self.sky.draw(surface)

        props_by_layer: dict[int, list[EnvironmentProp]] = {}
        for prop in self.props:
            if foreground_pass is True and not prop.is_in_front():
                continue
            if foreground_pass is False and prop.is_in_front():
                continue
            props_by_layer.setdefault(prop.layer_index, []).append(prop)

        all_indices = sorted(set(self.layer_stacks.keys()) | set(props_by_layer.keys()))
        if min_layer is not None or max_layer is not None:
            active_indices = [
                idx for idx in all_indices
                if (min_layer is None or idx >= min_layer) and (max_layer is None or idx <= max_layer)
            ]
        else:
            active_indices = all_indices

        for l_idx in active_indices:
            stack = self.layer_stacks.get(l_idx)
            is_visible = stack.get("visible", True) if stack else True
            if not is_visible:
                continue

            if stack:
                player_layer = stack.get("parallax_layer")
                if player_layer:
                    player_layer.draw(surface, cam_x=cam_x, cam_y=cam_y)

            for prop in props_by_layer.get(l_idx, []):
                prop.draw(surface, cam_x=cam_x, cam_y=cam_y)

    def to_config_dict(self) -> Dict[str, Any]:
        """Exports current environment configuration dictionary for saving."""
        serialized_stacks = {}
        legacy_parallax = []
        for l_idx, stack in self.layer_stacks.items():
            serialized_stacks[str(l_idx)] = {
                "name": stack["name"],
                "texture_path": stack["texture_path"],
                "scroll_ratio": stack["scroll_ratio"],
                "repeat_x": stack["repeat_x"],
                "scale_x": stack.get("scale_x", 1.0),
                "scale_y": stack.get("scale_y", 1.0),
                "stretch_fill": stack.get("stretch_fill", False),
                "pos_y_offset": stack.get("pos_y_offset", 0),
                "visible": stack.get("visible", True)
            }
            if stack["texture_path"]:
                legacy_parallax.append({
                    "path": stack["texture_path"],
                    "scroll_ratio": stack["scroll_ratio"],
                    "repeat_x": stack["repeat_x"]
                })

        sky_layers = [
            {"path": f"assets/graphics/Clouds 3/{i}.png", "speed": s}
            for i, s in zip(range(1, 5), [0, 0, 20, 40])
            if os.path.exists(f"assets/graphics/Clouds 3/{i}.png")
        ] if self.sky else []

        return {
            "bg_music_track": self.bg_music_track,
            "ground_y": self.ground_y,
            "sky": {"enabled": self.sky is not None, "layers": sky_layers},
            "layer_stacks": serialized_stacks,
            "parallax_layers": legacy_parallax,
            "props": [p.to_dict() for p in self.props]
        }

    @staticmethod
    def get_environment_folders() -> List[Dict[str, Any]]:
        """Discovers all valid environment asset subfolders under assets/graphics."""
        exclude_keywords = [
            "250 WARRIOR ICONS", "MAGE ICONS", "free-undead-loot", "icon", "ICONS",
            "font", "KEYS", "UI", "ui", "PS4", "PC", "Gamepad", "gdb-gamepad",
            "Player", "player", "skeleton", "Goblin", "Wizard_NPC", "Necromancer",
            "DarkFantasyEnemies", "Monsters", "audio", "Sound", "VFX", "PIPOYA",
            "Explosion", "MiniBlood", "blood", "shadow_warrior", "Moon_knight"
        ]
        folders: List[Dict[str, Any]] = []
        base_dir = "assets/graphics"
        if os.path.exists(base_dir):
            for root, _, files in os.walk(base_dir):
                if any(ex.lower() in root.lower() for ex in exclude_keywords):
                    continue
                png_files = [f for f in files if f.lower().endswith((".png", ".jpg", ".jpeg"))]
                if png_files:
                    rel_dir = os.path.relpath(root).replace("\\", "/")
                    name = os.path.basename(rel_dir) or rel_dir
                    folders.append({
                        "name": name,
                        "path": rel_dir,
                        "count": len(png_files)
                    })
        return sorted(folders, key=lambda x: str(x["name"]))

    @staticmethod
    def get_available_background_packs(search_dir: str = "assets/graphics/background images") -> List[str]:
        """Discovers all available background PNG images under background images root."""
        results: List[str] = []
        if not os.path.exists(search_dir):
            return results

        for root, _, files in os.walk(search_dir):
            for file in files:
                if file.lower().endswith((".png", ".jpg", ".jpeg")):
                    rel_path = os.path.relpath(os.path.join(root, file)).replace("\\", "/")
                    results.append(rel_path)

        return sorted(results)

    @classmethod
    def get_background_thumbnails(cls, folder_path: Optional[str] = None, thumb_w: int = 160, thumb_h: int = 90) -> List[Dict[str, Any]]:
        """Returns image thumbnails for a specific folder path or all environment background packs."""
        if folder_path and os.path.exists(folder_path) and os.path.isdir(folder_path):
            files = [os.path.join(folder_path, f).replace("\\", "/") for f in sorted(os.listdir(folder_path)) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
        else:
            files = cls.get_available_background_packs()

        thumbnails: List[Dict[str, Any]] = []
        for path in files:
            try:
                tex = AssetManager.get_texture(path)
                scaled = pg.transform.smoothscale(tex, (thumb_w, thumb_h))
                name = os.path.basename(path)
                parent = os.path.basename(os.path.dirname(path))
                label = f"{parent}/{name}" if parent else name
                thumbnails.append({
                    "path": path,
                    "name": label,
                    "folder": os.path.dirname(path).replace("\\", "/"),
                    "surface": scaled
                })
            except Exception:
                pass
        return thumbnails
