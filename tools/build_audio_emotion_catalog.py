"""
build_audio_emotion_catalog.py — Generates `game_data/audio_emotion_catalog.json`
and `game_data/scene_audio_recipes.json` for Guardian Runner.

Walks `assets/` for all audio files (.wav, .mp3, .ogg) and enriches every sound
with:
  - `display_title`: Evocative, feeling-first title so you immediately know what
    the sound feels like and represents.
  - `feeling_summary`: Plain-English description of the emotional state or
    physical sensation the sound creates.
  - `emotions`: List of emotion tags (e.g. "Dread & Ominous", "Grounded & Physical",
    "Heavy & Brutal", "Arcane & Ethereal", "Urgent & Adrenaline", "Melancholic & Lonely",
    "Sacred & Hopeful").
  - `environments`: List of scene tags (e.g. "Dark Forest", "Burning Village",
    "Catacombs & Ruin", "Demonic Void", "Boss Arena", "UI & Lore").
  - `role`: High-level sound design role ("Music", "Ambience Loop", "Footstep / Foley",
    "Weapon Whoosh", "Combat Impact", "Creature Vocal", "Spell / Element",
    "UI / Narrative Stinger", "Voice / Effort").
  - `bend_tip`: Specific recommendation for how to bend (pitch, filter, reverb, layer)
    the sound to fit Guardian Runner scenes.
  - `recommended_preset`: Key into `BEND_PRESETS` from `sound_bender.py`.
  - `is_duplicate_format`: True when an identical `.wav` exists for an `.ogg` twin
    (so the UI can hide duplicates by default).
"""

from __future__ import annotations

import os
import re
import json
import pathlib
from typing import Dict, List, Any, Tuple

ROOT = pathlib.Path(__file__).resolve().parent.parent


