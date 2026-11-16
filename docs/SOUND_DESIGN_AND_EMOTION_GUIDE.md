# 🎧 Guardian Runner — Sound Design, Emotion & Bending Guide

This guide translates the **~630 audio files** in `assets/` into **feelings, environments, and actionable sound-bending recipes**. Use it alongside the upgraded **Sound Bending & Scene Mood Studio** (`python audio_mixer_editor.py`) to pick and shape sounds that put the player directly inside the world.

---

## 1. 🎵 Music Library — Titles with Feelings, BPM & Scene Fit

Every music track in your repository has a specific pulse (BPM) and emotional gravity:

| Evocative Title | File Path | BPM | Emotional State | Best Scene / Moment | How to Bend / Transition |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **Whispering Canopy** *(Lonely Exploration)* | `assets/audio/1 Exploration TomMusic.ogg` | ~92 | 🕯️ Melancholic, Curious, Ancient | **Opening Forest Walk / Story Intro / Quiet Shrine** | Keep at `40–45%` volume underneath `Forest Night.wav` so the trees and wind feel louder than the melody. |
| **Ashes of the Last Watch** *(Grim Survival)* | `assets/audio/Combat Pack - vol 1/2. One Last Day on Earth - 110bpm - LOOP 52s.wav` *(and 1m44s Long Loop)* | 110 | 🌑 Grim Determination, Heavy Stride, Oppressive | **Level 1 Core Runner & Skeleton Patrols** | Its `110 BPM` pulse locks naturally with the Runner's stride. At high corruption, bend pitch `-1.5 st` and Low-Pass at `3200 Hz` to make it feel heavier and darker. |
| **Dawn Through Iron** *(Heroic Push)* | `assets/audio/Combat Pack - vol 1/1. For Better Tomorrow - 120bpm - LONG LOOP 1min 40s.wav` *(and 40s Loop)* | 120 | 🌅 Rising Courage, Forward Momentum, Resolve | **Mid-Level Breakthrough / Post-Pact Resuscitation** | Switch to this when the player survives an ambush or rejects corruption—it lifts the chest from `110` to `120 BPM`. |
| **No Quarter Given** *(Arena Showdown)* | `assets/audio/Combat Pack - vol 1/5. Only One Can Survive - 140bpm - 45sec.wav` | 140 | ⚔️ Martial Tension, Locked Arena Duel | **Gatekeeper / Mini-Boss Arena Lock** | Fire `Ominous Bells of Doom.mp3` (pitched `-3 st`) 0.5 seconds before dropping into this loop. |
| **Blood Debt Unleashed** *(Vengeful Assault)* | `assets/audio/Combat Pack - vol 1/3. Time For a Revenge - 157bpm - LOOP 48s.wav` | 157 | 🩸 Ruthless Aggression, High Adrenaline | **Blood Zombie / Dark Ronin Enraged Phase** | Spikes the player's heart rate during ruthless close-quarters blade exchanges. |
| **Heart of the Maelstrom** *(Apex Overdrive)* | `assets/audio/Combat Pack - vol 1/4. Ready As Can Be - 208bpm - LOOP 25s.wav` | 208 | ⚡ Breathless Panic, Swarm Overdrive | **Final Boss Phase / Timed Survival Rush** | Extreme `208 BPM` urgency—use sparingly for peak climax moments so the player feels pushed to the limit. |

---

## 2. 🌲 Environmental Immersion — Making the Player Feel *In the Place*

A scene feels fake when sound effects play over "digital silence" or over music alone. Real immersion uses **3 environmental layers** playing together before a single sword is swung:

1. **Layer 1: The Air / Room Tone (Continuous Bed at 35–45% volume)**
   - **Dark Forest**: `BGS Loops/Forest Night/Forest Night.wav` + `assets/audio/dark-forest.ogg` (deep woodland drone).
   - **Rainy / Damp Forest**: `BGS Loops/Forest Night/Forest Night Rain.wav` (filtered at `2600 Hz` so the rain sounds like it is hitting leaves overhead, not static white noise).
   - **Stormy Boss Arena**: `BGS Loops/Forest Night/Forest Night Storm.wav`.
   - **Burning Village**: `assets/audio/Burning Fire.mp3` (pitched `-2 st` for a deep structure-fire roar).
   - **Catacombs / Shrine**: `BGS Loops/Cave/Cave.wav` or `Cave Rain.wav`.
   - **Demonic Void / Andras Pact**: `Abyssal Horror/Abyssal_Descent.mp3` (pitched `-4 st` for sub-bass pressure).

