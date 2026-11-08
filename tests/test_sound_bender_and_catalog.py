"""
Automated tests for the Guardian Runner Audio Emotion Catalog, Scene Mood Recipes,
DSP Sound Bender (`src/game/audio/sound_bender.py`), and Audio Mixer Editor endpoints.
"""
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SIBLING_V3X = PROJECT_ROOT.parent / "V3X-Zulfiqar-Gideon"
if SIBLING_V3X.exists() and str(SIBLING_V3X) not in sys.path:
    sys.path.insert(0, str(SIBLING_V3X))

from src.game.audio.sound_bender import (
    BEND_PRESETS,
    REVERB_SPACES,
    SAMPLE_RATE,
    bake_sound_to_disk,
    render_bent_recipe,
)
from tools.build_audio_emotion_catalog import (
    SCENE_RECIPES,
    build_catalog,
)


def test_emotion_catalog_structure_and_coverage():
    """Verify the generated audio_emotion_catalog.json covers all assets with feelings and scenes."""
    catalog_path = PROJECT_ROOT / "game_data" / "audio_emotion_catalog.json"
    if not catalog_path.exists():
        build_catalog(PROJECT_ROOT)

    assert catalog_path.exists(), "audio_emotion_catalog.json should exist"
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    assert catalog["total_files"] >= 700
    assert catalog["unique_files"] >= 500
    assert len(catalog["emotions"]) == 7
    assert len(catalog["environments"]) == 6
    assert len(catalog["roles"]) >= 5
    assert len(catalog["scene_recipes"]) == len(SCENE_RECIPES)

    # Every asset entry must have an evocative display_title, feeling_summary, emotions, environments, and role
    assets_map = catalog["assets"]
    assert "assets/audio/smash.wav" in assets_map
    smash_entry = assets_map["assets/audio/smash.wav"]
    assert smash_entry["display_title"]
    assert smash_entry["feeling_summary"]
    assert len(smash_entry["emotions"]) >= 1
    assert len(smash_entry["environments"]) >= 1
    assert smash_entry["role"] in catalog["roles"]
    assert smash_entry["recommended_preset"] in BEND_PRESETS

    # Check that duplicate .ogg files in Free Fantasy SFX Pack are flagged cleanly
    duplicates = [a for a in assets_map.values() if a.get("is_duplicate_format")]
    assert len(duplicates) >= 150


def test_sound_bender_dsp_presets_and_layering():
    """Verify sound_bender.py bends pitch, lowpass, drive, reverb, and multi-layer audio into valid 16-bit WAV."""
    recipe = {
        "source_path": "assets/audio/smash.wav",
        "preset": "heavy_scythe_weight",
        "pitch_semitones": -4.0,
        "lowpass_hz": 3200.0,
        "highpass_hz": 40.0,
        "drive": 0.25,
        "reverb_space": "forest",
        "reverb_mix": 0.22,
        "gain_db": 1.0,
        "fade_in_ms": 5.0,
        "fade_out_ms": 40.0,
        "layers": [
            {
                "source_path": "assets/audio/sword-slice-2-393845.mp3",
                "delay_ms": 25.0,
                "pitch_semitones": -3.0,
                "gain_db": -2.0,
                "lowpass_hz": 1800.0,
            }
        ],
    }

    rendered = render_bent_recipe(str(PROJECT_ROOT), recipe)
    assert SAMPLE_RATE == 44100
    assert rendered.ndim == 2 and rendered.shape[1] == 2
    assert rendered.shape[0] > 4410  # at least 0.1s
    peak = float(np.max(np.abs(rendered)))
    assert 0.1 < peak <= 1.0

    baked_meta = bake_sound_to_disk(str(PROJECT_ROOT), "test_heavy_scythe_layer", recipe)
    baked_file = PROJECT_ROOT / baked_meta["relative_path"]
    try:
        assert baked_file.exists()
        assert baked_file.stat().st_size > 1000
        assert baked_meta["sample_rate"] == 44100
        assert baked_meta["duration_sec"] > 0.1

        # Verify pygame.mixer can load the baked 16-bit PCM WAV file cleanly
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        snd = pygame.mixer.Sound(str(baked_file))
        assert snd.get_length() > 0.1
    finally:
        if baked_file.exists():
            baked_file.unlink()
        reg_path = PROJECT_ROOT / "game_data" / "bent_sounds_registry.json"
        if reg_path.exists():
            with open(reg_path, "r", encoding="utf-8") as f:
                reg = json.load(f)
            reg.pop("test_heavy_scythe_layer", None)
            with open(reg_path, "w", encoding="utf-8") as f:
                json.dump(reg, f, indent=2)


def test_audio_mixer_editor_has_emotion_and_bake_endpoints():
    """Verify audio_mixer_editor.py contains the Sound Director UI and backend routes."""
    import audio_mixer_editor

    assert "/api/emotion-catalog" in audio_mixer_editor.HTML_CONTENT
    assert "/api/bake-sound" in audio_mixer_editor.HTML_CONTENT
    assert "Sound Bending & Layer Studio" in audio_mixer_editor.HTML_CONTENT
    assert "auditionBentSound" in audio_mixer_editor.HTML_CONTENT
    assert "bakeAndRegisterSound" in audio_mixer_editor.HTML_CONTENT
