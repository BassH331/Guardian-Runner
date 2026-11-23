"""
Utility Combat Engine — Action evaluation, combat spacing, whiff punishment, and telemetry adaptation.

Calculates dynamic utility scores for candidate combat actions:
- Tactical Combat Spacing & Retraction: Steps back out of range when player swings.
- Whiff Punishment: Detects player attack recovery frames and triggers counter-attacks.
- Action Scoring: Evaluates distance, player state, attack cooldowns, and stamina.
- Telemetry Heuristic Adaptation: Reads recent telemetry metrics from GameplayTracker
  to dynamically scale enemy combat aggressiveness and reaction urgency.
"""

from __future__ import annotations

import logging
import os
import random
from enum import Enum, auto
from typing import Optional, TYPE_CHECKING
import pygame as pg

from src.game.debug.gameplay_tracker import GameplayTracker

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.game.entities.player import Player


class TacticalAction(Enum):
    IDLE = 0
    CHASE = 10
    ATTACK = 20
    RETRACT_SPACING = 30  # Step back / maintain tactical distance
    PUNISH_WHIFF = 40     # Close in during player recovery
    DASH_EVADE = 50       # Special dash/teleport only for enemies with explicit mobility skills


class UtilityCombatEngine:
    """Evaluates combat situations and selects optimal tactical actions."""

    def __init__(
        self,
        has_dash_evasion: bool = False,
        has_block_anim: bool = False,
        preferred_spacing: float = 65.0,
    ) -> None:
        self.has_dash_evasion: bool = has_dash_evasion
        self.has_block_anim: bool = has_block_anim
        self.preferred_spacing: float = preferred_spacing

        # Heuristic tuning factors (modified by telemetry)
        diff = os.environ.get("AI_DIFFICULTY", "").upper()
        if diff == "NIGHTMARE":
            self.aggression_weight = 1.4
            self.whiff_sensitivity = 2.0
            self.retract_chance = 0.85
        elif diff == "HARD":
            self.aggression_weight = 1.2
            self.whiff_sensitivity = 1.6
            self.retract_chance = 0.70
        elif diff == "EASY":
            self.aggression_weight = 0.8
            self.whiff_sensitivity = 0.9
            self.retract_chance = 0.25
        else:
            self.aggression_weight = 1.0
            self.whiff_sensitivity = 1.2
            self.retract_chance = 0.45

        self._last_telemetry_check_time: float = 0.0
        # Committed posture hysteresis to prevent 60Hz per-frame random twitching
        self._committed_action: Optional[TacticalAction] = None
        self._commit_timer: float = 0.0
        self._retract_cooldown: float = 0.0
        self._spacing_hysteresis: float = 18.0

    def evaluate_action(
        self,
        enemy_rect: pg.Rect,
        player: Optional[Player],
        can_attack: bool,
        has_attack_token: bool,
        dt_sec: float,
    ) -> TacticalAction:
        """Score candidate actions and return a smoothed, committed tactical action."""
        if player is None:
            return TacticalAction.IDLE

        is_dead_val = getattr(player, "is_dead", False)
        if is_dead_val is True:
            return TacticalAction.IDLE

        dt_clamped = max(0.0, min(0.2, float(dt_sec)))
        self._commit_timer = max(0.0, self._commit_timer - dt_clamped)
        self._retract_cooldown = max(0.0, self._retract_cooldown - dt_clamped)

        self._adapt_from_telemetry()

        p_rect = getattr(player, "rect", None)
        px = getattr(p_rect, "centerx", None) if p_rect else None
        py = getattr(p_rect, "centery", None) if p_rect else None

        if not isinstance(px, (int, float)) or not isinstance(py, (int, float)):
            dx = 0.0
            dist_x = 0.0
            dist_y = 0.0
        else:
            dx = float(px) - enemy_rect.centerx
            dist_x = abs(dx)
            dist_y = abs(float(py) - enemy_rect.centery)

        player_is_attacking = (
            getattr(player, "is_attacking", False) is True
            or (callable(getattr(player, "should_deal_damage", None)) and player.should_deal_damage() is True)
        )
        player_is_recovering = (
            getattr(player, "is_recovering", False) is True
            or getattr(player, "in_attack_recovery", False) is True
        )

        # 1. Whiff Punishment Opportunity: Player missed attack and is recovering
        if player_is_recovering and dist_x < (self.preferred_spacing + 40) and dist_y < 120:
            if can_attack and has_attack_token:
                self._commit_timer = 0.0
                self._committed_action = TacticalAction.PUNISH_WHIFF
                logger.debug("[AI TACTICS] WHIFF PUNISHMENT triggered! Player missed swing (recovering) -> Enemy initiating counter-strike!")
                return TacticalAction.PUNISH_WHIFF

        # 2. Attack: Enemy is in range and holds a squad attack token
        if can_attack and has_attack_token and dist_y < 120:
            self._commit_timer = 0.0
            self._committed_action = TacticalAction.ATTACK
            return TacticalAction.ATTACK

        # Hold any committed movement/spacing beat smoothly instead of twitching every 16ms
        if self._commit_timer > 0.0 and self._committed_action is not None:
            if self._committed_action == TacticalAction.RETRACT_SPACING and dist_x < self.preferred_spacing + 75:
                return TacticalAction.RETRACT_SPACING
            if self._committed_action == TacticalAction.IDLE and dist_x <= self.preferred_spacing + self._spacing_hysteresis:
                return TacticalAction.IDLE

        # 3. Retract / Step back: Committed defensive beat when player swings close
        if (
            self._retract_cooldown <= 0.0
            and player_is_attacking
            and dist_x < (self.preferred_spacing + 30)
            and dist_y < 100
        ):
            if self.has_dash_evasion and random.random() < 0.6:
                self._retract_cooldown = 1.6
                logger.debug("[AI TACTICS] DASH EVASION triggered! Player swinging close -> Executing mobility dash.")
                return TacticalAction.DASH_EVADE
            self._retract_cooldown = 1.4
            if random.random() < self.retract_chance:
                self._committed_action = TacticalAction.RETRACT_SPACING
                self._commit_timer = 0.34
                return TacticalAction.RETRACT_SPACING

        # 4. Chase / Maintain Spacing with hysteresis so enemies don't oscillate at boundary
        if not can_attack and dist_x > self.preferred_spacing + (self._spacing_hysteresis * 0.5):
            self._committed_action = TacticalAction.CHASE
            self._commit_timer = 0.18
            return TacticalAction.CHASE

        # If directly crowding inside another attacker's reach without a token, step back briefly
        if not has_attack_token and dist_x < max(24.0, self.preferred_spacing - 20.0) and self._retract_cooldown <= 0.0:
            self._committed_action = TacticalAction.RETRACT_SPACING
            self._commit_timer = 0.30
            self._retract_cooldown = 1.2
            return TacticalAction.RETRACT_SPACING

        self._committed_action = TacticalAction.IDLE
        self._commit_timer = 0.20
        return TacticalAction.IDLE

    def _adapt_from_telemetry(self) -> None:
        """Periodically inspect GameplayTracker metrics to adjust AI heuristic weights."""
        tracker = GameplayTracker.get_instance()
        if tracker is None or not tracker.enabled:
            return

        # Check telemetry every ~2 seconds
        now = pg.time.get_ticks() / 1000.0
        if now - self._last_telemetry_check_time < 2.0:
            return
        self._last_telemetry_check_time = now

        # Read telemetry summary metrics if available
        metrics = getattr(tracker, "session_metrics", {})
        if metrics:
            player_hit_rate = metrics.get("player_accuracy", 0.5)
            player_aggression = metrics.get("player_attacks_per_min", 30.0)

            old_retract = self.retract_chance
            # If player attacks frequently with high accuracy, increase enemy spacing & whiff sensitivity
            if player_hit_rate > 0.6:
                self.retract_chance = min(0.75, 0.45 + (player_hit_rate - 0.6))
                self.whiff_sensitivity = 1.5
            else:
                self.retract_chance = 0.45

            if player_aggression > 40:
                self.aggression_weight = 1.2

            if abs(self.retract_chance - old_retract) > 0.01 or player_hit_rate > 0.6:
                logger.debug(
                    "[AI TELEMETRY ADAPT] Live Combat Tuning -> Player Accuracy: %.1f%% | Aggression: %.1f atk/min -> Adjusted Retraction Chance: %.1f%%, Whiff Sensitivity: %.2f",
                    player_hit_rate * 100, player_aggression, self.retract_chance * 100, self.whiff_sensitivity,
                )
