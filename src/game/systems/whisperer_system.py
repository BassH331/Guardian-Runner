"""
WhispererSystem  -  Reactive bark dialogue for Andras and Moon Knight.

Subscribes to EntityDied, DamageReceived, and RelicDropped events.
Selects the appropriate speaker and bark based on the player's current
corruption level, then fires it to SideNotification (or CinematicNarrativeOverlay).
"""

from __future__ import annotations

import random
import threading
from typing import TYPE_CHECKING, Optional

from src.game.systems.custom_events import Speaker, RelicDropped

if TYPE_CHECKING:
    from v3x_zulfiqar_gideon import EventBus
    from src.game.systems.corruption_manager import CorruptionManager
    from src.game.ui.cinematic_narrative_overlay import CinematicNarrativeOverlay
    from src.game.services.watsonx_dialogue_client import WatsonxDialogueClient


class WhispererSystem:
    """Selects and fires contextual bark lines from Andras and Moon Knight."""

    # Enabled so Andras and the Moon Knight react to psychological milestones
    # via non-blocking SideNotification cards.
    ENABLED: bool = True

    COOLDOWN: float = 55.0  # Calibrated quiet pacing between rare psychological echoes

    def __init__(
        self,
        event_bus: "EventBus",
        corruption_manager: "CorruptionManager",
        config: dict,
        overlay: Optional["CinematicNarrativeOverlay"] = None,
        watsonx_client: Optional["WatsonxDialogueClient"] = None,
        relic_manager=None,
        side_notification=None,
    ) -> None:
        self._event_bus = event_bus
        self._corruption_manager = corruption_manager
        self._barks: dict = config.get("whisperer_barks", {})
        self._boss_dialogue_config: dict = config.get("boss_dialogue", {})
        self._overlay = overlay
        self._watsonx_client = watsonx_client
        self._relic_manager = relic_manager
        self._side_notification = side_notification
        self._cooldown_remaining: float = 0.0

        # Thread-safe slot for watsonx background result
        self._pending_watsonx_bark: Optional[str] = None
        self._pending_lock = threading.Lock()

        # Subscribe to engine and custom events
        from v3x_zulfiqar_gideon.event_bus import EntityDied, DamageReceived
        event_bus.subscribe(EntityDied, self._on_entity_died)
        event_bus.subscribe(DamageReceived, self._on_damage_received)
        event_bus.subscribe(RelicDropped, self._on_relic_dropped)

        # Threshold tracking  -  detect corruption crossing a band boundary
        self._last_threshold: int = self._get_current_threshold()

    # ── Threshold helper ──────────────────────────────────────────────────────

    def _get_current_threshold(self) -> int:
        """Return the current corruption band as a discrete integer marker."""
        v = self._corruption_manager.value
        if v >= 90:
            return 90
        if v >= 66:
            return 66
        if v >= 50:
            return 50
        if v >= 33:
            return 33
        return 0

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_entity_died(self, event) -> None:
        """Suppress random minion-kill popup chatter so combat stays uncluttered."""
        return

    def _on_damage_received(self, event) -> None:
        """Trigger an on_near_death bark when the player drops below 20% HP (high priority)."""
        target = getattr(event, "target", None)
        if target is None:
            return
        from src.game.entities.player import Player
        if not isinstance(target, Player):
            return
        health_remaining = getattr(event, "health_remaining", 100.0)
        max_health = getattr(target, "max_health", 100.0)
        if max_health > 0 and (health_remaining / max_health) < 0.2:
            self._try_bark("on_near_death", force=True)

    def _on_relic_dropped(self, event) -> None:
        """Trigger an on_relic bark when a relic is dropped by a boss (high priority)."""
        self._try_bark("on_relic", force=True)

    # ── Per-frame update ──────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        """Tick the cooldown timer and detect corruption threshold crossings."""
        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= dt

        current = self._get_current_threshold()
        if current != self._last_threshold:
            self._last_threshold = current
            self._try_bark("on_threshold_crossed", force=True)

        # Check for watsonx bark result (set by background thread)
        with self._pending_lock:
            bark = self._pending_watsonx_bark
            self._pending_watsonx_bark = None

        if bark and self._cooldown_remaining <= 0:
            self._fire(Speaker.ANDRAS, bark)

    # ── Public API ────────────────────────────────────────────────────────────

    def notify_boss_spawn(self, boss_name: str) -> None:
        """Called by GameState when a boss spawns."""
        boss_cfg = self._boss_dialogue_config.get(boss_name, {})
        use_watsonx = boss_cfg.get("watsonx_taunt", False) and self._watsonx_client is not None
        if use_watsonx:
            self._request_watsonx_bark(boss_name)
        else:
            self._try_bark("on_boss_spawn", force=True)

    def _request_watsonx_bark(self, boss_name: str) -> None:
        """Requests async Andras dialogue from watsonx. Falls back automatically."""
        corruption = self._corruption_manager.value
        relics = []
        if self._relic_manager is not None and hasattr(self._relic_manager, "collected_ids"):
            relics = list(self._relic_manager.collected_ids())

        def _on_result(text: str) -> None:
            with self._pending_lock:
                self._pending_watsonx_bark = text

        self._watsonx_client.generate_andras_taunt(
            corruption=corruption,
            relics=relics,
            boss_name=boss_name,
            callback=_on_result,
        )

    # ── Internal bark selection ───────────────────────────────────────────────

    def _try_bark(self, trigger: str, force: bool = False) -> None:
        """Attempt to fire a bark for the given trigger."""
        if not force and self._cooldown_remaining > 0:
            return
        corruption = self._corruption_manager.value
        speaker = self._pick_speaker(corruption)
        bark = self._pick_bark(speaker, trigger, corruption)
        if bark is None:
            return
        self._fire(speaker, bark)

    def _pick_speaker(self, corruption: float) -> Speaker:
        """Choose which voice speaks based on the corruption level."""
        if corruption > 60:
            return Speaker.ANDRAS
        if corruption < 40:
            return Speaker.MOON_KNIGHT
        andras_weight = (corruption - 40) / 20.0
        return Speaker.ANDRAS if random.random() < andras_weight else Speaker.MOON_KNIGHT

    def _pick_bark(self, speaker: Speaker, trigger: str, corruption: float) -> Optional[str]:
        """Select a random valid bark text from the pool."""
        speaker_key = "andras" if speaker == Speaker.ANDRAS else "moon_knight"
        pool: list[dict] = self._barks.get(speaker_key, {}).get(trigger, [])
        valid = [
            b["text"]
            for b in pool
            if b["corruption_range"][0] <= corruption <= b["corruption_range"][1]
        ]
        if not valid and pool:
            valid = [b["text"] for b in pool]
        if not valid:
            return None
        return random.choice(valid)

    def _fire(self, speaker: Speaker, text: str) -> None:
        """Display the bark and reset the cooldown."""
        self._cooldown_remaining = self.COOLDOWN
        if not self.ENABLED:
            return
        if getattr(self, "_side_notification", None) is not None:
            speaker_label = "Andras, Marquis of Discord" if speaker == Speaker.ANDRAS else "The Moon Knight (Candora's Envoy)"
            icon = (
                "assets/free-undead-loot-pixel-art-icons/PNG/Transperent/Icon1.png"
                if speaker == Speaker.ANDRAS
                else "assets/graphics/UI/PNG/Exclamation_Yellow.png"
            )
            theme = "blood_bone" if speaker == Speaker.ANDRAS else "arcane_void"
            try:
                self._side_notification.show(text, speaker_label, icon=icon, hold=7.5, theme=theme)
            except TypeError:
                self._side_notification.show(text, speaker_label, icon=icon, hold=7.5)
            return

        if self._overlay is None:
            return
        show_fn = getattr(self._overlay, "show_bark", None)
        if show_fn is not None:
            show_fn(text, speaker=speaker)
        else:
            for method_name in ("show", "trigger", "display", "activate"):
                fn = getattr(self._overlay, method_name, None)
                if fn is not None:
                    try:
                        fn(text, speaker=speaker)
                    except TypeError:
                        fn(text)
                    break
