import os
import math
import re
import pygame as pg
from typing import Dict, Any, Optional, Callable, List
from v3x_zulfiqar_gideon import AssetManager, UITheme
from src.game.systems.custom_events import Speaker


def _natural_sort_key(s: str) -> List[Any]:
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", os.path.basename(s))]


SPEAKER_AVATAR_MAP: Dict[str, str] = {
    "green monster": "assets/graphics/green_monster/idle",
    "the gatekeeper": "assets/graphics/green_monster/idle",
    "gatekeeper": "assets/graphics/green_monster/idle",
    "the iron gatekeeper": "assets/graphics/green_monster/idle",
    "greenmonster": "assets/graphics/green_monster/idle",
    "blood zombie": "assets/graphics/bloodZombie/Idle",
    "bloodzombie": "assets/graphics/bloodZombie/Idle",
    "the fabricator's enforcer": "assets/wizard/Idle",
    "fire wizard": "assets/wizard/Idle",
    "firewizard": "assets/wizard/Idle",
    "wizard": "assets/wizard/Idle",
    "dark ronin": "assets/graphics/Ronin/spr_RoninIdle_strip8.png",
    "darkronin": "assets/graphics/Ronin/spr_RoninIdle_strip8.png",
    "ronin": "assets/graphics/Ronin/spr_RoninIdle_strip8.png",
    "skeleton": "assets/skeleton/Skeleton_01_White_Idle",
    "necromancer": "assets/graphics/Necromancer_creativekind-Sheet.png",
    "andras": "assets/Agis",
    "andras, marquis of discord": "assets/Agis",
    "agis": "assets/Agis",
}