2. **Layer 2: Near-Field Props (Tied to Objects on Screen)**
   - **Roadside Torches & Fireplaces**: `SFX/Torch/Torch Loop.wav` (warm, close-up resinous crackle).
   - **Streams / Water**: `SFX/Waterfalls Rivers and Streams/River Stream Loop.wav`.
   - **Grimoire / Relics**: `Be Not Afraid UI/--Unholy/Souls/Unholy UI - Souls (4).wav`.

3. **Layer 3: Distant World Callouts (Every 12–25 seconds, Muffled & Reverbed)**
   - Take a creature sound (`Wendigo sounds.mp3`, `DeepOne_Rumble1.mp3`, `bats.wav`, `Beast_Hooting.wav`) and apply the **"Distant Through-the-Fog Omen"** preset (`Pitch -3 st`, `Low-Pass 950 Hz`, `Forest Reverb 45%`, `Volume 20%`).
   - Because high frequencies don't travel far through trees and mist, rolling off everything above `950 Hz` tricks the human ear into hearing the monster **hundreds of meters away in the dark forest**.

---

## 3. 🥾 Making Movement & Combat Sound Real (Why Raw Sounds Feel Fake)

When footsteps or sword swings sound "pasted on" instead of physical, it is almost always due to three things:

### Problem A: Footsteps Have Too Much High-Frequency "Click"
- **Why**: Studio recordings of footsteps (`Dirt Run 1..5.wav`, `Dirt Chain Run 1..5.wav`) are recorded with a microphone 1 foot from the shoe. In a dark, damp forest, that bright `6,000–12,000 Hz` click makes the character sound like they are tapping on a desk.
- **How to Fix (Bend Recipe — *"Grounded Damp Forest Step"*)**:
  - **Pitch**: `-1.5 semitones` (gives the Runner physical boot weight).
  - **Warmth / Low-Pass Filter**: `2,600 Hz` (cuts the brittle click and leaves the earthy soil thud).
  - **Space Reverb**: `Forest Canopy` at `14%` mix.
  - **Variation**: Alternate `Dirt Chain Run 1`, `Dirt Chain Run 3`, and `Dirt Chain Run 5` across frames `3` and `8` of the `RUN` cycle so two consecutive steps are never identical.
  - **Jump & Landing Weight**: Pair `Dirt Jump.wav` on `JUMP_UP` frame `0` with `Dirt Chain Land.wav` (pitched `-2 st`) on `JUMP_DOWN` landing so gravity feels real.

### Problem B: The Scythe Sounds Like a Light Fencing Sword
- **Why**: Standard sword whooshes (`Sword Attack 1..3.wav`) are pitched for a 2-pound short sword, whereas your Runner wields a massive cursed scythe.
- **How to Fix (Bend Recipe — *"Cursed Scythe Massive Weight"*)**:
  - **Pitch**: `-3.5 to -4.5 semitones` (stretches the air displacement and lowers the resonant frequency so the blade sounds huge).
  - **Grit / Drive**: `35%` (adds harmonic weight to the midrange).
  - **Layering**: Stack `whoosh-cinematic-sound-effect-376889.wav` (primary, `-3 st`) + `Deadly Kombat/blade_hit_07.wav` or `Sword Attack 2.wav` (layer 2, delayed `25 ms`, gain `60%`).

### Problem C: Hits Lack "Transfer of Force" (Blade + Body/Bone)
- **Why**: A single slice sound only tells the ear about the *blade*, not what the blade *hit*.
- **How to Fix (2-Layer Impact Stacking)**:
  - **Against Skeletons**: Layer 1 = `blade_hit_07.wav` (the steel edge) + Layer 2 (`+15 ms` delay) = `bone_breaking_03.wav` pitched `-2 st` (the marrow snapping).
  - **Against Blood Zombie**: Layer 1 = `blade_hit_08.wav` + Layer 2 (`+10 ms` delay) = `guts_and_gore_19.wav` or `body_hit_large_32.wav` pitched `-2 st`.
  - **Against Shield / Block**: Layer 1 = `Sword Blocked 2.wav` + Layer 2 = `block_large_59.wav` pitched `-3 st`.

---