# ── Curated Evocative Lookup for Music & Standalone Named Tracks ─────────────
EXPLICIT_TRACK_MAP: Dict[str, Dict[str, Any]] = {
    "1 exploration tommusic": {
        "display_title": "Whispering Canopy — Lonely Forest Exploration",
        "feeling_summary": "Wandering alone beneath ancient trees; evokes quiet curiosity, solitude, and distant ancient mystery.",
        "emotions": ["Melancholic & Lonely", "Arcane & Ethereal"],
        "environments": ["Dark Forest", "Catacombs & Ruin"],
        "role": "Music",
        "bpm": 92,
        "bend_tip": "Layer softly (45% volume) over 'Forest Night.wav' + 'Forest Night Rain.wav' so the music breathes inside the woods.",
        "recommended_preset": "neutral",
    },
    "1. for better tomorrow - 120bpm - long loop 1min 40s": {
        "display_title": "Dawn Through Iron — Heroic Stride (120 BPM Long)",
        "feeling_summary": "Steady, driving forward momentum with a spark of resolve; makes the player feel like a determined guardian pushing through darkness.",
        "emotions": ["Urgent & Adrenaline", "Sacred & Hopeful"],
        "environments": ["Dark Forest", "Boss Arena"],
        "role": "Music",
        "bpm": 120,
        "bend_tip": "Great for mid-level progression after surviving the first wave; keeps the player moving forward with confidence.",
        "recommended_preset": "neutral",
    },
    "1. for better tomorrow - 120bpm - loop 40s": {
        "display_title": "Dawn Through Iron — Heroic Stride (120 BPM Short Loop)",
        "feeling_summary": "Tighter 40-second loop of steady heroic combat momentum.",
        "emotions": ["Urgent & Adrenaline", "Sacred & Hopeful"],
        "environments": ["Dark Forest", "Boss Arena"],
        "role": "Music",
        "bpm": 120,
        "bend_tip": "Use for shorter skirmish waves or stage transitions.",
        "recommended_preset": "neutral",
    },
    "2. one last day on earth - 110bpm - long loop 1min44s": {
        "display_title": "Ashes of the Last Watch — Grim Survival (110 BPM Extended)",
        "feeling_summary": "Heavy, grounded 110 BPM pulse; feels like marching through a cursed world with weight on your shoulders.",
        "emotions": ["Dread & Ominous", "Heavy & Brutal"],
        "environments": ["Dark Forest", "Catacombs & Ruin"],
        "role": "Music",
        "bpm": 110,
        "bend_tip": "Ideal primary Level 1 combat-runner music; its 110 BPM tempo naturally locks with the Runner's stride.",
        "recommended_preset": "neutral",
    },
    "2. one last day on earth - 110bpm - loop 52s": {
        "display_title": "Ashes of the Last Watch — Grim Survival (110 BPM Core Loop)",
        "feeling_summary": "Focused 52-second loop of heavy, grim survival tension.",
        "emotions": ["Dread & Ominous", "Heavy & Brutal"],
        "environments": ["Dark Forest", "Catacombs & Ruin"],
        "role": "Music",
        "bpm": 110,
        "bend_tip": "Pitch down -1.5 semitones and low-pass at 3.5kHz during low-HP or high-corruption states to make the world feel oppressive.",
        "recommended_preset": "neutral",
    },
    "3. time for a revenge - 157bpm - loop 48s": {
        "display_title": "Blood Debt Unleashed — Vengeful Assault (157 BPM)",
        "feeling_summary": "Aggressive, high-pulse 157 BPM battle theme; spikes heart rate and pushes the player into ruthless offense.",
        "emotions": ["Urgent & Adrenaline", "Heavy & Brutal"],
        "environments": ["Boss Arena", "Burning Village"],
        "role": "Music",
        "bpm": 157,
        "bend_tip": "Trigger when a mini-boss (Blood Zombie / Dark Ronin) enters its enraged phase.",
        "recommended_preset": "neutral",
    },
    "4. ready as can be - 208bpm - loop 25s": {
        "display_title": "Heart of the Maelstrom — Overdrive Panic (208 BPM)",
        "feeling_summary": "Breakneck 208 BPM sprint; creates breathless urgency, overwhelming swarm pressure, or Demon Time bullet-time contrast.",
        "emotions": ["Urgent & Adrenaline"],
        "environments": ["Boss Arena", "Demonic Void"],
        "role": "Music",
        "bpm": 208,
        "bend_tip": "Use for final boss phase or timed survival rushes where the player must react on pure instinct.",
        "recommended_preset": "neutral",
    },
    "5. only one can survive - 140bpm - 45sec": {
        "display_title": "No Quarter Given — Duel to the Death (140 BPM)",
        "feeling_summary": "Tense, martial 140 BPM showdown track; feels like a locked arena duel where only one walks out.",
        "emotions": ["Urgent & Adrenaline", "Dread & Ominous"],
        "environments": ["Boss Arena"],
        "role": "Music",
        "bpm": 140,
        "bend_tip": "Pair with 'Ominous Bells of Doom' as a pre-duel stinger before dropping into this 140 BPM boss loop.",
        "recommended_preset": "neutral",
    },
    "burning fire": {
        "display_title": "Embers of the Ruined Home — Burning Village Roar",
        "feeling_summary": "Crackling, consuming blaze that evokes loss, smoke, and the night everything burned down.",
        "emotions": ["Dread & Ominous", "Melancholic & Lonely"],
        "environments": ["Burning Village"],
        "role": "Ambience Loop",
        "bend_tip": "Pitch down -2 semitones for a deeper roaring inferno, and layer 'Torch Loop.wav' on top for close-up ember crackles.",
        "recommended_preset": "distant_fog_omen",
    },
    "dark-forest": {
        "display_title": "Shrouded Boughs — Deep Dark Forest Drone",
        "feeling_summary": "Low, brooding woodland atmosphere that makes the trees feel watchful and alive.",
        "emotions": ["Dread & Ominous", "Melancholic & Lonely"],
        "environments": ["Dark Forest"],
        "role": "Ambience Loop",
        "bend_tip": "Keep at 25-35% volume underneath 'Forest Night.wav' to glue footsteps and combat into the forest floor.",
        "recommended_preset": "neutral",
    },
    "night sounds": {
        "display_title": "Watchers in the Thicket — Night Insects & Distant Wind",
        "feeling_summary": "Nocturnal crickets and cool night air; grounds the player in a real outdoor midnight environment.",
        "emotions": ["Melancholic & Lonely", "Grounded & Physical"],
        "environments": ["Dark Forest"],
        "role": "Ambience Loop",
        "bend_tip": "Roll off highs above 4.5kHz so insects never clash with crisp blade slashes.",
        "recommended_preset": "grounded_forest_step",
    },
    "ominous bells of doom": {
        "display_title": "Toll of the Forsaken — Funeral Cathedral Bell",
        "feeling_summary": "Heavy iron bell tolling through mist; signals irreversible fate, boss arrival, or a dark pact.",
        "emotions": ["Dread & Ominous"],
        "environments": ["Burning Village", "Catacombs & Ruin", "Boss Arena", "Demonic Void"],
        "role": "UI / Narrative Stinger",
        "bend_tip": "Pitch down -3 semitones with 'Abyssal Void' reverb for boss warnings or pact confirmations.",
        "recommended_preset": "abyssal_demonic_pact",
    },
    "magical light aura sound effect": {
        "display_title": "Star-Fire Awakening — Celestial Resonance Hum",
        "feeling_summary": "Warm, shimmering harmonic aura that feels protective, ancient, and transcendent.",
        "emotions": ["Sacred & Hopeful", "Arcane & Ethereal"],
        "environments": ["UI & Lore", "Demonic Void"],
        "role": "Spell / Element",
        "bend_tip": "Pitch +2 semitones for pure Star-Fire/Candora light, or pitch -6 semitones with drive for corrupted purple void power.",
        "recommended_preset": "crisp_ethereal_relic",
    },
    "reveal sound effect": {
        "display_title": "Veil Parted — Lore & Relic Revelation Stinger",
        "feeling_summary": "A sudden, dramatic unveiling that tells the player they have uncovered something forbidden or pivotal.",
        "emotions": ["Arcane & Ethereal", "Dread & Ominous"],
        "environments": ["UI & Lore", "Catacombs & Ruin"],
        "role": "UI / Narrative Stinger",
        "bend_tip": "Add 'Cavern' or 'Void' reverb at 35% so the reveal lingers while text types out.",
        "recommended_preset": "catacomb_echo",
    },
    "wendigo screams": {
        "display_title": "Howl of the Starving Woods — Distant Wendigo Shriek",
        "feeling_summary": "Piercing, feral scream echoing through timber; triggers primal fight-or-flight tension.",
        "emotions": ["Dread & Ominous", "Urgent & Adrenaline"],
        "environments": ["Dark Forest"],
        "role": "Creature Vocal",
        "bend_tip": "Use 'Distant Through-the-Fog Omen' preset (low-pass 950 Hz + forest reverb) so it sounds 200 meters away in the trees.",
        "recommended_preset": "distant_fog_omen",
    },
    "lighting": {
        "display_title": "Sky-Split Judgement — Thunder & Arcane Bolt",
        "feeling_summary": "Sharp electric crack followed by rolling thunder; delivers sudden shock and elemental authority.",
        "emotions": ["Heavy & Brutal", "Urgent & Adrenaline"],
        "environments": ["Dark Forest", "Boss Arena", "Burning Village"],
        "role": "Spell / Element",
        "bend_tip": "Layer with 'Rock Wall 1.wav' pitched down -3st for an earth-shaking staff lightning strike.",
        "recommended_preset": "heavy_scythe_weight",
    },
    "whoosh-cinematic-sound-effect-376889": {
        "display_title": "Shadow Step Rush — Cinematic Air Tear Whoosh",
        "feeling_summary": "Deep, breathless displacement of air; makes dashes, rolls, and wide scythe arcs feel fast and lethal.",
        "emotions": ["Grounded & Physical", "Urgent & Adrenaline"],
        "environments": ["Dark Forest", "Boss Arena"],
        "role": "Weapon Whoosh",
        "bend_tip": "Pitch down -3st for heavy scythe swings, or +2st for a razor-fast shadow dash.",
        "recommended_preset": "heavy_scythe_weight",
    },
    "smash": {
        "display_title": "Earth-Cleaver — Heavy Overhead Smash Impact",
        "feeling_summary": "Crushing, low-end impact that makes the ground feel like it cracked under the weapon.",
        "emotions": ["Heavy & Brutal", "Grounded & Physical"],
        "environments": ["Dark Forest", "Boss Arena"],
        "role": "Combat Impact",
        "bend_tip": "Layer with 'bone_breaking_03.wav' or 'Dirt Chain Land.wav' for maximum physical crunch.",
        "recommended_preset": "brutal_bone_impact",
    },
    "thrust": {
        "display_title": "Viper Lunge — Sharp Forward Blade Thrust",
        "feeling_summary": "Focused, piercing metallic forward lunge.",
        "emotions": ["Grounded & Physical", "Urgent & Adrenaline"],
        "environments": ["Dark Forest", "Boss Arena"],
        "role": "Weapon Whoosh",
        "bend_tip": "Pitch down -2st and add 20% drive so the thrust has midrange body instead of sounding thin.",
        "recommended_preset": "heavy_scythe_weight",
    },
}


