"""
sound_bender.py — DSP Sound Bending & Multi-Layer Audio Baker for Guardian Runner.

Allows taking 1 to 3 source audio files (.wav, .mp3, .ogg) and "bending" them
to match the desired emotional weight and physical environment:
  - Pitch / Speed shifting in semitones (-12 to +12) for size & weight
  - Warmth / Distance low-pass filter (200 Hz to 20,000 Hz) to sit in dirt/fog
  - Mud-cut high-pass filter (20 Hz to 2,000 Hz)
  - Visceral Drive / Grit saturation (0.0 to 1.0) for combat punch
  - Space / Reverb convolution ("dry", "forest", "cavern", "void")
  - Trim & Fade-In / Fade-Out envelope shaping
  - Multi-layer stacking (e.g., Dirt Step + Armor Chain + Sub Thud)

Outputs standard 16-bit PCM WAV files into `assets/audio/bent/` and records the
recipe in `game_data/bent_sounds_registry.json` so every bent sound can be
re-opened, tweaked, or re-baked at any time.
"""

from __future__ import annotations

import os
import json
import math
import wave
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

SAMPLE_RATE = 44100
BENT_DIR_REL = "assets/audio/bent"
BENT_REGISTRY_REL = "game_data/bent_sounds_registry.json"
REVERB_SPACES = ("dry", "none", "forest", "cavern", "void")


# ── Built-in Preset Recipes for Learning & One-Click Bending ─────────────────
BEND_PRESETS: Dict[str, Dict[str, Any]] = {
    "neutral": {
        "name": "Raw / Unbent (Original)",
        "feeling": "Exact source file with no coloration.",
        "pitch_semitones": 0.0,
        "lowpass_hz": 20000.0,
        "highpass_hz": 20.0,
        "drive": 0.0,
        "reverb_space": "dry",
        "reverb_mix": 0.0,
        "fade_in_ms": 0.0,
        "fade_out_ms": 10.0,
        "gain": 1.0,
    },
    "grounded_forest_step": {
        "name": "Grounded Damp Forest Step",
        "feeling": "Warm, physical boot-on-soil weight; removes harsh digital click so footsteps feel planted in the Dark Forest.",
        "pitch_semitones": -1.5,
        "lowpass_hz": 2600.0,
        "highpass_hz": 55.0,
        "drive": 0.12,
        "reverb_space": "forest",
        "reverb_mix": 0.14,
        "fade_in_ms": 2.0,
        "fade_out_ms": 25.0,
        "gain": 0.95,
    },
    "heavy_scythe_weight": {
        "name": "Cursed Scythe Massive Weight",
        "feeling": "Drops pitch 4 semitones and adds saturation grit so a standard sword swing feels like a heavy demonic scythe.",
        "pitch_semitones": -4.0,
        "lowpass_hz": 6500.0,
        "highpass_hz": 35.0,
        "drive": 0.35,
        "reverb_space": "forest",
        "reverb_mix": 0.18,
        "fade_in_ms": 0.0,
        "fade_out_ms": 40.0,
        "gain": 1.15,
    },
    "brutal_bone_impact": {
        "name": "Visceral Bone-Crushing Impact",
        "feeling": "Hard punchy saturation with sub-weight (-2.5 st) and tight decay for skeleton/zombie hits.",
        "pitch_semitones": -2.5,
        "lowpass_hz": 8000.0,
        "highpass_hz": 40.0,
        "drive": 0.48,
        "reverb_space": "forest",
        "reverb_mix": 0.12,
        "fade_in_ms": 0.0,
        "fade_out_ms": 30.0,
        "gain": 1.2,
    },
    "distant_fog_omen": {
        "name": "Distant Through-the-Fog Omen",
        "feeling": "Rolls off highs (950 Hz) and wraps the sound in deep forest canopy reflection so monsters or bells sound far away in the mist.",
        "pitch_semitones": -3.0,
        "lowpass_hz": 950.0,
        "highpass_hz": 80.0,
        "drive": 0.05,
        "reverb_space": "forest",
        "reverb_mix": 0.45,
        "fade_in_ms": 25.0,
        "fade_out_ms": 180.0,
        "gain": 0.75,
    },
    "catacomb_echo": {
        "name": "Cold Stone Catacomb Echo",
        "feeling": "Reflective stone walls with eerie mid-focus for underground ruins, shrines, and skeleton crypts.",
        "pitch_semitones": -1.0,
        "lowpass_hz": 4200.0,
        "highpass_hz": 90.0,
        "drive": 0.08,
        "reverb_space": "cavern",
        "reverb_mix": 0.42,
        "fade_in_ms": 5.0,
        "fade_out_ms": 150.0,
        "gain": 0.95,
    },
    "abyssal_demonic_pact": {
        "name": "Abyssal Void & Andras Pact",
        "feeling": "Drops pitch half an octave (-6 st) into a dark cavernous void tail for demonic whispers, relics, and Demon Time.",
        "pitch_semitones": -6.0,
        "lowpass_hz": 3200.0,
        "highpass_hz": 30.0,
        "drive": 0.28,
        "reverb_space": "void",
        "reverb_mix": 0.55,
        "fade_in_ms": 15.0,
        "fade_out_ms": 250.0,
        "gain": 1.1,
    },
    "crisp_ethereal_relic": {
        "name": "Sacred Star-Fire Shimmer",
        "feeling": "Lifts pitch (+3 st), clears low mud, and adds an airy shimmer tail for Moon Knight / Candora / light relics.",
        "pitch_semitones": 3.0,
        "lowpass_hz": 16000.0,
        "highpass_hz": 220.0,
        "drive": 0.0,
        "reverb_space": "void",
        "reverb_mix": 0.38,
        "fade_in_ms": 10.0,
        "fade_out_ms": 200.0,
        "gain": 0.95,
    },
}