class CinematicNarrativeOverlay:
    """In-game slow-motion cinematic narrative overlay component.
    
    When activated by Kimi AI Director or key story events, combat slows to
    10% speed while a dark radial vignette and floating dialogue box appear with
    typewriter dialogue text and interactive keypress choices ([1] or [2]).
    """

    def __init__(self):
        self.is_active: bool = False
        self._current_event: Optional[Dict[str, Any]] = None
        self._on_choice_selected: Optional[Callable[[Dict[str, Any]], None]] = None
        self._speaker: Optional[Speaker] = None

        # Text animation states
        self._full_text: str = ""
        self._displayed_text: str = ""
        self._char_index: int = 0
        self._char_timer: float = 0.0
        self._CHAR_SPEED_SEC: float = 0.008

        # Avatar animation
        self._avatar_frames: List[pg.Surface] = []
        self._avatar_frame_idx: int = 0
        self._avatar_frame_timer: float = 0.0
        self._AVATAR_FRAME_SPEED: float = 0.28  # seconds per frame (calm, ominous demon pacing)

        # Book Opening Ritual state
        self._is_book_ritual: bool = False
        self._ritual_timer: float = 0.0
        self._ritual_elapsed: float = 0.0
        self._book_image: Optional[pg.Surface] = None
        self._book_frames: List[pg.Surface] = []
        self._runic_text: str = ""

        # Surface & dimension caching
        self._width: int = 1280
        self._height: int = 720
        self._vignette_surface: Optional[pg.Surface] = None
        self._btn1_rect: Optional[pg.Rect] = None
        self._btn2_rect: Optional[pg.Rect] = None
        self._rebuild_vignette()

    def _rebuild_vignette(self) -> None:
        """Create atmospheric dark scrim overlay."""
        surface = pg.display.get_surface()
        if surface:
            self._width = surface.get_width()
            self._height = surface.get_height()

        self._vignette_surface = pg.Surface((self._width, self._height), pg.SRCALPHA)
        # Semi-transparent dark atmospheric scrim (0, 0, 0, 160) for standard dialogue so
        # gameplay world and characters remain visible; deeper dark (0, 0, 0, 240) for book ritual.
        alpha = 240 if getattr(self, "_is_book_ritual", False) else 160
        self._vignette_surface.fill((0, 0, 0, alpha))

    def activate(self, narrative_event: Dict[str, Any], on_choice_selected: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        """Trigger slow-motion cinematic overlay with Kimi narrative event dictionary."""
        surface = pg.display.get_surface()
        if surface:
            self._width = surface.get_width()
            self._height = surface.get_height()

        self._current_event = narrative_event
        self._on_choice_selected = on_choice_selected
        self._full_text = narrative_event.get("dialogue_text", "")
        self._displayed_text = ""
        self._char_index = 0
        self._char_timer = 0.0
        self._avatar_frame_idx = 0
        self._avatar_frame_timer = 0.0
        
        self._avatar_frames = []
        self._book_frames = []
        self._book_image = None
        self._is_book_ritual = bool(narrative_event.get("is_book_ritual", False))
        self._runic_text = str(narrative_event.get("runic_text", ""))
        self._ritual_timer = float(narrative_event.get("duration", 5.0))
        self._ritual_elapsed = 0.0
        self._rebuild_vignette()

        if self._is_book_ritual:
            # Single book image cutscene asset (Magic Books interface / book interface7.png)
            book_img_path = narrative_event.get("book_image_path") or os.path.join(
                "assets", "graphics", "Magic Books interface", "book interface7.png"
            )
            if os.path.exists(book_img_path):
                try:
                    loaded = pg.image.load(book_img_path)
                    if pg.display.get_surface():
                        try:
                            loaded = loaded.convert_alpha()
                        except pg.error:
                            pass
                    # Sharp pixel art integer-scaled rendering (native 100x100 -> 240x240)
                    self._book_image = pg.transform.scale(loaded, (240, 240))
                    self._book_frames = [self._book_image]
                except Exception as e:
                    print(f"[CinematicOverlay] Error loading book image {book_img_path}: {e}")
        else:
            self._AVATAR_FRAME_SPEED = 0.28  # calm demon pacing

        # Resolve avatar sprite path: check event avatar_sprite, else lookup speaker_name in SPEAKER_AVATAR_MAP
        avatar_path = narrative_event.get("avatar_sprite")
        if not avatar_path and not self._is_book_ritual:
            speaker_key = str(narrative_event.get("speaker_name", "")).strip().lower()
            if speaker_key:
                if speaker_key in SPEAKER_AVATAR_MAP:
                    avatar_path = SPEAKER_AVATAR_MAP[speaker_key]
                else:
                    for map_name, map_path in SPEAKER_AVATAR_MAP.items():
                        if map_name in speaker_key or speaker_key in map_name:
                            avatar_path = map_path
                            break
            if not avatar_path and self._speaker is Speaker.ANDRAS:
                avatar_path = SPEAKER_AVATAR_MAP.get("andras")

        if avatar_path and not self._is_book_ritual:
            try:
                resolved_path = os.path.normpath(avatar_path)
                if not os.path.exists(resolved_path) and os.path.exists(os.path.join("assets", resolved_path)):
                    resolved_path = os.path.join("assets", resolved_path)

                raw_frames: List[pg.Surface] = []

                if os.path.isfile(resolved_path) or resolved_path.lower().endswith(".png"):
                    frames = AssetManager.get_animation_frames(resolved_path)
                    if frames:
                        raw_frames = list(frames)
                    else:
                        img = pg.image.load(resolved_path)
                        if pg.display.get_surface():
                            try:
                                img = img.convert_alpha()
                            except pg.error:
                                pass
                        raw_frames = [img]
                elif os.path.isdir(resolved_path):
                    # Check for direct PNG files
                    direct_pngs = sorted(
                        [
                            os.path.join(resolved_path, f)
                            for f in os.listdir(resolved_path)
                            if f.lower().endswith(".png") and os.path.isfile(os.path.join(resolved_path, f))
                        ],
                        key=_natural_sort_key,
                    )

                    if not direct_pngs:
                        # Inspect child subfolders (prioritize 'idle', then any folder with PNGs)
                        subdirs = [
                            os.path.join(resolved_path, d)
                            for d in os.listdir(resolved_path)
                            if os.path.isdir(os.path.join(resolved_path, d))
                        ]

                        target_subfolder = None
                        # Priority 1: exact name 'idle'
                        for d in subdirs:
                            if os.path.basename(d).lower() == "idle":
                                sub_pngs = [
                                    f for f in os.listdir(d)
                                    if f.lower().endswith(".png") and os.path.isfile(os.path.join(d, f))
                                ]
                                if sub_pngs:
                                    target_subfolder = d
                                    break

                        # Priority 2: contains 'idle' in name
                        if not target_subfolder:
                            for d in subdirs:
                                if "idle" in os.path.basename(d).lower():
                                    sub_pngs = [
                                        f for f in os.listdir(d)
                                        if f.lower().endswith(".png") and os.path.isfile(os.path.join(d, f))
                                    ]
                                    if sub_pngs:
                                        target_subfolder = d
                                        break

                        # Priority 3: first child folder containing PNGs
                        if not target_subfolder:
                            for d in subdirs:
                                sub_pngs = [
                                    f for f in os.listdir(d)
                                    if f.lower().endswith(".png") and os.path.isfile(os.path.join(d, f))
                                ]
                                if sub_pngs:
                                    target_subfolder = d
                                    break

                        if target_subfolder:
                            direct_pngs = sorted(
                                [
                                    os.path.join(target_subfolder, f)
                                    for f in os.listdir(target_subfolder)
                                    if f.lower().endswith(".png") and os.path.isfile(os.path.join(target_subfolder, f))
                                ],
                                key=_natural_sort_key,
                            )

                    if direct_pngs:
                        for png_file in direct_pngs:
                            img = pg.image.load(png_file)
                            if pg.display.get_surface():
                                try:
                                    img = img.convert_alpha()
                                except pg.error:
                                    pass
                            raw_frames.append(img)
                    else:
                        # Fallback to AssetManager
                        frames = AssetManager.get_animation_frames(resolved_path)
                        if frames:
                            raw_frames = list(frames)

                # Implement adaptive aspect-preserving scaling
                if raw_frames:
                    card_h = 180
                    card_y = self._height - card_h - 25
                    target_max_w = min(int(self._width * 0.45), 450)
                    target_max_h = min(int(card_y - 40), 400)

                    for f in raw_frames:
                        raw_w = f.get_width()
                        raw_h = f.get_height()
                        if raw_w <= 0 or raw_h <= 0:
                            continue
                        scale = min(target_max_w / raw_w, target_max_h / raw_h)
                        scaled_w = max(1, int(raw_w * scale))
                        scaled_h = max(1, int(raw_h * scale))
                        self._avatar_frames.append(pg.transform.smoothscale(f, (scaled_w, scaled_h)))
            except Exception as e:
                print(f"[CinematicOverlay] Avatar load error: {e}")

        self.is_active = True

    def show_bark(
        self,
        text: str,
        speaker: Optional[Speaker] = None,
        speaker_name: Optional[str] = None,
        avatar_sprite: Optional[str] = None,
    ) -> None:
        """Show a whisperer bark line or boss dialogue line via the overlay."""
        self._speaker = speaker
        event: Dict[str, Any] = {
            "dialogue_text": text,
            "option_1_label": "[SPACE] Continue",
        }
        if speaker_name is not None:
            event["speaker_name"] = speaker_name
        if avatar_sprite is not None:
            event["avatar_sprite"] = avatar_sprite
        self.activate(event)

    def deactivate(self) -> None:
        """Dismiss overlay and restore full game speed."""
        self.is_active = False
        self._current_event = None
        self._on_choice_selected = None
        self._speaker = None
        self._avatar_frames = []
        self._book_frames = []
        self._book_image = None
        self._is_book_ritual = False
        self._ritual_elapsed = 0.0
        self._avatar_frame_idx = 0
        self._rebuild_vignette()

    def handle_event(self, event: pg.event.Event) -> bool:
        """Handle keypresses [1], [2], SPACE, ENTER, ESC, mouse clicks, or gamepad buttons to select story choice."""
        if not self.is_active or not self._current_event:
            return False

        if event.type == pg.KEYDOWN:
            if event.key in (pg.K_1, pg.K_KP1, pg.K_RETURN, pg.K_SPACE, pg.K_ESCAPE):
                self._select_option(1)
                return True
            elif event.key in (pg.K_2, pg.K_KP2) and "option_2_label" in self._current_event:
                self._select_option(2)
                return True
        elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            mpos = event.pos
            if self._btn2_rect and self._btn2_rect.collidepoint(mpos):
                self._select_option(2)
                return True
            elif self._btn1_rect and self._btn1_rect.collidepoint(mpos):
                self._select_option(1)
                return True
            elif "option_2_label" not in self._current_event:
                # In single-option monologue, clicking anywhere advances
                self._select_option(1)
                return True
        elif event.type == pg.JOYBUTTONDOWN:
            if event.button in (0, 2):
                # Gamepad button index 2 (Xbox X) and index 0 (PlayStation Cross/X) advance/skip narrative dialogue
                self._select_option(1)
                return True
            elif event.button in (1, 3) and "option_2_label" in self._current_event:
                # Gamepad button index 1 (B / Circle) or index 3 (Y / Triangle) selects option 2 if present
                self._select_option(2)
                return True
            elif "option_2_label" not in self._current_event and event.button in (1, 6, 7):
                # In single-option monologue / bark, common face and trigger buttons also advance
                self._select_option(1)
                return True
        return False

    def _select_option(self, option_index: int) -> None:
        """Apply selected choice buff and deactivate overlay."""
        if not self._current_event:
            return

        buff_key = f"option_{option_index}_buff"
        buff_data = self._current_event.get(buff_key, {})
        
        callback = self._on_choice_selected
        self.deactivate()

        if callback:
            callback(buff_data)

    def update(self, dt: float) -> None:
        """Update typewriter text animation, avatar/book frame animation, and auto-timers."""
        if not self.is_active:
            return

        # Normalize dt: engine ticks in milliseconds (~16.6ms), while timers operate in seconds
        dt_sec = dt / 1000.0 if dt > 1.0 else dt

        # Book ritual auto-timer & elapsed tracking (advances automatically if user does not press SPACE)
        if self._is_book_ritual:
            self._ritual_elapsed += dt_sec
            if self._ritual_timer > 0.0:
                self._ritual_timer -= dt_sec
                if self._ritual_timer <= 0.0:
                    self._select_option(1)
                    return

        # Typewriter effect
        if self._char_index < len(self._full_text):
            self._char_timer += dt_sec
            while self._char_timer >= self._CHAR_SPEED_SEC and self._char_index < len(self._full_text):
                self._char_timer -= self._CHAR_SPEED_SEC
                self._char_index += 1
                self._displayed_text = self._full_text[:self._char_index]

        # Avatar frame cycling
        if len(self._avatar_frames) > 1:
            self._avatar_frame_timer += dt_sec
            if self._avatar_frame_timer >= self._AVATAR_FRAME_SPEED:
                self._avatar_frame_timer -= self._AVATAR_FRAME_SPEED
                self._avatar_frame_idx = (self._avatar_frame_idx + 1) % len(self._avatar_frames)

    def draw(self, surface: pg.Surface) -> None:
        """Render atmospheric scrim and floating bottom dialogue box."""
        if not self.is_active or not self._current_event:
            return

        if surface:
            self._width = surface.get_width()
            self._height = surface.get_height()

        card_w = int(self._width * 0.85)
        card_h = 180
        card_x = (self._width - card_w) // 2
        card_y = self._height - card_h - 25

        # 1. Draw atmospheric scrim — tinted per speaker when a bark is active
        if self._vignette_surface:
            if self._speaker is Speaker.ANDRAS:
                tint = pg.Surface((self._width, self._height), pg.SRCALPHA)
                tint.fill((60, 0, 10, 160))
                surface.blit(self._vignette_surface, (0, 0))
                surface.blit(tint, (0, 0))
            elif self._speaker is Speaker.MOON_KNIGHT:
                tint = pg.Surface((self._width, self._height), pg.SRCALPHA)
                tint.fill((10, 20, 60, 140))
                surface.blit(self._vignette_surface, (0, 0))
                surface.blit(tint, (0, 0))
            else:
                surface.blit(self._vignette_surface, (0, 0))

        # 1.5 Draw animated Avatar Sprite or Book Opening Ritual in the void
        if self._is_book_ritual and (self._book_image or self._book_frames):
            bframe = self._book_image if self._book_image is not None else self._book_frames[0]
            
            # Levitation oscillation (smooth vertical sine wave float)
            hover_offset = math.sin(self._ritual_elapsed * 2.2) * 8.0
            bx = (self._width - bframe.get_width()) // 2
            by = int((self._height - bframe.get_height()) // 3 - 15 + hover_offset)

            # Multi-layer occult aura behind book:
            # 1. Ethereal purple occult glow with breathing intensity
            glow_pulse = 0.82 + 0.18 * math.sin(self._ritual_elapsed * 2.8)
            glow_w = int((bframe.get_width() + 60) * glow_pulse)
            glow_h = int((bframe.get_height() + 60) * glow_pulse)
            glow_x = (self._width - glow_w) // 2
            glow_y = int(by + (bframe.get_height() - glow_h) // 2)
            glow_surf = pg.Surface((glow_w, glow_h), pg.SRCALPHA)
            pg.draw.ellipse(glow_surf, (130, 45, 230, int(75 * glow_pulse)), glow_surf.get_rect())
            surface.blit(glow_surf, (glow_x, glow_y))

            # 2. Concentrated golden/arcane medallion core aura behind central seal
            core_pulse = 0.75 + 0.25 * math.cos(self._ritual_elapsed * 3.4)
            core_size = int(110 * core_pulse)
            core_x = (self._width - core_size) // 2
            core_y = int(by + (bframe.get_height() - core_size) // 2)
            core_surf = pg.Surface((core_size, core_size), pg.SRCALPHA)
            pg.draw.ellipse(core_surf, (245, 185, 45, int(65 * core_pulse)), core_surf.get_rect())
            surface.blit(core_surf, (core_x, core_y))

            # 3. Rising occult motes / sparks drifting from the open grimoire
            for i in range(7):
                mote_progress = (self._ritual_elapsed * 28.0 + i * 22.0) % 95.0
                mote_x = bx + int(bframe.get_width() * (0.22 + 0.56 * ((i * 47) % 100) / 100.0) + math.sin(self._ritual_elapsed * 2.0 + i * 1.3) * 10.0)
                mote_y = int(by + bframe.get_height() * 0.55 - mote_progress)
                mote_alpha = int(max(0, min(190, 190 * (1.0 - (mote_progress / 95.0)))))
                if mote_alpha > 10:
                    mote_color = (255, 215, 120, mote_alpha) if i % 2 == 0 else (200, 140, 255, mote_alpha)
                    mote_surf = pg.Surface((4, 4), pg.SRCALPHA)
                    mote_surf.fill(mote_color)
                    surface.blit(mote_surf, (mote_x, mote_y))

            # 4. Render the grimoire
            surface.blit(bframe, (bx, by))

            # 5. Render untranslatable runes floating above the book
            if self._runic_text:
                font_runes = None
                for fname in ("segoeuihistoric", "segoeuisymbol", "cambria", "arial"):
                    try:
                        font_runes = pg.font.SysFont(fname, 28)
                        if font_runes:
                            break
                    except Exception:
                        pass
                if not font_runes:
                    font_runes = AssetManager.get_font(None, 28)
                rune_surf = font_runes.render(self._runic_text, True, (225, 185, 255))
                rune_shadow = font_runes.render(self._runic_text, True, (0, 0, 0))
                rx = (self._width - rune_surf.get_width()) // 2
                rune_float = math.sin(self._ritual_elapsed * 2.2 + 0.6) * 4.0
                ry = int(by - 48 + rune_float)
                surface.blit(rune_shadow, (rx + 2, ry + 2))
                surface.blit(rune_surf, (rx, ry))
        elif self._avatar_frames:
            frame = self._avatar_frames[self._avatar_frame_idx % len(self._avatar_frames)]
            av_x = (self._width - frame.get_width()) // 2
            av_y = max(20, (card_y - frame.get_height()) // 2)
            if av_y + frame.get_height() >= card_y:
                av_y = max(0, card_y - frame.get_height() - 5)
            surface.blit(frame, (av_x, av_y))

        # 2. Modern UI Dialogue Panel Base

        # Background with a sleek dark glass look
        card_rect = pg.Rect(card_x, card_y, card_w, card_h)
        pg.draw.rect(surface, (15, 15, 20, 240), card_rect, border_radius=8)
        
        # Subtle inner highlight for 3D depth
        inner_rect = pg.Rect(card_x + 1, card_y + 1, card_w - 2, card_h - 2)
        pg.draw.rect(surface, (45, 45, 55, 180), inner_rect, width=1, border_radius=8)
        
        # Sleek accent border (Gold/Neon)
        pg.draw.rect(surface, (235, 190, 80), card_rect, width=2, border_radius=8)

        # Subtle top accent line (for modern flair)
        top_accent_rect = pg.Rect(card_x + 15, card_y, card_w - 30, 2)
        pg.draw.rect(surface, (255, 215, 110), top_accent_rect)

        # 3. Draw Speaker Tag (Modern Header)
        # When a whisperer bark is active, override the speaker label with a
        # small all-caps coloured label; otherwise use the event's speaker_name.
        if self._speaker is Speaker.ANDRAS:
            speaker_label = "ANDRAS"
            speaker_colour = (200, 30, 30)
        elif self._speaker is Speaker.MOON_KNIGHT:
            speaker_label = "MOON KNIGHT"
            speaker_colour = (120, 160, 220)
        else:
            speaker_label = str(self._current_event.get("speaker_name", "Kimi Narrative Director"))
            speaker_colour = (255, 220, 100)

        if self._speaker is not None:
            # Small all-caps whisperer label (11px) drawn above the standard header position
            font_whisper = AssetManager.get_font(None, 11)
            label_surf = font_whisper.render(speaker_label, True, speaker_colour)
            label_shadow = font_whisper.render(speaker_label, True, (0, 0, 0))
            surface.blit(label_shadow, (card_x + 27, card_y + 7))
            surface.blit(label_surf, (card_x + 25, card_y + 6))
            font_title = AssetManager.get_font(None, 24)
            # Render transparent placeholder for speaker_name slot so layout stays intact
            speaker_shadow_surf = font_title.render("", True, (0, 0, 0))
            surface.blit(speaker_shadow_surf, (card_x + 27, card_y + 17))
        else:
            font_title = AssetManager.get_font(None, 24)
            speaker_surf = font_title.render(speaker_label, True, speaker_colour)
            speaker_shadow_surf = font_title.render(speaker_label, True, (0, 0, 0))
            surface.blit(speaker_shadow_surf, (card_x + 27, card_y + 17))
            surface.blit(speaker_surf, (card_x + 25, card_y + 15))

        # Separator line under speaker
        pg.draw.line(surface, (80, 75, 70), (card_x + 25, card_y + 45), (card_x + card_w - 25, card_y + 45), 1)

        # 4. Draw Typewriter Dialogue Text with Word Wrap
        font_body = AssetManager.get_font(None, 20)
        max_line_width = card_w - 50
        words = self._displayed_text.split(" ")
        lines = []
        cur_line = ""
        for word in words:
            test_line = f"{cur_line} {word}".strip() if cur_line else word
            if font_body.size(test_line)[0] <= max_line_width:
                cur_line = test_line
            else:
                if cur_line:
                    lines.append(cur_line)
                cur_line = word
        if cur_line:
            lines.append(cur_line)

        line_y = card_y + 55
        for line in lines[:3]:
            d_surf = font_body.render(line, True, (240, 240, 245))
            surface.blit(d_surf, (card_x + 25, line_y))
            line_y += 22

        # 5. Draw Modern Interactive Choice Buttons
        opt1 = str(self._current_event.get("option_1_label", "[SPACE] Continue"))

        font_choice = AssetManager.get_font(None, 18)
        
        # Button 1 (Embrace / Affirmative / Continue) - Pill Shape
        btn1_w = font_choice.size(opt1)[0] + 40
        self._btn1_rect = pg.Rect(card_x + 25, card_y + 130, btn1_w, 34)
        pg.draw.rect(surface, (30, 50, 40, 230), self._btn1_rect, border_radius=17)
        pg.draw.rect(surface, (80, 200, 100), self._btn1_rect, width=1, border_radius=17)
        opt1_surf = font_choice.render(opt1, True, (160, 240, 160))
        surface.blit(opt1_surf, (card_x + 45, card_y + 137))

        # Button 2 (Reject / Negative) - Pill Shape (Only if option_2_label exists)
        if "option_2_label" in self._current_event:
            opt2 = str(self._current_event["option_2_label"])
            btn2_w = font_choice.size(opt2)[0] + 40
            self._btn2_rect = pg.Rect(card_x + btn1_w + 45, card_y + 130, btn2_w, 34)
            pg.draw.rect(surface, (50, 25, 30, 230), self._btn2_rect, border_radius=17)
            pg.draw.rect(surface, (220, 80, 80), self._btn2_rect, width=1, border_radius=17)
            opt2_surf = font_choice.render(opt2, True, (240, 150, 150))
            surface.blit(opt2_surf, (card_x + btn1_w + 65, card_y + 137))
        else:
            self._btn2_rect = None