def classify_asset(rel_path: str, file_size: int) -> Dict[str, Any]:
    """Classify an audio asset path into human-friendly emotion, scene, title, and bend advice."""
    norm = rel_path.replace("\\", "/")
    filename = os.path.basename(norm)
    stem, ext = os.path.splitext(filename)
    stem_lower = stem.lower().strip()
    norm_lower = norm.lower()

    # 1. Check explicit curated tracks first
    if stem_lower in EXPLICIT_TRACK_MAP:
        entry = dict(EXPLICIT_TRACK_MAP[stem_lower])
        entry["path"] = norm
        entry["filename"] = filename
        entry["pack"] = _detect_pack_name(norm)
        return entry

    # 2. Abyssal Horror SFX Vol.1
    if "abyssal horror" in norm_lower:
        if "abyssal_descent" in stem_lower:
            variant = "II" if "1" in stem_lower else "I"
            return {
                "path": norm,
                "filename": filename,
                "pack": "Abyssal Horror Vol.1",
                "display_title": f"Abyssal Descent Drone {variant} — Sub-Void Pressure",
                "feeling_summary": "Sinking into a bottomless black ocean of dread; creates instant psychological weight during Andras dialogues or corruption spikes.",
                "emotions": ["Dread & Ominous", "Arcane & Ethereal"],
                "environments": ["Demonic Void", "Catacombs & Ruin", "Boss Arena"],
                "role": "Ambience Loop",
                "bend_tip": "Pitch down -4 semitones and loop at 30% volume beneath dialogue overlays to make the room feel suffocating.",
                "recommended_preset": "abyssal_demonic_pact",
            }
        # DeepOne vocals
        num_match = re.search(r"(\d+)$", stem_lower)
        num_str = f" #{num_match.group(1)}" if num_match else ""
        if "chatter" in stem_lower:
            title = f"Chittering Void Spawn{num_str} — Unhinged Stalker Mandibles"
            feel = "Alien, insectoid chittering that makes unseen creatures in the dark feel erratic and unsettling."
        elif "frothygrowl" in stem_lower:
            title = f"Blood-Choked Abomination Growl{num_str} — Wet Visceral Menace"
            feel = "Guttural, wet, rabid snarl; perfect for Blood Zombie or corrupted beasts lunging at close range."
        elif "groan" in stem_lower:
            title = f"Hollowed Vessel Groan{num_str} — Tormented Undead Agony"
            feel = "Slow, mournful undead moan carrying the weight of a trapped soul."
        elif "rumble" in stem_lower:
            title = f"Leviathan Sub-Rumble{num_str} — Chest-Rattling Dread Growl"
            feel = "Deep sub-bass throat vibration that makes a boss or demon feel 20 feet tall."
        elif "grunt" in stem_lower:
            title = f"Abyssal Brute Grunt{num_str} — Heavy Monster Exertion"
            feel = "Short, heavy guttural bark when a monster swings or takes a heavy blow."
        else:
            title = f"Deep One Menace Growl{num_str} — Eldritch Predator Snarl"
            feel = "Dark, resonant monster growl that signals lethal danger."

        return {
            "path": norm,
            "filename": filename,
            "pack": "Abyssal Horror Vol.1",
            "display_title": title,
            "feeling_summary": feel,
            "emotions": ["Dread & Ominous", "Heavy & Brutal"],
            "environments": ["Demonic Void", "Dark Forest", "Boss Arena"],
            "role": "Creature Vocal",
            "bend_tip": "Pitch down -3 to -5 semitones with 'Cavern' or 'Void' reverb to turn this into an intimidating boss vocal.",
            "recommended_preset": "abyssal_demonic_pact",
        }

    # 3. Be Not Afraid UI (--Unholy / Souls & BNA_UI)
    if "be not afraid ui" in norm_lower:
        num_match = re.search(r"(\d+)", stem_lower)
        num = int(num_match.group(1)) if num_match else 1
        if "souls" in norm_lower:
            moods = [
                "Whispering Soul Wisp",
                "Phantom Exhale Stinger",
                "Cursed Relic Resonance",
                "Spectral Choir Swell",
                "Hollow Ledger Sigh",
                "Grave-Cold Spirit Chime",
                "Tainted Sigil Pulse",
                "Echo of the Fallen",
            ]
            label = moods[(num - 1) % len(moods)]
            return {
                "path": norm,
                "filename": filename,
                "pack": "Be Not Afraid — Unholy Souls",
                "display_title": f"{label} #{num} — Ethereal Soul & Relic Aura",
                "feeling_summary": "Haunting, otherworldly spirit texture; makes collecting relics, reading the grimoire, or harvesting souls feel sacred yet cursed.",
                "emotions": ["Arcane & Ethereal", "Dread & Ominous", "Melancholic & Lonely"],
                "environments": ["Demonic Void", "UI & Lore", "Catacombs & Ruin"],
                "role": "UI / Narrative Stinger",
                "bend_tip": "Pitch +2st for pure angelic/Star-Fire lore moments, or -5st for Andras corruption and soul absorption.",
                "recommended_preset": "abyssal_demonic_pact",
            }
        else:
            is_long = "long" in stem_lower
            if is_long:
                title = f"Cathedral Pact Banner Swell #{num} — Major Lore/Boss Stinger"
                feel = "Long, resonant gothic UI/cutscene impact designed for chapter titles, boss warnings, and pact choices."
                preset = "abyssal_demonic_pact"
            elif num <= 20:
                title = f"Occult Grimoire Rune Click #{num} — Crisp Gothic Tactile UI"
                feel = "Carved stone and dark iron tactile click; gives menu navigation and dialogue advances physical weight."
                preset = "catacomb_echo"
            elif num <= 45:
                title = f"Sanctum Seal Chime #{num} — Dark Ritual Confirmation"
                feel = "Metallic-arcane resonant tone that makes equipping a power or advancing lore feel consequential."
                preset = "catacomb_echo"
            else:
                title = f"Unholy Altar Toll #{num} — Heavy Fate Notification"
                feel = "Deep, ominous notification strike for warnings, corruption thresholds, and objective pop-ups."
                preset = "abyssal_demonic_pact"

            return {
                "path": norm,
                "filename": filename,
                "pack": "Be Not Afraid — Gothic UI",
                "display_title": title,
                "feeling_summary": feel,
                "emotions": ["Arcane & Ethereal", "Dread & Ominous"],
                "environments": ["UI & Lore", "Demonic Void", "Catacombs & Ruin"],
                "role": "UI / Narrative Stinger",
                "bend_tip": "Combine a crisp Rune Click (#1-#15) with a pitched-down Soul Whisper (-4st) for an unforgettable relic pickup sound.",
                "recommended_preset": preset,
            }

    # 4. TomMusic BGS Loops (Environmental Ambience Beds)
    if "bgs loops" in norm_lower:
        is_rain = "rain" in stem_lower
        is_storm = "storm" in stem_lower
        weather = " (Driving Storm & Thunder)" if is_storm else (" (Steady Rain & Damp Leaves)" if is_rain else " (Calm Natural Air)")
        if "forest night" in stem_lower:
            title = f"Dark Forest Midnight Canopy{weather}"
            feel = "Immersive nocturnal woodland bed; wraps the player in cool night air, rustling boughs, and quiet tension."
            env = ["Dark Forest"]
            emo = ["Dread & Ominous", "Melancholic & Lonely", "Grounded & Physical"]
        elif "forest day" in stem_lower:
            title = f"Ancient Woodland Clearing{weather}"
            feel = "Open, breathing forest atmosphere with natural wind and canopy movement."
            env = ["Dark Forest"]
            emo = ["Grounded & Physical", "Sacred & Hopeful"]
        elif "cave" in stem_lower:
            title = f"Sunken Stone Catacombs{weather}"
            feel = "Cold, echoing subterranean air with dripping stone and enclosed pressure."
            env = ["Catacombs & Ruin", "Demonic Void"]
            emo = ["Dread & Ominous", "Melancholic & Lonely"]
        elif "interior" in norm_lower or "inside" in stem_lower:
            time_lbl = "Night" if "night" in stem_lower else "Day"
            title = f"Ruined Sanctuary Interior ({time_lbl}){weather}"
            feel = "Sheltered, intimate room tone while wind/rain batters the stone walls outside."
            env = ["Catacombs & Ruin", "Burning Village"]
            emo = ["Melancholic & Lonely", "Grounded & Physical"]
        elif "beach" in stem_lower or "sea" in stem_lower:
            title = f"Black-Water Shore & Crashing Surge{weather}"
            feel = "Rolling, relentless water and wind; adds vast, desolate scale to coastal or abyssal borders."
            env = ["Demonic Void", "Dark Forest"]
            emo = ["Melancholic & Lonely", "Dread & Ominous"]
        else:
            title = f"Environmental Atmosphere Bed — {stem}"
            feel = "Continuous environmental room tone that makes the world feel alive."
            env = ["Dark Forest"]
            emo = ["Grounded & Physical"]

        return {
            "path": norm,
            "filename": filename,
            "pack": "TomMusic — Environmental BGS Loops",
            "display_title": title,
            "feeling_summary": feel,
            "emotions": emo,
            "environments": env,
            "role": "Ambience Loop",
            "bend_tip": "Run at 30–45% volume as your continuous scene bed, and roll off highs at 3.5kHz so combat SFX cut right through.",
            "recommended_preset": "grounded_forest_step",
        }

    # 5. TomMusic Footsteps (Dirt, Stone, Water, Wood; Walk, Run, Jump, Land; Chain vs Plain)
    if "/footsteps/" in norm_lower:
        has_chain = "chain" in stem_lower
        armor_lbl = "Armored Chain-Boot" if has_chain else "Light Leather-Boot"
        if "dirt" in stem_lower:
            surf_lbl = "Damp Forest Dirt"
            env = ["Dark Forest", "Burning Village"]
        elif "stone" in stem_lower:
            surf_lbl = "Cold Catacomb Flagstone"
            env = ["Catacombs & Ruin", "Boss Arena"]
        elif "wood" in stem_lower:
            surf_lbl = "Creaking Timber & Roots"
            env = ["Burning Village", "Dark Forest"]
        else:
            surf_lbl = "Shallow Mire & Puddle"
            env = ["Dark Forest", "Catacombs & Ruin"]

        num_match = re.search(r"(\d+)$", stem_lower)
        step_num = f" (Step #{num_match.group(1)})" if num_match else ""
        if "jump" in stem_lower:
            act_lbl = "Jump Push-Off"
            feel = f"Physical push-off from {surf_lbl.lower()}{' with subtle armor rattle' if has_chain else ''}; sells the upward burst of a jump."
        elif "land" in stem_lower:
            act_lbl = "Heavy Landing Thud"
            feel = f"Grounded two-foot impact on {surf_lbl.lower()}{' with chain settle' if has_chain else ''}; makes gravity and body weight feel real."
        elif "run" in stem_lower:
            act_lbl = f"Sprint Stride{step_num}"
            feel = f"Urgent, driving footstrike on {surf_lbl.lower()}{' with metallic armor cadence' if has_chain else ''}."
        else:
            act_lbl = f"Cautious Step{step_num}"
            feel = f"Deliberate, grounded step on {surf_lbl.lower()}{' with quiet chain clink' if has_chain else ''}."

        return {
            "path": norm,
            "filename": filename,
            "pack": f"TomMusic — Footsteps ({surf_lbl})",
            "display_title": f"{armor_lbl} on {surf_lbl} — {act_lbl}",
            "feeling_summary": feel,
            "emotions": ["Grounded & Physical"],
            "environments": env,
            "role": "Footstep / Foley",
            "bend_tip": "Use 'Grounded Damp Forest Step' preset (Pitch -1.5st, Low-Pass 2600 Hz, 14% Forest Reverb) so footsteps sit inside the dirt road instead of clicking on top of the mix.",
            "recommended_preset": "grounded_forest_step",
        }

    # 6. TomMusic Attacks / Weapons / Spells / Doors / Torch / Waterfalls
    if "tommusic" in norm_lower:
        if "sword" in stem_lower:
            if "parry" in stem_lower or "blocked" in stem_lower:
                title = f"Steel-on-Steel Deflection ({stem}) — Sparks & Guard Impact"
                feel = "Sharp, ringing metallic deflection that rewards timed blocks and parries."
                role = "Combat Impact"
                preset = "brutal_bone_impact"
            elif "unsheath" in stem_lower or "sheath" in stem_lower:
                title = f"Scythe & Blade Draw ({stem}) — Cold Iron Readiness"
                feel = "Crisp metallic slide that signals entering or ending a combat stance."
                role = "Weapon Whoosh"
                preset = "heavy_scythe_weight"
            elif "impact" in stem_lower:
                title = f"Cleaving Blade Bite ({stem}) — Flesh & Iron Strike"
                feel = "Solid metallic bite when a slash connects with an enemy."
                role = "Combat Impact"
                preset = "brutal_bone_impact"
            else:
                title = f"Scythe Arc Swing ({stem}) — Fast Steel Cut"
                feel = "Clean weapon swing through the air; pitch down -4st to transform from light sword into heavy scythe."
                role = "Weapon Whoosh"
                preset = "heavy_scythe_weight"
            return {
                "path": norm,
                "filename": filename,
                "pack": "TomMusic — Weapon & Combat",
                "display_title": title,
                "feeling_summary": feel,
                "emotions": ["Heavy & Brutal", "Grounded & Physical"],
                "environments": ["Dark Forest", "Boss Arena"],
                "role": role,
                "bend_tip": "Pitch down -3 to -4 semitones and layer with a Deadly Kombat body/bone hit for visceral scythe combat.",
                "recommended_preset": preset,
            }

        if "bow" in stem_lower:
            return {
                "path": norm,
                "filename": filename,
                "pack": "TomMusic — Ranged & Projectile",
                "display_title": f"Whip-Snap Projectile ({stem}) — Taut String & Air Dart",
                "feeling_summary": "Snappy, high-tension release or impact; useful for ranged projectiles, bat darts, or bone throws.",
                "emotions": ["Urgent & Adrenaline", "Grounded & Physical"],
                "environments": ["Dark Forest", "Boss Arena"],
                "role": "Weapon Whoosh",
                "bend_tip": "Layer under spell launches or fast thrust attacks to add a snappy transient.",
                "recommended_preset": "grounded_forest_step",
            }

        if "/spells/" in norm_lower:
            if "fire" in stem_lower:
                title = f"Hellfire Surge ({stem}) — Searing Flame Burst"
                feel = "Explosive, hungry flame ignition for Fire Wizard spells, burning totems, or enhanced attacks."
                env = ["Burning Village", "Boss Arena"]
            elif "ice" in stem_lower:
                title = f"Rime-Shard Shatter ({stem}) — Crystalline Frost Snap"
                feel = "Piercing, brittle crystalline burst; great for Candora's Tear, glass/crystal relics, or freezing time."
                env = ["UI & Lore", "Catacombs & Ruin"]
            elif "rock" in stem_lower:
                title = f"Earth-Shatter Tremor ({stem}) — Crushing Stone Mass"
                feel = "Massive, tectonic stone crunch; adds devastating ground weight to smash attacks and boss slams."
                env = ["Catacombs & Ruin", "Boss Arena"]
            else:
                title = f"Arcane Surge ({stem}) — Elemental Pulse"
                feel = "Dynamic elemental energy burst for magic attacks and environmental hazards."
                env = ["Boss Arena", "Demonic Void"]
            return {
                "path": norm,
                "filename": filename,
                "pack": "TomMusic — Elemental Spells",
                "display_title": title,
                "feeling_summary": feel,
                "emotions": ["Arcane & Ethereal", "Heavy & Brutal"],
                "environments": env,
                "role": "Spell / Element",
                "bend_tip": "Pitch 'Rock Wall' or 'Fireball' down -3st and layer at 40% under the player's Smash/Power finisher.",
                "recommended_preset": "heavy_scythe_weight",
            }

        if "/torch/" in norm_lower:
            return {
                "path": norm,
                "filename": filename,
                "pack": "TomMusic — Fire & Torches",
                "display_title": f"Flickering Roadside Brazier ({stem}) — Warm Pitch & Flame",
                "feeling_summary": "Intimate, resinous fire crackle and swoosh that brings animated torches and fireplaces to life.",
                "emotions": ["Grounded & Physical", "Dread & Ominous"],
                "environments": ["Dark Forest", "Burning Village", "Catacombs & Ruin"],
                "role": "Ambience Loop" if "loop" in stem_lower else "Spell / Element",
                "bend_tip": "Attach 'Torch Loop.wav' with spatial attenuation to animated fireplace/torch props so they hum as the Runner passes.",
                "recommended_preset": "grounded_forest_step",
            }

        if "/doors gates" in norm_lower or "/chopping" in norm_lower or "/waterfalls" in norm_lower:
            return {
                "path": norm,
                "filename": filename,
                "pack": "TomMusic — World Props & Mechanisms",
                "display_title": f"Ancient World Mechanism ({stem}) — Heavy Wood, Iron & Water",
                "feeling_summary": "Physical world-interaction foley (iron gates, heavy chests, rushing streams) that makes props feel tangible.",
                "emotions": ["Grounded & Physical"],
                "environments": ["Catacombs & Ruin", "Dark Forest"],
                "role": "Ambience Loop" if "loop" in stem_lower else "Footstep / Foley",
                "bend_tip": "Use 'Portcullis Gate' or 'Chest Open' pitched down -2st when unlocking boss arenas or ancient shrines.",
                "recommended_preset": "catacomb_echo",
            }

    # 7. Deadly Kombat Free Version
    if "deadly kombat" in norm_lower:
        if "blade_hit" in stem_lower:
            title = f"Executioner's Carve ({stem}) — Wet Steel Slice"
            feel = "Razor-sharp steel slicing through armor and flesh; immediate visceral feedback on hit."
            role = "Combat Impact"
        elif "bone_breaking" in stem_lower:
            title = f"Shattered Marrow ({stem}) — Brutal Bone Snap"
            feel = "Sickening, crispy bone fracture; makes killing or critting Skeletons feel deeply satisfying."
            role = "Combat Impact"
        elif "guts_and_gore" in stem_lower:
            title = f"Crimson Rupture ({stem}) — Wet Gore Splatter"
            feel = "Heavy, visceral blood-and-flesh tear for Blood Zombie hits and finishers."
            role = "Combat Impact"
        elif "block_" in stem_lower:
            title = f"Iron Guard Impact ({stem}) — Heavy Shield/Weapon Block"
            feel = "Solid, concussive defensive impact when an attack is absorbed by a shield or parry."
            role = "Combat Impact"
        elif "whoosh" in stem_lower or "somersault" in stem_lower:
            title = f"Martial Air Whip ({stem}) — Agile Combat Swing/Roll"
            feel = "Punchy, physical body or weapon movement through air."
            role = "Weapon Whoosh"
        elif "fire_punch" in stem_lower or "metal_punch" in stem_lower or "wood_bat" in stem_lower:
            title = f"Crushing Finisher Blow ({stem}) — Heavy Elemental/Blunt Strike"
            feel = "Devastating knockout impact with massive midrange punch."
            role = "Combat Impact"
        else:
            title = f"Heavy Trauma Impact ({stem}) — Staggering Body/Face Blow"
            feel = "Thudding, high-impact strike that communicates real physical force."
            role = "Combat Impact"

        return {
            "path": norm,
            "filename": filename,
            "pack": "Deadly Kombat — Visceral Combat",
            "display_title": title,
            "feeling_summary": feel,
            "emotions": ["Heavy & Brutal", "Grounded & Physical"],
            "environments": ["Dark Forest", "Boss Arena"],
            "role": role,
            "bend_tip": "Stack a 'blade_hit' + 'bone_breaking' (delayed 15ms, pitched -2st) for a signature Guardian Runner scythe crunch.",
            "recommended_preset": "brutal_bone_impact",
        }

    # 8. Beasts / Dinosaurs / Fantasy Monsters / CreatureSoundFree
    if any(k in norm_lower for k in ("beasts/", "dinosaurs/", "fantasy monsters/", "creaturesoundfree")):
        if "dinosaur" in norm_lower:
            pack = "Dinosaurs — Primeval Roars"
            title = f"Primeval Behemoth ({stem}) — Earth-Shaking Reptilian Roar"
            feel = "Massive, chest-deep prehistoric vocalization; ideal for Dragon props, Green Monster, or demonic transformation."
        elif "fantasy monsters" in norm_lower:
            pack = "Fantasy Monsters — Vocal Pack"
            if "fae_" in stem_lower:
                title = f"Sylvan Spirit Voice ({stem}) — Eerie Forest Fae"
                feel = "Delicate yet uncanny forest spirit vocal; adds mystery or unsettling contrast in the dark woods."
            elif "giant_" in stem_lower:
                title = f"Colossus Titan Vocal ({stem}) — Towering Brute Force"
                feel = "Booming, heavy-chested giant roar or groan for Gatekeeper and heavy bosses."
            elif "warg_" in stem_lower or "serpent" in stem_lower:
                title = f"Shadow Hound / Serpent ({stem}) — Feral Predator Snarl"
                feel = "Vicious, hungry predator vocalization that keeps the player on edge."
            else:
                title = f"Twisted Forest Denizen ({stem}) — Goblin/Beast Call"
                feel = "Distinctive creature personality vocal for ambushes and minion reactions."
        elif "creaturesoundfree" in norm_lower:
            pack = "Creature Sound Free — Undead & Beasts"
            title = f"Ravenous Undead / Lion Roar ({stem}) — Breath & Feral Rage"
            feel = "Raw, organic breathing and roaring; grounds undead enemies with real lung and throat texture."
        else:
            pack = "Beasts — Monster Vocalizations"
            title = f"Feral Forest Beast ({stem}) — Bellow & Threat Growl"
            feel = "Powerful animalistic roar or snort that fills the forest with living danger."

        return {
            "path": norm,
            "filename": filename,
            "pack": pack,
            "display_title": title,
            "feeling_summary": feel,
            "emotions": ["Dread & Ominous", "Heavy & Brutal"],
            "environments": ["Dark Forest", "Boss Arena", "Catacombs & Ruin"],
            "role": "Creature Vocal",
            "bend_tip": "Pitch down -3st for bosses, or use 'Distant Through-the-Fog Omen' to place monster calls deep in the background trees.",
            "recommended_preset": "heavy_scythe_weight",
        }

    # 9. Male Effort / Damage / Death Grunts in assets/audio/
    if any(k in stem_lower for k in ("effort grunt", "damage grunt", "death groan", "fighting-man", "angry-grunt")):
        num_match = re.search(r"^(\d+)", stem_lower)
        num_str = f" #{num_match.group(1)}" if num_match else ""
        if "damage" in stem_lower or "pain" in stem_lower:
            title = f"Warrior Pain Shock{num_str} — Visceral Hit Reaction"
            feel = "Sharp, human intake of breath and pain when the Runner takes a direct hit."
            emo = ["Heavy & Brutal", "Grounded & Physical"]
        elif "death" in stem_lower:
            title = f"Last Breath Collapse{num_str} — Mortal Defeat Groan"
            feel = "Exhausted, fading final breath when the Runner falls."
            emo = ["Melancholic & Lonely", "Dread & Ominous"]
        else:
            title = f"Guardian Combat Exertion{num_str} — Heavy Scythe Swing Grunt"
            feel = "Short, physical breath exertion that makes heavy attacks and jumps feel human and effortful."
            emo = ["Grounded & Physical", "Urgent & Adrenaline"]

        return {
            "path": norm,
            "filename": filename,
            "pack": "Guardian Voice — Human Effort & Pain",
            "display_title": title,
            "feeling_summary": feel,
            "emotions": emo,
            "environments": ["Dark Forest", "Boss Arena"],
            "role": "Voice / Effort",
            "bend_tip": "Keep volume subtle (35–50%) and pitch -1st so the grunt blends naturally behind the weapon whoosh.",
            "recommended_preset": "grounded_forest_step",
        }

    # 10. Remaining standalone files in assets/audio
    return {
        "path": norm,
        "filename": filename,
        "pack": _detect_pack_name(norm),
        "display_title": f"{stem.replace('_', ' ').replace('-', ' ').title()} — Core Game Audio",
        "feeling_summary": "Core atmospheric or combat sound effect in the Guardian Runner library.",
        "emotions": ["Grounded & Physical", "Dread & Ominous"],
        "environments": ["Dark Forest", "Boss Arena"],
        "role": "Ambience Loop" if file_size > 800_000 else "Combat Impact",
        "bend_tip": "Audition with 'Grounded Damp Forest Step' or 'Cursed Scythe Massive Weight' to match the scene tone.",
        "recommended_preset": "neutral",
    }