def _ensure_mixer_initialized() -> None:
    """Initialize pygame.mixer in dummy mode if not already initialized."""
    import pygame as pg

    if not pg.mixer.get_init():
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        try:
            pg.mixer.pre_init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=512)
            pg.init()
            pg.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=512)
        except Exception:
            pass


def load_audio_array(file_path: str) -> Tuple[np.ndarray, int]:
    """
    Load any supported audio file (.wav, .mp3, .ogg) as a float32 stereo array
    in range [-1.0, 1.0] at SAMPLE_RATE (44100 Hz).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    _ensure_mixer_initialized()
    import pygame as pg

    if pg.mixer.get_init():
        snd = pg.mixer.Sound(file_path)
        raw = pg.sndarray.array(snd)
        init_freq, init_bits, init_channels = pg.mixer.get_init()
        arr = raw.astype(np.float32)
        if init_bits in (-16, 16):
            arr /= 32768.0
        elif init_bits in (-8, 8):
            arr /= 128.0
        elif init_bits in (-32, 32):
            arr /= 2147483648.0

        if arr.ndim == 1:
            arr = np.column_stack([arr, arr])
        elif arr.shape[1] == 1:
            arr = np.repeat(arr, 2, axis=1)
        elif arr.shape[1] > 2:
            arr = arr[:, :2]

        if init_freq != SAMPLE_RATE and len(arr) > 1:
            ratio = SAMPLE_RATE / float(init_freq)
            new_len = max(1, int(round(len(arr) * ratio)))
            old_idx = np.linspace(0.0, len(arr) - 1, num=len(arr))
            new_idx = np.linspace(0.0, len(arr) - 1, num=new_len)
            left = np.interp(new_idx, old_idx, arr[:, 0])
            right = np.interp(new_idx, old_idx, arr[:, 1])
            arr = np.column_stack([left, right]).astype(np.float32)

        return np.clip(arr, -1.0, 1.0), SAMPLE_RATE

    # Fallback for pure .wav if pygame.mixer could not initialize
    with wave.open(file_path, "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw_bytes = wf.readframes(n_frames)

    if sampwidth == 2:
        data = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 1:
        data = (np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sampwidth == 4:
        data = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported WAV sample width: {sampwidth}")

    if n_channels == 1:
        arr = np.column_stack([data, data])
    else:
        arr = data.reshape(-1, n_channels)[:, :2]

    if framerate != SAMPLE_RATE and len(arr) > 1:
        ratio = SAMPLE_RATE / float(framerate)
        new_len = max(1, int(round(len(arr) * ratio)))
        old_idx = np.linspace(0.0, len(arr) - 1, num=len(arr))
        new_idx = np.linspace(0.0, len(arr) - 1, num=new_len)
        arr = np.column_stack([
            np.interp(new_idx, old_idx, arr[:, 0]),
            np.interp(new_idx, old_idx, arr[:, 1]),
        ]).astype(np.float32)

    return np.clip(arr, -1.0, 1.0), SAMPLE_RATE


def pitch_shift_array(arr: np.ndarray, semitones: float) -> np.ndarray:
    """
    Shift pitch & speed by `semitones` (-12 to +12) via linear resampling.
    Just like classic game/film foley sampler pitching: pitching down lowers
    frequency AND stretches duration, giving physical mass and size.
    """
    if abs(semitones) < 1e-3 or len(arr) <= 1:
        return arr

    rate = 2.0 ** (float(semitones) / 12.0)
    new_len = max(2, int(round(len(arr) / rate)))
    old_idx = np.arange(len(arr), dtype=np.float32)
    new_idx = np.linspace(0.0, len(arr) - 1, num=new_len, dtype=np.float32)
    left = np.interp(new_idx, old_idx, arr[:, 0])
    right = np.interp(new_idx, old_idx, arr[:, 1])
    return np.column_stack([left, right]).astype(np.float32)


def _fft_filter(arr: np.ndarray, lowpass_hz: float, highpass_hz: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    """
    Apply smooth Butterworth-like 2nd-order frequency roll-off in the FFT domain
    for fast, vectorised low-pass (warmth/distance) and high-pass (mud-cut).
    """
    lowpass_hz = float(max(80.0, min(20000.0, lowpass_hz)))
    highpass_hz = float(max(10.0, min(5000.0, highpass_hz)))

    if lowpass_hz >= 19500.0 and highpass_hz <= 25.0:
        return arr

    n = len(arr)
    if n < 8:
        return arr

    freqs = np.fft.rfftfreq(n, d=1.0 / sr)
    mask = np.ones_like(freqs, dtype=np.float32)

    if lowpass_hz < 19500.0:
        # Smooth 2nd-order Butterworth low-pass magnitude response
        mask *= 1.0 / np.sqrt(1.0 + (freqs / lowpass_hz) ** 4)

    if highpass_hz > 25.0:
        safe_freqs = np.maximum(freqs, 1e-3)
        mask *= 1.0 / np.sqrt(1.0 + (highpass_hz / safe_freqs) ** 4)
        mask[0] = 0.0

    out = np.empty_like(arr, dtype=np.float32)
    for ch in range(2):
        spec = np.fft.rfft(arr[:, ch])
        out[:, ch] = np.fft.irfft(spec * mask, n=n).astype(np.float32)
    return out


def apply_drive(arr: np.ndarray, drive: float) -> np.ndarray:
    """Apply soft-clipping harmonic saturation for gritty combat punch."""
    drive = float(max(0.0, min(1.0, drive)))
    if drive <= 1e-3:
        return arr
    k = 1.0 + drive * 5.0
    saturated = np.tanh(arr * k) / math.tanh(k)
    return ((1.0 - 0.5 * drive) * arr + (0.5 * drive) * saturated).astype(np.float32)


def _generate_space_ir(space: str, sr: int = SAMPLE_RATE) -> Optional[np.ndarray]:
    """
    Generate a deterministic stereo impulse response for the requested space:
      - "forest": Short diffused canopy reflections (0.45s, warm high-damped)
      - "cavern": Medium stone catacomb reflections (1.1s, distinct early echoes)
      - "void":   Long abyssal demonic shimmer/dark tail (2.0s, deep decay)
    """
    space = (space or "dry").lower().strip()
    if space == "dry" or space == "none":
        return None

    rng = np.random.default_rng(seed={"forest": 101, "cavern": 202, "void": 303}.get(space, 404))

    if space == "forest":
        dur = 0.45
        decay = 7.5
        lp = 2800.0
        early_taps = [(0.018, 0.45), (0.037, 0.32), (0.063, 0.24), (0.095, 0.16)]
    elif space == "cavern":
        dur = 1.15
        decay = 3.8
        lp = 3600.0
        early_taps = [(0.024, 0.55), (0.052, 0.42), (0.089, 0.35), (0.145, 0.25), (0.210, 0.18)]
    else:  # "void"
        dur = 2.0
        decay = 2.1
        lp = 2200.0
        early_taps = [(0.035, 0.50), (0.078, 0.42), (0.135, 0.36), (0.220, 0.30), (0.340, 0.22)]

    n = int(dur * sr)
    t = np.linspace(0.0, dur, num=n, dtype=np.float32)
    env = np.exp(-decay * t)
    noise_l = rng.standard_normal(n).astype(np.float32) * env * 0.25
    noise_r = rng.standard_normal(n).astype(np.float32) * env * 0.25

    for delay_s, gain in early_taps:
        idx = int(delay_s * sr)
        if idx < n:
            noise_l[idx] += gain
        idx_r = min(n - 1, idx + int(0.004 * sr))
        if idx_r < n:
            noise_r[idx_r] += gain * 0.95

    ir = np.column_stack([noise_l, noise_r])
    ir = _fft_filter(ir, lowpass_hz=lp, highpass_hz=90.0, sr=sr)
    energy = float(np.sqrt(np.mean(ir ** 2))) + 1e-6
    ir /= energy * 18.0
    return ir.astype(np.float32)


def apply_reverb(arr: np.ndarray, space: str, mix: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Convolve `arr` with a synthetic environment impulse response via FFT."""
    mix = float(max(0.0, min(0.85, mix)))
    if mix <= 1e-3 or not space or space in ("dry", "none"):
        return arr

    ir = _generate_space_ir(space, sr=sr)
    if ir is None:
        return arr

    n_out = len(arr) + len(ir) - 1
    n_fft = 1 << (n_out - 1).bit_length()

    wet = np.empty((n_out, 2), dtype=np.float32)
    for ch in range(2):
        A = np.fft.rfft(arr[:, ch], n=n_fft)
        B = np.fft.rfft(ir[:, ch], n=n_fft)
        conv = np.fft.irfft(A * B, n=n_fft)[:n_out]
        wet[:, ch] = conv.astype(np.float32)

    dry_padded = np.zeros_like(wet)
    dry_padded[: len(arr)] = arr

    combined = (1.0 - mix * 0.45) * dry_padded + mix * wet
    return combined.astype(np.float32)


