"""Tests for SaveManager death auto-save and MainMenu CONTINUE restoration."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.game.services.save_manager import SaveManager, SaveSlot


def test_save_slot_roundtrip_v2(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(SaveManager, "SAVE_DIR", tmp_path)

    slot = SaveSlot(
        slot_id="auto",
        player_health=200.0,
        player_max_health=200.0,
        player_mana=95.0,
        is_enhanced=True,
        demonic_pact_offered=True,
        world_distance=26900.0,
        max_distance=26900.0,
        souls_collected=9650,
        total_souls=1500,
        corruption=20.0,
        boss_defeat_count=3,
        bosses_defeated=["BloodZombie", "Gatekeeper", "FireWizard"],
        relics_collected=["bark_of_the_great_one", "the_eye", "candoras_tear"],
        health_relic_charges=2,
        level_path="game_data/level_1.json",
    )

    assert SaveManager.save("auto", slot) is True
    loaded = SaveManager.load("auto")
    assert loaded is not None
    assert loaded.world_distance == 26900.0
    assert loaded.player_health == 200.0
    assert loaded.player_max_health == 200.0
    assert loaded.is_enhanced is True
    assert loaded.demonic_pact_offered is True
    assert loaded.corruption == 20.0
    assert loaded.boss_defeat_count == 3
    assert loaded.relics_collected == ["bark_of_the_great_one", "the_eye", "candoras_tear"]
    assert loaded.health_relic_charges == 2


def test_auto_save_on_death_restores_full_health(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(SaveManager, "SAVE_DIR", tmp_path)

    player = SimpleNamespace(
        health=0.0,
        max_health=200.0,
        mana=40.0,
        is_dead=True,
        is_enhanced=True,
    )
    relic_mgr = MagicMock()
    relic_mgr.collected_ids.return_value = ["bark_of_the_great_one", "the_eye"]
    game_state = SimpleNamespace(
        player=SimpleNamespace(sprite=player),
        world_distance=26900.0,
        max_distance_reached=26900.0,
        player_ui=SimpleNamespace(current_soul_total=9650),
        total_souls=1500,
        _boss_defeat_count=3,
        _bosses_defeated=["BloodZombie", "Gatekeeper", "FireWizard"],
        _demonic_pact_offered=True,
        _health_relic_charges=3,
        _game_start_ticks=0,
        _level_path="game_data/level_1.json",
        relic_manager=relic_mgr,
        corruption_manager=SimpleNamespace(value=20.0),
    )

    assert SaveManager.auto_save(game_state) is True
    loaded = SaveManager.load("auto")
    assert loaded is not None
    assert loaded.world_distance == 26900.0
    # Saved on death -> revived to full max_health so Continue doesn't load dead
    assert loaded.player_health == 200.0
    assert loaded.player_max_health == 200.0
    assert loaded.is_enhanced is True
    assert loaded.relics_collected == ["bark_of_the_great_one", "the_eye"]