def _detect_pack_name(norm_path: str) -> str:
    parts = norm_path.split("/")
    if len(parts) >= 3 and parts[0] == "assets" and parts[1] == "audio" and len(parts) > 3:
        return parts[2]
    if len(parts) >= 3 and parts[0] == "assets" and parts[1] != "audio":
        return parts[1]
    return "Core Audio Library"


SCENE_RECIPES: List[Dict[str, Any]] = [
    {
        "id": "scene_dark_forest_awakening",
        "title": "🌲 Scene 1: The Dark Forest Awakening (Exploration & Dread)",
        "target_feeling": "Lonely, damp, watchful. The player should feel the cool midnight mist, hear their boots pressing into damp earth, and sense unseen eyes in the canopy.",
        "ambient_bed_primary": "assets/audio/Free Fantasy SFX Pack By TomMusic/WAV Files/BGS Loops/Forest Night/Forest Night.wav",
        "ambient_bed_secondary": "assets/audio/Free Fantasy SFX Pack By TomMusic/WAV Files/BGS Loops/Forest Night/Forest Night Rain.wav",
        "music_track": "assets/audio/1 Exploration TomMusic.ogg",
        "recommended_bend_preset": "grounded_forest_step",
        "how_to_mix": [
            "1. Set 'Forest Night.wav' as your continuous room-tone bed at 40% volume.",
            "2. Layer 'Forest Night Rain.wav' or 'dark-forest.ogg' at 25% volume with Low-Pass at 2400 Hz for damp air.",
            "3. Bend footsteps ('Dirt Chain Run 1..5') with Pitch -1.5st and Low-Pass 2600 Hz so they thud into the soil instead of clicking.",
            "4. Trigger 'Wendigo sounds.mp3' or 'DeepOne_Rumble.mp3' pitched down -4st with 45% Forest Reverb at rare intervals."
        ],
    },
    {
        "id": "scene_burning_village_prologue",
        "title": "🔥 Scene 2: Memories of the Burning Village (Tragedy & Fury)",
        "target_feeling": "Suffocating heat, grief, and irreversible doom. The fire should roar in the chest while distant bells toll.",
        "ambient_bed_primary": "assets/audio/Burning Fire.mp3",
        "ambient_bed_secondary": "assets/audio/Free Fantasy SFX Pack By TomMusic/WAV Files/SFX/Torch/Torch Loop.wav",
        "music_track": "assets/audio/Abyssal Horror SFX Vol.1/Abyssal Horror/Abyssal_Descent.mp3",
        "recommended_bend_preset": "distant_fog_omen",
        "how_to_mix": [
            "1. Pitch 'Burning Fire.mp3' down -2st so it sounds like a massive roaring structure fire rather than a small campfire.",
            "2. Layer 'Torch Loop.wav' unbent at 35% volume for close-up snapping embers.",
            "3. Bend 'Ominous Bells of Doom.mp3' with Pitch -3st + Void Reverb (50%) when transitioning between comic panels."
        ],
    },
    {
        "id": "scene_whispering_grimoire_pact",
        "title": "👁️ Scene 3: The Whispering Grimoire & Andras Pact (Unholy Intimacy)",
        "target_feeling": "Time slows down; the forest recedes into a suffocating void where only Andras's bargain and the pulsing runes exist.",
        "ambient_bed_primary": "assets/audio/Abyssal Horror SFX Vol.1/Abyssal Horror/Abyssal_Descent1.mp3",
        "ambient_bed_secondary": "assets/audio/Be Not Afraid UI/--Unholy/Souls/Unholy UI - Souls (4).wav",
        "music_track": "assets/audio/Magical Light Aura Sound Effect.mp3",
        "recommended_bend_preset": "abyssal_demonic_pact",
        "how_to_mix": [
            "1. Duck forest ambience by 70% (low-pass at 600 Hz) as soon as the Grimoire opens.",
            "2. Bring in 'Abyssal_Descent1.mp3' pitched down -4st as a sub-bass void bed.",
            "3. Use 'Unholy UI - Souls (1..16)' pitched -3st for rune levitation and 'BNA_UI13_Long.wav' for pact confirmation."
        ],
    },
    {
        "id": "scene_blood_zombie_horde_clash",
        "title": "🩸 Scene 4: Blood Zombie & Skeleton Horde Clash (Visceral Weight)",
        "target_feeling": "Relentless iron, bone, and sinew. Every scythe swing feels heavy and dangerous; every hit cracks bone or tears armor.",
        "ambient_bed_primary": "assets/audio/Free Fantasy SFX Pack By TomMusic/WAV Files/BGS Loops/Forest Night/Forest Night Storm.wav",
        "ambient_bed_secondary": "assets/audio/dark-forest.ogg",
        "music_track": "assets/audio/Combat Pack - vol 1/2. One Last Day on Earth - 110bpm - LOOP 52s.wav",
        "recommended_bend_preset": "heavy_scythe_weight",
        "how_to_mix": [
            "1. Drive the encounter with 'One Last Day on Earth (110 BPM)' or escalate to 'Time For a Revenge (157 BPM)'.",
            "2. Bend player scythe swings ('whoosh-cinematic' or 'Sword Attack 1..3') down -4st with 35% Drive.",
            "3. Stack 'blade_hit_07.wav' + 'bone_breaking_03.wav' (delayed 15ms, pitched -2st) for Skeleton hits, and 'guts_and_gore_19.wav' for Blood Zombie hits."
        ],
    },
]


