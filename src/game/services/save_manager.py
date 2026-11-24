"""
SaveManager — Atomic, JSON-based persistence system for Pixel-Runner.

Features:
- Atomic file writes via temporary file renaming to prevent save corruption.
- Versioned SaveSlot schema for forward/backward compatibility.
- Auto-save integration on boss defeat and checkpoint triggers.
"""

from __future__ import annotations

import json
import os
import pathlib
import tempfile
import time
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import pygame as pg

if TYPE_CHECKING:
    from src.game.states.game_state import GameState


@dataclass
class SaveSlot:
    """Versioned schema representing saved game progress."""
    slot_id: str
    player_health: float = 100.0
    player_max_health: float = 100.0
    player_mana: float = 100.0
    is_enhanced: bool = False
    demonic_pact_offered: bool = False
    world_distance: float = 0.0
    max_distance: float = 0.0
    souls_collected: int = 0
    total_souls: int = 0
    corruption: float = 0.0
    boss_defeat_count: int = 0
    bosses_defeated: List[str] = field(default_factory=list)
    relics_collected: List[str] = field(default_factory=list)
    health_relic_charges: int = 3
    timestamp: str = ""
    playtime_seconds: float = 0.0
    level_path: str = "game_data/level_1.json"
    version: int = 2

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SaveSlot:
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


class SaveManager:
    """Atomic save file manager supporting multiple save slots."""

    SAVE_DIR: pathlib.Path = pathlib.Path("save_data")

    @classmethod
    def _ensure_dir(cls) -> None:
        cls.SAVE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def save(cls, slot_id: str, data: SaveSlot) -> bool:
        """Atomically write *data* to save slot JSON file."""
        cls._ensure_dir()
        data.slot_id = slot_id
        data.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        target_path = cls.SAVE_DIR / f"slot_{slot_id}.json"

        try:
            # Atomic write: write to temp file first, then replace
            with tempfile.NamedTemporaryFile(
                "w", dir=cls.SAVE_DIR, delete=False, suffix=".tmp"
            ) as tmp_file:
                json.dump(data.to_dict(), tmp_file, indent=2)
                tmp_path = tmp_file.name

            os.replace(tmp_path, target_path)
            print(f"[SAVE MANAGER] Successfully saved slot '{slot_id}' to {target_path}")
            return True
        except Exception as err:
            print(f"[SAVE MANAGER] Failed to write save slot '{slot_id}': {err}")
            return False

    @classmethod
    def load(cls, slot_id: str) -> Optional[SaveSlot]:
        """Load and parse *slot_id* save file."""
        target_path = cls.SAVE_DIR / f"slot_{slot_id}.json"
        if not target_path.exists():
            return None

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            return SaveSlot.from_dict(raw_data)
        except Exception as err:
            print(f"[SAVE MANAGER] Error reading save slot '{slot_id}': {err}")
            return None

    @classmethod
    def delete(cls, slot_id: str) -> bool:
        """Delete a save slot file."""
        target_path = cls.SAVE_DIR / f"slot_{slot_id}.json"
        if target_path.exists():
            try:
                target_path.unlink()
                print(f"[SAVE MANAGER] Deleted save slot '{slot_id}'")
                return True
            except OSError as err:
                print(f"[SAVE MANAGER] Failed to delete slot '{slot_id}': {err}")
        return False

    @classmethod
    def auto_save(cls, game_state: GameState) -> bool:
        """Extract live game state and persist to the auto-save slot."""
        player = game_state.player.sprite
        p_max_health = float(getattr(player, "max_health", 100.0)) if player else 100.0
        raw_health = float(player.health) if player else p_max_health
        # If saving on death, restore full health for when the player presses Continue
        p_health = p_max_health if (raw_health <= 0.0 or (player and getattr(player, "is_dead", False))) else raw_health
        p_mana = float(getattr(player, "mana", 100.0)) if player else 100.0
        is_enhanced = bool(getattr(player, "is_enhanced", False)) if player else False

        relics = (
            game_state.relic_manager.collected_ids()
            if hasattr(game_state, "relic_manager") and game_state.relic_manager
            else []
        )
        corruption = (
            float(game_state.corruption_manager.value)
            if hasattr(game_state, "corruption_manager") and game_state.corruption_manager
            else 0.0
        )

        slot_data = SaveSlot(
            slot_id="auto",
            player_health=p_health,
            player_max_health=p_max_health,
            player_mana=p_mana,
            is_enhanced=is_enhanced,
            demonic_pact_offered=bool(getattr(game_state, "_demonic_pact_offered", False)),
            world_distance=float(game_state.world_distance),
            max_distance=float(game_state.max_distance_reached),
            souls_collected=int(game_state.player_ui.current_soul_total),
            total_souls=int(getattr(game_state, "total_souls", 0)),
            corruption=corruption,
            boss_defeat_count=int(getattr(game_state, "_boss_defeat_count", 0)),
            bosses_defeated=list(getattr(game_state, "_bosses_defeated", [])),
            relics_collected=relics,
            health_relic_charges=int(getattr(game_state, "_health_relic_charges", 3)),
            playtime_seconds=float((pg.time.get_ticks() - getattr(game_state, "_game_start_ticks", 0)) / 1000.0),
            level_path=str(getattr(game_state, "_level_path", "game_data/level_1.json")),
        )
        return cls.save("auto", slot_data)
