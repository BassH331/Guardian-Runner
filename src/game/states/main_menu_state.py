import os
import sys
import math
import threading
import pygame as pg
from v3x_zulfiqar_gideon import State, AssetManager

class MainMenuState(State):
    """Refined Main Menu matching the game's obsidian and gold mythology aesthetic."""

    def __init__(self, manager):
        super().__init__(manager)
        self.width = pg.display.get_surface().get_width()
        self.height = pg.display.get_surface().get_height()

        # Background Animation
        self.frames = []
        self.current_frame_index = 0
        self.frame_timer = 0.0
        self.frame_delay = 80.0  # ms
        self.loading_thread = None
        
        # Start loading in background
        self.loading_progress = 0.0
        self.converted_frames = False
        self.loading_thread = threading.Thread(target=self.load_frames, daemon=True)
        self.loading_thread.start()
        
        # Fallback/Loading placeholder
        self.bg_placeholder = pg.Surface((self.width, self.height))
        self.bg_placeholder.fill((12, 10, 20))

        # ── Ambient Floating Particles (Embers) ──────────────────────────────
        self._particles = [
            {
                "x": float((i * 97) % self.width),
                "y": float((i * 61) % self.height),
                "speed_x": 10.0 + (i % 4) * 6.0,
                "speed_y": -14.0 - (i % 3) * 7.0,
                "size": 2 + (i % 3),
                "alpha_phase": (i * 0.7),
            }
            for i in range(30)
        ]

        # ── Typography & Title ───────────────────────────────────────────────
        self.title_font = AssetManager.get_font(
            "assets/font/Abaddon Bold.ttf", 96
        )
        self.subtitle_font = AssetManager.get_font(
            "assets/font/Abaddon Bold.ttf", 28
        )
        self.prompt_font = AssetManager.get_font(
            "assets/font/Abaddon Bold.ttf", 28
        )

        self.title_text = "GUARDIAN RUNNER"
        self.subtitle_text = "OF THE STAR-FIRE"

        # ── Industry-Standard Interactive Menu Buttons ───────────────────────
        self._menu_font = AssetManager.get_font("assets/font/Abaddon Bold.ttf", 24)
        self._menu_items: list[tuple[str, callable]] = []
        if self._has_resumable_save():
            self._menu_items.append(("CONTINUE", self.continue_game))
        self._menu_items.extend([
            ("NEW GAME", self.start_game),
            ("SETTINGS", self.open_settings),
            ("CONTROLS", self.open_controls),
            ("QUIT", self.exit_game),
        ])
        self.selected_index: int = 0
        self.buttons = []
        self._button_rects: list[pg.Rect] = []
        self._build_menu_layout()
        
        # Input Cooldown & Transition
        self.input_cooldown = 0.4
        self.time_entered: float = 0.0
        self.is_starting: bool = False
        self.pending_route: str = "PLAY"
        self.start_alpha: float = 0.0

    def load_frames(self):
        from v3x_zulfiqar_gideon import SettingsManager
        quality = SettingsManager().get("graphics_quality")
        bg_dir = "assets/graphics/background images/intro_bg"
        try:
            if os.path.exists(bg_dir):
                frame_files = sorted([f for f in os.listdir(bg_dir) if f.endswith(".gif") or f.endswith(".png")])
                if quality == "low":
                    frame_files = frame_files[:1]
                elif quality == "medium":
                    frame_files = frame_files[::4]
                    
                total_frames = len(frame_files)
                loaded_frames = []
                for i, f in enumerate(frame_files):
                    try:
                        img = pg.image.load(os.path.join(bg_dir, f))
                        img = pg.transform.scale(img, (self.width, self.height))
                        loaded_frames.append(img)
                    except Exception as e:
                        print(f"Error loading frame {f}: {e}")
                    
                    self.loading_progress = (i + 1) / max(1, total_frames)
                
                self.frames = loaded_frames
                print(f"Loaded {len(self.frames)} frames in background (Quality: {quality}).")
            else:
                self.loading_progress = 1.0
        except Exception as e:
            print(f"Failed to load background frames: {e}")
            self.loading_progress = 1.0

    def _has_resumable_save(self) -> bool:
        import json
        save_path = "save_data/slot_auto.json"
        if not os.path.exists(save_path):
            return False
        try:
            with open(save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return float(data.get("world_distance", 0.0)) > 10.0
        except Exception:
            return False

    def _build_menu_layout(self) -> None:
        btn_w, btn_h = 300, 44
        gap = 12
        start_y = int(self.height * 0.50)
        x = (self.width - btn_w) // 2
        self._button_rects = [
            pg.Rect(x, start_y + i * (btn_h + gap), btn_w, btn_h)
            for i in range(len(self._menu_items))
        ]

    def _play_nav_sfx(self) -> None:
        if hasattr(self.manager, "audio_manager") and self.manager.audio_manager:
            try:
                self.manager.audio_manager.play_sound("magic_sfx", volume=0.18)
            except Exception:
                pass

    def continue_game(self):
        if not self.is_starting:
            self.pending_route = "CONTINUE"
            self.is_starting = True

    def start_game(self):
        if not self.is_starting:
            self.pending_route = "PLAY"
            self.is_starting = True

    def open_settings(self):
        if self.is_starting:
            return
        from src.game.states.settings_state import SettingsState
        self._play_nav_sfx()
        self.manager.push(SettingsState(self.manager))

    def open_controls(self):
        if self.is_starting:
            return
        from src.game.states.controls_state import ControlsState
        self._play_nav_sfx()
        self.manager.push(ControlsState(self.manager))

    def exit_game(self):
        self.manager.set_router(None)
        pg.quit()
        sys.exit()
        
    def on_enter(self):
        self.time_entered = pg.time.get_ticks() / 1000.0
        self.is_starting = False
        self.start_alpha = 0.0
        if hasattr(self.manager, 'audio_manager') and self.manager.audio_manager:
            self.manager.audio_manager.play_music("background_music", volume=0.5)

    def handle_event(self, event):
        if self.is_starting:
            return

        current_time = pg.time.get_ticks() / 1000.0
        if current_time - self.time_entered <= self.input_cooldown:
            return

        if event.type == pg.MOUSEMOTION:
            for idx, rect in enumerate(self._button_rects):
                if rect.collidepoint(event.pos):
                    self.selected_index = idx
                    break
        elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            for idx, rect in enumerate(self._button_rects):
                if rect.collidepoint(event.pos):
                    self.selected_index = idx
                    self._menu_items[idx][1]()
                    return
        elif event.type == pg.KEYDOWN:
            if event.key in (pg.K_UP, pg.K_w):
                self.selected_index = (self.selected_index - 1) % len(self._menu_items)
                self._play_nav_sfx()
            elif event.key in (pg.K_DOWN, pg.K_s):
                self.selected_index = (self.selected_index + 1) % len(self._menu_items)
                self._play_nav_sfx()
            elif event.key in (pg.K_SPACE, pg.K_RETURN, pg.K_KP_ENTER):
                self._menu_items[self.selected_index][1]()
            elif event.key == pg.K_ESCAPE:
                self.selected_index = len(self._menu_items) - 1
        elif event.type == pg.JOYHATMOTION and event.value[1] != 0:
            step = -1 if event.value[1] > 0 else 1
            self.selected_index = (self.selected_index + step) % len(self._menu_items)
            self._play_nav_sfx()
        elif event.type == pg.JOYBUTTONDOWN and event.button in (0, 1, 6, 7):
            self._menu_items[self.selected_index][1]()

    def update(self, dt):
        dt_sec = dt / 1000.0 if dt > 0.5 else dt

        # Convert frames to display format on main thread when thread finishes
        if self.loading_thread and not self.loading_thread.is_alive() and not self.converted_frames:
            self.frames = [f.convert() for f in self.frames]
            self.converted_frames = True

        # Update Background Animation
        if self.frames:
            self.frame_timer += dt
            if self.frame_timer >= self.frame_delay:
                self.frame_timer = 0.0
                self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)

        # Update floating particles
        for p in self._particles:
            p["x"] += p["speed_x"] * dt_sec
            p["y"] += p["speed_y"] * dt_sec
            if p["x"] > self.width + 10:
                p["x"] = -10
            if p["y"] < -10:
                p["y"] = float(self.height + 10)

        for btn in self.buttons:
            btn.update(dt)

        # Transition to StoryState / GameState
        if self.is_starting:
            self.start_alpha += 480.0 * dt_sec
            if self.start_alpha >= 255.0:
                self.finish(self.pending_route)

    def draw(self, surface):
        if self.frames:
            surface.blit(self.frames[self.current_frame_index], (0, 0))
        else:
            surface.blit(self.bg_placeholder, (0, 0))
            
        # Dark atmospheric overlay
        vignette = pg.Surface((self.width, self.height), pg.SRCALPHA)
        vignette.fill((8, 6, 14, 140))
        surface.blit(vignette, (0, 0))

        # Floating ambient embers
        ticks = pg.time.get_ticks()
        for p in self._particles:
            p_pulse = (math.sin(ticks * 0.005 + p["alpha_phase"]) + 1.0) * 0.5
            p_alpha = int(100 + 110 * p_pulse)
            glow = pg.Surface((14, 14), pg.SRCALPHA)
            pg.draw.circle(glow, (255, 180, 40, int(p_alpha * 0.45)), (7, 7), 6)
            pg.draw.circle(glow, (255, 220, 100, p_alpha), (7, 7), p["size"])
            surface.blit(glow, (int(p["x"]) - 7, int(p["y"]) - 7))

        # ── Render Title Banner with Gold Typography ─────────────────────────
        title_cx = self.width // 2
        title_cy = int(self.height * 0.24)

        # Title Drop Shadow
        shd_surf = self.title_font.render(self.title_text, True, (0, 0, 0))
        surface.blit(shd_surf, shd_surf.get_rect(center=(title_cx + 4, title_cy + 4)))
        
        # Title Glow & Main Gold Color
        title_surf = self.title_font.render(self.title_text, True, (255, 215, 80))
        surface.blit(title_surf, title_surf.get_rect(center=(title_cx, title_cy)))

        # Subtitle Tag
        sub_shd = self.subtitle_font.render(self.subtitle_text, True, (0, 0, 0))
        surface.blit(sub_shd, sub_shd.get_rect(center=(title_cx + 2, title_cy + 58)))

        sub_surf = self.subtitle_font.render(self.subtitle_text, True, (210, 180, 120))
        surface.blit(sub_surf, sub_surf.get_rect(center=(title_cx, title_cy + 56)))

        # ── Obsidian & Gold Menu Buttons ─────────────────────────────────────
        pulse = (math.sin(ticks * 0.006) + 1.0) * 0.5
        for idx, ((label, _), rect) in enumerate(zip(self._menu_items, self._button_rects)):
            is_sel = (idx == self.selected_index)
            plate = pg.Surface((rect.w, rect.h), pg.SRCALPHA)
            bg_alpha = 225 if is_sel else 175
            plate.fill((22, 16, 34, bg_alpha) if is_sel else (10, 8, 18, bg_alpha))
            border_col = (255, 215, 80, int(190 + 65 * pulse)) if is_sel else (130, 105, 60, 140)
            pg.draw.rect(plate, border_col, (0, 0, rect.w, rect.h), width=2 if is_sel else 1, border_radius=8)
            surface.blit(plate, rect.topleft)

            txt_col = (255, 230, 130) if is_sel else (200, 185, 155)
            display_label = f">  {label}  <" if is_sel else label
            l_shd = self._menu_font.render(display_label, True, (0, 0, 0))
            l_txt = self._menu_font.render(display_label, True, txt_col)
            surface.blit(l_shd, l_shd.get_rect(center=(rect.centerx + 2, rect.centery + 2)))
            surface.blit(l_txt, l_txt.get_rect(center=rect.center))

        # Subtle footer hint
        hint_font = AssetManager.get_font("assets/font/Abaddon Bold.ttf", 16)
        hint_surf = hint_font.render("UP/DOWN Select   |   ENTER Confirm   |   F11 Fullscreen", True, (165, 150, 125))
        surface.blit(hint_surf, hint_surf.get_rect(center=(self.width // 2, self.height - 28)))

        # ── Smooth Exit Fade Overlay ─────────────────────────────────────────
        if self.is_starting and self.start_alpha > 0.0:
            fade_surf = pg.Surface((self.width, self.height), pg.SRCALPHA)
            fade_surf.fill((0, 0, 0, int(min(255.0, self.start_alpha))))
            surface.blit(fade_surf, (0, 0))