def build_catalog(base_dir: pathlib.Path) -> Dict[str, Any]:
    assets_dir = base_dir / "assets"
    all_files: List[Tuple[str, int]] = []

    for root, _, files in os.walk(assets_dir):
        if "__MACOSX" in root:
            continue
        for f in files:
            if f.lower().endswith((".wav", ".mp3", ".ogg", ".flac", ".m4a")):
                full = pathlib.Path(root) / f
                rel = full.relative_to(base_dir).as_posix()
                try:
                    sz = full.stat().st_size
                except OSError:
                    sz = 0
                all_files.append((rel, sz))

    all_files.sort(key=lambda x: x[0])

    # Identify OGG files that have an identical WAV twin in TomMusic pack
    wav_stems = set()
    for rel, _ in all_files:
        if rel.lower().endswith(".wav") and "/wav files/" in rel.lower():
            key = rel.lower().replace("/wav files/", "/").rsplit(".", 1)[0]
            wav_stems.add(key)

    entries: Dict[str, Dict[str, Any]] = {}
    emotion_counts: Dict[str, int] = {}
    environment_counts: Dict[str, int] = {}
    role_counts: Dict[str, int] = {}

    for rel, sz in all_files:
        info = classify_asset(rel, sz)
        is_dup = False
        if rel.lower().endswith(".ogg") and "/ogg files/" in rel.lower():
            key = rel.lower().replace("/ogg files/", "/").rsplit(".", 1)[0]
            if key in wav_stems:
                is_dup = True
        info["is_duplicate_format"] = is_dup
        info["size_kb"] = round(sz / 1024.0, 1)
        entries[rel] = info

        if not is_dup:
            for em in info.get("emotions", []):
                emotion_counts[em] = emotion_counts.get(em, 0) + 1
            for env in info.get("environments", []):
                environment_counts[env] = environment_counts.get(env, 0) + 1
            r = info.get("role", "Other")
            role_counts[r] = role_counts.get(r, 0) + 1

    from src.game.audio.sound_bender import BEND_PRESETS

    catalog = {
        "version": "1.0",
        "total_files": len(entries),
        "unique_files": sum(1 for v in entries.values() if not v.get("is_duplicate_format")),
        "emotions": [
            {"id": "Dread & Ominous", "icon": "🌑", "color": "#a855f7", "desc": "Suspense, dark pacts, unseen threats, and psychological weight."},
            {"id": "Grounded & Physical", "icon": "🥾", "color": "#10b981", "desc": "Real-world texture: boots on damp dirt, armor clinks, timber, wind, and rain."},
            {"id": "Heavy & Brutal", "icon": "🩸", "color": "#ef4444", "desc": "Visceral scythe weight, bone-shattering impacts, and monstrous force."},
            {"id": "Arcane & Ethereal", "icon": "✨", "color": "#06b6d4", "desc": "Otherworldly runes, soul whispers, relics, and elemental spellcraft."},
            {"id": "Urgent & Adrenaline", "icon": "⚡", "color": "#f59e0b", "desc": "High-BPM combat drive, fast dashes, and survival pressure."},
            {"id": "Melancholic & Lonely", "icon": "🕯️", "color": "#64748b", "desc": "Solitude, tragic memories, quiet night air, and forsaken ruins."},
            {"id": "Sacred & Hopeful", "icon": "🌅", "color": "#eab308", "desc": "Star-Fire light, Candora's grace, and heroic resolve."},
        ],
        "environments": [
            {"id": "Dark Forest", "icon": "🌲", "desc": "Damp soil, midnight canopy, wind through boughs, and distant beasts."},
            {"id": "Burning Village", "icon": "🔥", "desc": "Roaring embers, collapsing timber, smoke, and tragic memory."},
            {"id": "Catacombs & Ruin", "icon": "🏛️", "desc": "Cold flagstone, echoing crypts, iron gates, and ancient shrines."},
            {"id": "Demonic Void", "icon": "👁️", "desc": "Sub-bass abyssal pressure, Andras's pact, and bullet-time overdrive."},
            {"id": "Boss Arena", "icon": "⚔️", "desc": "High-stakes showdowns, lethal telegraphs, and heavy steel clashes."},
            {"id": "UI & Lore", "icon": "📜", "desc": "Grimoire pages, relic reveals, chapter banners, and notifications."},
        ],
        "roles": list(role_counts.keys()),
        "summary_counts": {
            "by_emotion": emotion_counts,
            "by_environment": environment_counts,
            "by_role": role_counts,
        },
        "bend_presets": BEND_PRESETS,
        "scene_recipes": SCENE_RECIPES,
        "assets": entries,
    }
    return catalog


def main() -> None:
    import sys

    target_root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT
    engine_sibling = target_root.parent / "V3X-Zulfiqar-Gideon"
    if engine_sibling.exists():
        sys.path.insert(0, str(engine_sibling))
    sys.path.insert(0, str(target_root))

    catalog = build_catalog(target_root)
    out_catalog = target_root / "game_data" / "audio_emotion_catalog.json"
    out_recipes = target_root / "game_data" / "scene_audio_recipes.json"
    out_catalog.parent.mkdir(parents=True, exist_ok=True)

    with open(out_catalog, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)

    with open(out_recipes, "w", encoding="utf-8") as f:
        json.dump({"scene_recipes": SCENE_RECIPES}, f, indent=2)

    print(
        f"[AudioEmotionCatalog] Wrote {catalog['total_files']} total assets "
        f"({catalog['unique_files']} unique after hiding OGG/WAV twins) -> {out_catalog}"
    )


if __name__ == "__main__":
    main()