## 4. 🎛️ The 4 Sound-Bending Knobs Explained Simply

Inside the **Sound Bending & Scene Mood Studio** (`audio_mixer_editor.py`), you have 4 core controls plus a Layer Stacker:

| Control | What It Does Physically | Emotional Effect When Turned **Down / Left** | Emotional Effect When Turned **Up / Right** |
| :--- | :--- | :--- | :--- |
| **1. Pitch / Weight** (`-12` to `+12 st`) | Changes playback speed & frequency (like slowing down or speeding up tape). | **Bigger, heavier, darker, slower, more ancient/demonic.** Turns a man's grunt into a brute, or a sword into a giant scythe. | **Smaller, faster, sharper, more frantic or crystalline.** Turns a chime into Star-Fire shimmer or a dash into a whip-crack. |
| **2. Warmth / Distance (Low-Pass Hz)** (`200` to `20,000 Hz`) | Cuts frequencies above the cutoff point. | **Farther away, muffled by fog/trees, grounded in soft dirt, underwater/void.** | **Right in your face, sharp, metallic, raw, aggressive.** |
| **3. Grit / Drive** (`0%` to `100%`) | Soft-clips peaks and boosts dense midrange harmonics. | **Clean, natural, delicate, acoustic.** | **Visceral, crushing, distorted, corrupted, high-impact.** |
| **4. Space / Reverb** (`Dry`, `Forest`, `Catacomb`, `Void`) | Wraps the sound in acoustic reflections of an environment. | **Intimate, dry, inside the player's own head or boots.** | **Vast, echoing, lonely, cavernous, or otherworldly.** |

---

## 5. 🗂️ Quick Directory of Your Hidden Sound Packs

| Pack Folder in `assets/` | What's Actually Inside | Best Emotional Use in Guardian Runner |
| :--- | :--- | :--- |
| `Abyssal Horror SFX Vol.1` | 2 sub-void drones (`Abyssal_Descent`) + 17 wet, guttural eldritch growls & rumbles (`DeepOne_*`). | **Demonic Void, Andras Pact, Corruption Vignette, Blood Zombie & Boss Growls.** |
| `Be Not Afraid UI (--Unholy)` | 66 gothic stone/iron ritual UI clicks & swells (`BNA_UI*`) + 16 haunting spirit whispers (`Unholy UI - Souls`). | **Grimoire Cutscene, Relic Reveals, Boss Warnings, Soul Harvest, Menu Transitions.** |
| `Combat Pack - vol 1` | 7 full combat music loops across `110`, `120`, `140`, `157`, and `208 BPM`. | **Dynamic combat pacing from grim exploration (110 BPM) to boss frenzy (157–208 BPM).** |
| `Deadly Kombat Free version` | 50 brutal martial impacts: `blade_hit`, `bone_breaking`, `guts_and_gore`, `block_large`, `body_hit_finisher`, `fire_punch`. | **Layering heavy physical crunch onto scythe hits, skeleton deaths, and parries.** |
| `TomMusic / BGS Loops` | 21 seamless environmental loops: `Forest Night`, `Forest Day`, `Cave`, `Interior`, `Beach/Sea` (each with Calm, Rain, Storm). | **Continuous environmental beds so every level feels like a real physical place.** |
| `TomMusic / SFX / Footsteps` | 96 footsteps across `Dirt`, `Stone`, `Wood`, `Water` — both Leather (`Dirt Run`) and Armored (`Dirt Chain Run`), plus `Jump` and `Land`. | **Grounded player movement, jumping, and landing matched to the road surface.** |
| `TomMusic / SFX / Attacks & Spells` | Sword swings/parries/unsheathes, Bow snaps, `Fireball`, `Ice Freeze`, `Rock Wall`, `Torch Loop`. | **Weapon layers, Fire Wizard spells, animated roadside torches, earth-slam finishers.** |
| `Beasts`, `Dinosaurs`, `Fantasy Monsters`, `CreatureSoundFree` | 119 creature vocals: giant roars, warg snarls, heavy undead breathing, dinosaur bellows, eerie forest fae. | **Boss intros, distant forest callouts, skeleton/zombie breathing, transformation roars.** |
| `assets/audio/01..41 Effort/Damage/Death Grunt` | 69 human male voice reactions (effort grunts, damage shock, death groans). | **Subtle human physicality behind heavy scythe swings, jumps, and taking damage.** |
