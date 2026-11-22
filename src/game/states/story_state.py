"""
Prologue Story State  -  Atmospheric scene with NPC-style dialogue presentation.

Presents the core story premise ("The Cycle of Vessels") using the established
in-game dialogue aesthetic: dark translucent slate, luminous gold typography,
atmospheric backdrop, multi-beat narrative progression, and pulsing continue prompt.
"""

from __future__ import annotations

import math
import os
from typing import Optional
import pygame as pg

from v3x_zulfiqar_gideon import State, AssetManager
from src.game.ui.animated_dialogue_renderer import AnimatedDialogueRenderer
from src.game.audio.voiceover_manager import VoiceoverManager


class StoryState(State):
    """Atmospheric prologue state displaying the core pitch in NPC-dialogue style."""

    _PROLOGUE_TEXT = (
        "Beneath the Elderwood lies the Oathstone - the prison holding Andras, "
        "Marquis of Discord, behind the Watch's Star-Fire Seal. When the seal cracked, "
        "the Fourth Vanguard marched in. Only young Dain survived when Garrick shoved him "
        "clear - and Andras burned a mark into his palm. Dain reached the Citadel to warn "
        "the Watch, then turned right back around alone."
    )

    _PROLOGUE_CHAPTERS = [
        (
            "I. THE CITADEL & THE WOUND",
            "Beneath the Elderwood lies the Oathstone - the prison holding Andras, "
            "Marquis of Discord, behind the Watch's Star-Fire Seal. When the seal cracked, "
            "the Fourth Vanguard marched in. With them rode young Dain, already hollowed by "
            "a quiet betrayal at home - carrying a note he was never meant to find.",
        ),
        (
            "II. THE FOUR GATES",
            "Four captains - Vane, Garrick, Solen, and Commander Kaelen - spread along "
            "the road to hold the four Watch-gates. In the ambush, Garrick shoved Dain "
            "clear and bought his breath. Andras let the boy escape, burning his mark "
            "into Dain's palm - knowing only a bitter Watchman can open the Oathstone.",
        ),
        (
            "III. THE RETURN ALONE",
            "Dain reached the Citadel to warn the Watch of what fell in the dark - "
            "then turned right back around alone. Why he walks back into the Elderwood "
            "with his scythe is yours to uncover: out of anger at everything he lost, "
            "or to save his brothers and his people.",
        ),
    ]

    def __init__(
        self,
        manager,
        *args,
        text: Optional[str] = None,
        title: str = "THE CYCLE OF VESSELS",
        **kwargs,
    ):
        super().__init__(manager)
        surf = pg.display.get_surface()
        self.width = surf.get_width() if surf else 1280
        self.height = surf.get_height() if surf else 720

        if text is not None:
            self._chapters = [(title, text)]
        else:
            self._chapters = list(self._PROLOGUE_CHAPTERS)

        self._chapter_index: int = 0
        self.title: str = self._chapters[0][0]
        self.story_text: str = self._chapters[0][1]

        # ── Fonts (Clean, crisp, highly legible pixel fonts matching the title) ──
        self.title_font = AssetManager.get_font(
            "assets/font/Abaddon Bold.ttf",
            36,
        )
        self.font = AssetManager.get_font(
            "assets/font/Abaddon Bold.ttf",
            24,
        )
        self.prompt_font = AssetManager.get_font(
            "assets/font/Abaddon Bold.ttf",
            20,
        )

        # ── Background Art & Parallax ─────────────────────────────────────────
        bg_path = "assets/graphics/Pixel-Art-Battlegrounds/PNG/Battleground3/Bright/jungle_bg.png"
        trees_path = "assets/graphics/Pixel-Art-Battlegrounds/PNG/Battleground3/Bright/trees&bushes.png"
        sky_path = "assets/graphics/Pixel-Art-Battlegrounds/PNG/Battleground3/Bright/sky.png"

        self._sky_img: Optional[pg.Surface] = None
        self._bg_img: Optional[pg.Surface] = None
        self._trees_img: Optional[pg.Surface] = None

        try:
            raw_sky = AssetManager.get_texture(sky_path)
            self._sky_img = pg.transform.smoothscale(raw_sky, (self.width, self.height))
        except Exception:
            pass

        try:
            raw_bg = AssetManager.get_texture(bg_path)
            self._bg_img = pg.transform.smoothscale(raw_bg, (self.width, self.height))
        except Exception:
            pass

        try:
            raw_trees = AssetManager.get_texture(trees_path)
            self._trees_img = pg.transform.smoothscale(raw_trees, (self.width, self.height))
        except Exception:
            pass

        # ── Ambient Ember Particles ──────────────────────────────────────────
        self._particles = [
            {
                "x": float((i * 37) % self.width),
                "y": float(self.height - 180 + (i * 13) % 150),
                "speed_x": 12.0 + (i % 5) * 6.0,
                "speed_y": -15.0 - (i % 4) * 8.0,
                "size": 2 + (i % 3),
                "alpha_phase": (i * 0.7),
            }
            for i in range(35)
        ]

        # ── Dialogue Box Dimensions ──────────────────────────────────────────
        self.box_w = min(1160, self.width - 80)
        self.box_h = 280
        self.box_x = (self.width - self.box_w) // 2
        self.box_y = self.height - self.box_h - 35

        # ── Dialogue Box & Typewriter State ──────────────────────────────────
        self.alpha: float = 0.0
        self.fade_speed: float = 300.0
        self.elapsed: float = 0.0
        self.text_progress: float = 0.0
        self.text_speed: float = 52.0
        self.is_text_complete: bool = False
        self.is_exiting: bool = False
        self.exit_alpha: float = 0.0

        self.anim_renderer = AnimatedDialogueRenderer(
            typing_speed=self.text_speed,
            scale_duration=0.12,
            max_scale=1.08,
            theme="default",
        )
        self.anim_renderer.set_text(self.story_text)

        # Word wrap pre-calculation (box_w - 70 padding)
        self._wrapped_lines: list[str] = self._word_wrap(self.story_text, max_width=self.box_w - 70)
        self._black_overlay = pg.Surface((self.width, self.height), pg.SRCALPHA)

        # Voiceover for prologue narration  -  disabled until WAV assets are recorded.
        self._voiceover = VoiceoverManager()

        # Intro video playback state (active only when text is None and intro.mp4 exists)
        self._allow_video: bool = (text is None)
        self._video_mode: bool = False
        self._video_reader = None
        self._video_size: tuple[int, int] = (1280, 720)
        self._video_fps: float = 24.0
        self._video_accum: float = 0.0
        self._video_surf: Optional[pg.Surface] = None

    def _load_chapter(self, idx: int) -> None:
        """Load the specified prologue chapter into the typewriter renderer."""
        self._chapter_index = max(0, min(idx, len(self._chapters) - 1))
        self.title, self.story_text = self._chapters[self._chapter_index]
        self.text_progress = 0.0
        self.is_text_complete = False
        self.anim_renderer.set_text(self.story_text)
        self._wrapped_lines = self._word_wrap(self.story_text, max_width=self.box_w - 70)
        if hasattr(self.manager, "audio_manager") and self.manager.audio_manager:
            try:
                self.manager.audio_manager.play_sound("magic_sfx", volume=0.25)
            except Exception:
                pass

    def _word_wrap(self, text: str, max_width: int) -> list[str]:
        words = text.split(" ")
        lines: list[str] = []
        curr = ""
        for w in words:
            test = f"{curr} {w}".strip() if curr else w
            if self.font.size(test)[0] <= max_width:
                curr = test
            else:
                if curr:
                    lines.append(curr)
                curr = w
        if curr:
            lines.append(curr)
        return lines

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def on_enter(self):
        self.alpha = 0.0
        self.elapsed = 0.0
        self._chapter_index = 0
        self.title, self.story_text = self._chapters[0]
        self.text_progress = 0.0
        self.is_text_complete = False
        self.is_exiting = False
        self.exit_alpha = 0.0
        self.anim_renderer.set_text(self.story_text)
        if self._start_intro_video():
            return
        if hasattr(self.manager, "audio_manager") and self.manager.audio_manager:
            self.manager.audio_manager.play_music("background_music", volume=0.45)

    def _start_intro_video(self) -> bool:
        video_path = "assets/video/intro.mp4"
        if not self._allow_video or not os.path.exists(video_path) or pg.display.get_surface() is None:
            return False
        try:
            import imageio_ffmpeg
            reader = imageio_ffmpeg.read_frames(video_path)
            meta = next(reader)
            self._video_size = tuple(meta["size"])
            self._video_fps = float(meta.get("fps") or 24.0)
            self._video_reader = reader
            self._video_accum = 0.0
            first_bytes = next(reader, None)
            if first_bytes is None:
                self._stop_intro_video()
                return False
            surf = pg.image.frombuffer(first_bytes, self._video_size, "RGB").convert()
            if surf.get_size() != (self.width, self.height):
                surf = pg.transform.scale(surf, (self.width, self.height))
            self._video_surf = surf
            self._video_mode = True
            audio_path = "assets/video/intro_audio.wav"
            if os.path.exists(audio_path) and pg.mixer.get_init():
                try:
                    pg.mixer.music.load(audio_path)
                    pg.mixer.music.set_volume(0.85)
                    pg.mixer.music.play()
                except Exception:
                    pass
            return True
        except Exception as e:
            print(f"[StoryState] Intro video fallback to chapters: {e}")
            self._stop_intro_video()
            return False

    def _stop_intro_video(self, keep_surface: bool = False) -> None:
        if not keep_surface:
            self._video_mode = False
        if self._video_reader is not None:
            try:
                self._video_reader.close()
            except Exception:
                pass
            self._video_reader = None
        if pg.mixer.get_init():
            try:
                pg.mixer.music.stop()
            except Exception:
                pass

    def on_exit(self):
        self._stop_intro_video()

    # ── Events ───────────────────────────────────────────────────────────────

    def handle_event(self, event: pg.event.Event):
        if self._video_mode:
            skip_pressed = (
                (event.type == pg.KEYDOWN and event.key in (pg.K_RETURN, pg.K_SPACE, pg.K_ESCAPE))
                or (event.type == pg.JOYBUTTONDOWN and event.button in (0, 1, 7))
            )
            if skip_pressed and self.elapsed >= 0.4 and not self.is_exiting:
                self._stop_intro_video(keep_surface=True)
                self.is_exiting = True
            return

        advance_pressed = (
            (event.type == pg.KEYDOWN and event.key in (pg.K_RETURN, pg.K_SPACE, pg.K_e, pg.K_x))
            or (event.type == pg.JOYBUTTONDOWN and event.button in (0, 1, 2, 6, 7))
        )

        if advance_pressed:
            if not self.is_text_complete:
                # First press instantly completes the current chapter's text
                self.anim_renderer.skip_to_end()
                self.text_progress = float(len(self.story_text))
                self.is_text_complete = True
            elif self._chapter_index + 1 < len(self._chapters):
                # Advance to next prologue chapter
                self._load_chapter(self._chapter_index + 1)
            elif not self.is_exiting:
                # Final chapter complete -> transition to cutscene / game
                self.is_exiting = True

    # ── Update ───────────────────────────────────────────────────────────────

    def update(self, dt: float):
        dt_sec = dt / 1000.0 if dt > 0.5 else dt
        self.elapsed += dt_sec

        # Fade in screen
        if self.alpha < 255.0:
            self.alpha = min(255.0, self.alpha + self.fade_speed * dt_sec)

        if self._video_mode:
            if self._video_reader is not None and not self.is_exiting:
                frame_dur = 1.0 / max(1.0, self._video_fps)
                self._video_accum += dt_sec
                while self._video_accum >= frame_dur:
                    self._video_accum -= frame_dur
                    try:
                        raw = next(self._video_reader)
                        surf = pg.image.frombuffer(raw, self._video_size, "RGB").convert()
                        if surf.get_size() != (self.width, self.height):
                            surf = pg.transform.scale(surf, (self.width, self.height))
                        self._video_surf = surf
                    except StopIteration:
                        self._stop_intro_video(keep_surface=True)
                        self.is_exiting = True
                        break
            if self.is_exiting:
                self.exit_alpha += 450.0 * dt_sec
                if self.exit_alpha >= 255.0:
                    self._stop_intro_video(keep_surface=False)
                    self.finish("NEW_GAME")
            return

        # Advance typewriter text
        if not self.is_text_complete:
            self.anim_renderer.update(dt_sec)
            self.text_progress = float(self.anim_renderer.current_char_count)
            if self.anim_renderer.is_complete:
                self.text_progress = float(len(self.story_text))
                self.is_text_complete = True

        # Update ambient embers
        for p in self._particles:
            p["x"] += p["speed_x"] * dt_sec
            p["y"] += p["speed_y"] * dt_sec
            if p["x"] > self.width + 20:
                p["x"] = -20
            if p["y"] < -20:
                p["y"] = float(self.height - 200)

        # Handle exit fade
        if self.is_exiting:
            self.exit_alpha += 450.0 * dt_sec
            if self.exit_alpha >= 255.0:
                self.finish("NEW_GAME")

    # ── Draw ─────────────────────────────────────────────────────────────────

    def draw(self, surface: pg.Surface):
        if self._video_mode and self._video_surf is not None:
            surface.fill((0, 0, 0))
            surface.blit(self._video_surf, (0, 0))
            if self.elapsed >= 0.8:
                skip_str = "[ SPACE / ESC ] SKIP INTRO"
                s_surf = self.prompt_font.render(skip_str, True, (235, 215, 165))
                pad_box = pg.Surface((s_surf.get_width() + 24, s_surf.get_height() + 12), pg.SRCALPHA)
                pad_box.fill((10, 8, 16, 170))
                bx = self.width - pad_box.get_width() - 24
                by = self.height - pad_box.get_height() - 20
                surface.blit(pad_box, (bx, by))
                surface.blit(s_surf, (bx + 12, by + 6))
            if self.is_exiting and self.exit_alpha > 0.0:
                exit_overlay = pg.Surface((self.width, self.height), pg.SRCALPHA)
                exit_overlay.fill((0, 0, 0, int(min(255.0, self.exit_alpha))))
                surface.blit(exit_overlay, (0, 0))
            return

        surface.fill((12, 10, 20))

        # 1. Background Layers with gentle subtle drift
        drift = math.sin(self.elapsed * 0.3) * 6.0
        if self._sky_img:
            surface.blit(self._sky_img, (0, 0))
        if self._bg_img:
            surface.blit(self._bg_img, (int(drift * 0.5), 0))
        if self._trees_img:
            surface.blit(self._trees_img, (int(drift), 0))

        # Dark atmospheric vignette / gradient over top and bottom
        vignette = pg.Surface((self.width, self.height), pg.SRCALPHA)
        vignette.fill((8, 6, 14, 140))
        surface.blit(vignette, (0, 0))

        # 2. Ambient Glowing Particles (Embers / Fireflies)
        ticks = pg.time.get_ticks()
        for p in self._particles:
            p_pulse = (math.sin(ticks * 0.004 + p["alpha_phase"]) + 1.0) * 0.5
            p_alpha = int(120 + 110 * p_pulse)
            glow_surf = pg.Surface((16, 16), pg.SRCALPHA)
            pg.draw.circle(glow_surf, (255, 180, 40, int(p_alpha * 0.4)), (8, 8), 6)
            pg.draw.circle(glow_surf, (255, 220, 100, p_alpha), (8, 8), p["size"])
            surface.blit(glow_surf, (int(p["x"]) - 8, int(p["y"]) - 8))

        # 3. Bottom NPC-Style Dialogue Box
        box_w = self.box_w
        box_h = self.box_h
        box_x = self.box_x
        box_y = self.box_y

        # Obsidian Dark Slate Background with Gold Border
        box_surf = pg.Surface((box_w, box_h), pg.SRCALPHA)
        box_surf.fill((10, 6, 18, 232))
        pg.draw.rect(
            box_surf,
            (255, 190, 50, 200),
            (0, 0, box_w, box_h),
            width=2,
            border_radius=10,
        )
        pg.draw.rect(
            box_surf,
            (120, 80, 20, 90),
            (4, 4, box_w - 8, box_h - 8),
            width=1,
            border_radius=8,
        )
        surface.blit(box_surf, (box_x, box_y))

        # 4. Title Header Tag & Chapter Counter
        title_y = box_y + 18
        title_x = box_x + 35

        t_shd = self.title_font.render(self.title, True, (0, 0, 0))
        surface.blit(t_shd, (title_x + 2, title_y + 2))
        t_surf = self.title_font.render(self.title, True, (255, 205, 70))
        surface.blit(t_surf, (title_x, title_y))

        if len(self._chapters) > 1:
            chap_str = f"MEMORY {self._chapter_index + 1} / {len(self._chapters)}"
            c_surf = self.prompt_font.render(chap_str, True, (180, 150, 210))
            surface.blit(c_surf, (box_x + box_w - c_surf.get_width() - 35, title_y + 8))

        # 5. Typewriter Story Text
        text_start_y = title_y + 48
        text_rect = pg.Rect(box_x + 35, text_start_y, box_w - 70, box_h - 88)
        self.anim_renderer.render(
            surface=surface,
            font=self.font,
            rect=text_rect,
            color=(245, 235, 215),
            shadow_color=(0, 0, 0),
            align="left",
            line_spacing=6,
        )

        # 6. Pulsing Continue Prompt
        if self.is_text_complete:
            p_pulse = (math.sin(ticks * 0.007) + 1.0) * 0.5
            p_alpha = int(140 + 115 * p_pulse)
            is_last = (self._chapter_index + 1 >= len(self._chapters))
            prompt_str = (
                "[ PRESS SPACE OR ENTER TO AWAKEN ]"
                if is_last
                else "[ PRESS SPACE OR ENTER TO CONTINUE ]"
            )

            p_w = self.prompt_font.size(prompt_str)[0]
            px = box_x + box_w - p_w - 30
            py = box_y + box_h - 36

            p_shd = self.prompt_font.render(prompt_str, True, (0, 0, 0))
            p_shd.set_alpha(int(p_alpha * 0.85))
            surface.blit(p_shd, (px + 2, py + 2))

            p_txt = self.prompt_font.render(prompt_str, True, (255, 215, 90))
            p_txt.set_alpha(p_alpha)
            surface.blit(p_txt, (px, py))

        # 7. Cinematic Fade-In / Exit Transition
        if self.alpha < 255.0:
            fade_overlay = pg.Surface((self.width, self.height), pg.SRCALPHA)
            fade_overlay.fill((0, 0, 0, int(255 - self.alpha)))
            surface.blit(fade_overlay, (0, 0))

        if self.is_exiting and self.exit_alpha > 0.0:
            exit_overlay = pg.Surface((self.width, self.height), pg.SRCALPHA)
            exit_overlay.fill((0, 0, 0, int(min(255.0, self.exit_alpha))))
            surface.blit(exit_overlay, (0, 0))