def apply_envelope(
    arr: np.ndarray,
    trim_start_ms: float = 0.0,
    trim_end_ms: float = 0.0,
    fade_in_ms: float = 0.0,
    fade_out_ms: float = 10.0,
    sr: int = SAMPLE_RATE,
) -> np.ndarray:
    """Trim start/end and apply smooth linear fade-in and fade-out."""
    start_idx = max(0, int((trim_start_ms / 1000.0) * sr))
    if trim_end_ms > 0.0:
        end_idx = min(len(arr), int((trim_end_ms / 1000.0) * sr))
    else:
        end_idx = len(arr)

    if end_idx > start_idx + 16:
        arr = arr[start_idx:end_idx].copy()
    else:
        arr = arr.copy()

    n = len(arr)
    if n < 4:
        return arr

    fi = min(n // 2, max(0, int((fade_in_ms / 1000.0) * sr)))
    if fi > 1:
        ramp_in = np.linspace(0.0, 1.0, num=fi, dtype=np.float32)[:, None]
        arr[:fi] *= ramp_in

    fo = min(n // 2, max(0, int((fade_out_ms / 1000.0) * sr)))
    if fo > 1:
        ramp_out = np.linspace(1.0, 0.0, num=fo, dtype=np.float32)[:, None]
        arr[-fo:] *= ramp_out

    return arr


def process_single_layer(
    base_dir: str,
    rel_path: str,
    pitch_semitones: float = 0.0,
    lowpass_hz: float = 20000.0,
    highpass_hz: float = 20.0,
    drive: float = 0.0,
    gain: float = 1.0,
    trim_start_ms: float = 0.0,
    trim_end_ms: float = 0.0,
    fade_in_ms: float = 0.0,
    fade_out_ms: float = 10.0,
) -> np.ndarray:
    """Load and process a single layer before mixing and master reverb."""
    full_path = rel_path if os.path.isabs(rel_path) else os.path.join(base_dir, rel_path)
    arr, sr = load_audio_array(full_path)
    arr = apply_envelope(
        arr,
        trim_start_ms=trim_start_ms,
        trim_end_ms=trim_end_ms,
        fade_in_ms=fade_in_ms,
        fade_out_ms=fade_out_ms,
        sr=sr,
    )
    arr = pitch_shift_array(arr, pitch_semitones)
    arr = _fft_filter(arr, lowpass_hz=lowpass_hz, highpass_hz=highpass_hz, sr=sr)
    arr = apply_drive(arr, drive=drive)
    arr = arr * float(gain)
    return arr


def _resolve_gain(cfg: Dict[str, Any], default_linear: float = 1.0) -> float:
    if "gain_db" in cfg and cfg["gain_db"] is not None:
        return float(10.0 ** (float(cfg["gain_db"]) / 20.0))
    return float(cfg.get("gain", default_linear))


def render_bent_recipe(base_dir: str, recipe: Dict[str, Any]) -> np.ndarray:
    """
    Render a complete bend recipe (primary sound + optional stacked layers +
    shared reverb space) into a stereo float32 array in [-1.0, 1.0].
    """
    source_path = recipe.get("source_path") or recipe.get("path")
    if not source_path:
        raise ValueError("Recipe must include 'source_path'")

    base_dir_str = str(base_dir)
    main_arr = process_single_layer(
        base_dir=base_dir_str,
        rel_path=str(source_path),
        pitch_semitones=float(recipe.get("pitch_semitones", 0.0)),
        lowpass_hz=float(recipe.get("lowpass_hz", 20000.0)),
        highpass_hz=float(recipe.get("highpass_hz", 20.0)),
        drive=float(recipe.get("drive", 0.0)),
        gain=_resolve_gain(recipe, 1.0),
        trim_start_ms=float(recipe.get("trim_start_ms", 0.0)),
        trim_end_ms=float(recipe.get("trim_end_ms", 0.0)),
        fade_in_ms=float(recipe.get("fade_in_ms", 0.0)),
        fade_out_ms=float(recipe.get("fade_out_ms", 10.0)),
    )

    layers = recipe.get("layers") or []
    layer_arrays: List[Tuple[int, np.ndarray]] = [(0, main_arr)]

    for layer in layers:
        l_path = (layer.get("source_path") or layer.get("path") or "").strip()
        if not l_path:
            continue
        delay_ms = float(layer.get("delay_ms", 0.0))
        offset_samples = max(0, int((delay_ms / 1000.0) * SAMPLE_RATE))
        l_arr = process_single_layer(
            base_dir=base_dir_str,
            rel_path=l_path,
            pitch_semitones=float(layer.get("pitch_semitones", 0.0)),
            lowpass_hz=float(layer.get("lowpass_hz", 20000.0)),
            highpass_hz=float(layer.get("highpass_hz", 20.0)),
            drive=float(layer.get("drive", 0.0)),
            gain=_resolve_gain(layer, 0.6),
            trim_start_ms=float(layer.get("trim_start_ms", 0.0)),
            trim_end_ms=float(layer.get("trim_end_ms", 0.0)),
            fade_in_ms=float(layer.get("fade_in_ms", 0.0)),
            fade_out_ms=float(layer.get("fade_out_ms", 10.0)),
        )
        layer_arrays.append((offset_samples, l_arr))

    total_len = max(off + len(a) for off, a in layer_arrays)
    mixed = np.zeros((total_len, 2), dtype=np.float32)
    for off, a in layer_arrays:
        mixed[off : off + len(a)] += a

    reverb_space = str(recipe.get("reverb_space", "dry"))
    reverb_mix = float(recipe.get("reverb_mix", 0.0))
    mixed = apply_reverb(mixed, space=reverb_space, mix=reverb_mix, sr=SAMPLE_RATE)

    # Peak limiter to prevent harsh digital clipping while preserving dynamics
    peak = float(np.max(np.abs(mixed))) if len(mixed) > 0 else 0.0
    if peak > 0.98:
        mixed = mixed * (0.98 / peak)

    return np.clip(mixed, -1.0, 1.0)


def save_wav_array(arr: np.ndarray, output_path: str, sr: int = SAMPLE_RATE) -> None:
    """Write a float32 stereo array [-1.0, 1.0] to a 16-bit PCM WAV file."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    pcm16 = np.clip(arr * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())


def bake_sound_to_disk(base_dir: str, output_alias: str, recipe: Dict[str, Any]) -> Dict[str, Any]:
    """
    Bake `recipe` into `assets/audio/bent/<output_alias>.wav` and record its
    parameters in `game_data/bent_sounds_registry.json`.
    Returns metadata including `relative_path` and `duration_sec`.
    """
    import re

    safe_alias = re.sub(r"[^a-zA-Z0-9_\-]", "_", output_alias.strip()).strip("_").lower()
    if not safe_alias:
        safe_alias = "bent_sound"

    rel_wav_path = f"{BENT_DIR_REL}/{safe_alias}.wav"
    abs_wav_path = os.path.join(base_dir, rel_wav_path)

    rendered = render_bent_recipe(base_dir, recipe)
    save_wav_array(rendered, abs_wav_path, sr=SAMPLE_RATE)
    duration_sec = round(len(rendered) / float(SAMPLE_RATE), 3)

    # Persist recipe in bent_sounds_registry.json
    reg_path = os.path.join(base_dir, BENT_REGISTRY_REL)
    registry: Dict[str, Any] = {}
    if os.path.exists(reg_path):
        try:
            with open(reg_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
        except Exception:
            registry = {}

    registry[safe_alias] = {
        "alias": safe_alias,
        "output_path": rel_wav_path,
        "duration_sec": duration_sec,
        "recipe": recipe,
    }
    os.makedirs(os.path.dirname(reg_path), exist_ok=True)
    with open(reg_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)

    return {
        "alias": safe_alias,
        "relative_path": rel_wav_path,
        "duration_sec": duration_sec,
        "sample_rate": SAMPLE_RATE,
        "recipe": recipe,
    }
