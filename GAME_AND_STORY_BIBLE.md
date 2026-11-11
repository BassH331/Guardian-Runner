# Guardian-Runner (Pixel-Runner) — Complete Game Mechanics, World Wiring & Story Bible

> **Purpose of this document:** Everything in this file describes **how the game is actually played**, **how every story beat is wired into the codebase and JSON configs**, **every character, boss, relic, and zone in Level 1 (`0px` to `36,000px`)**, and the **exact technical constraints** that any story rewrite must follow so ChatGPT (or any writer) can fix, deepen, and sharpen the narrative cleanly.

---

## 1. High-Level Pitch & Current Genre Identity

- **Working Titles in Repo:** *Guardian-Runner* / *Pixel-Runner* (built on a custom Python/Pygame engine called **V3X-Zulfiqar-Gideon**).
- **Genre:** Dark-fantasy **2D horizontal action side-scrolling runner + boss rush**, blending momentum-based traversal, stamina-gated scythe combat, horror/atmospheric exploration, and a branching **Corruption (`0–100%`)** morality spine.
- **Core Emotional Loop:** You sprint, leap, parry, and carve eastward through a cursed forest (`36,000px` total in Act I) haunted by undead remnants of your own fallen military company—the **Fourth Vanguard**—while two voices compete in your head (**Andras, Marquis of Discord** vs. **The Moon Knight / Candora's Envoy**). Every boss you defeat is one of your transformed comrades; beating them drops keepsake **Relics** that unlock playable powers (like **Demon Time**) and push your Corruption toward one of **three endings**.

---

## 2. How the Game Is Actually Played (Detailed Gameplay Mechanics)

### 2.1 Camera, Pacing & World Flow
- **Traversal Loop:** The player starts at the far western edge of the **Elderwood** (`0px`) and advances rightward across `36,000px` (`level_end_distance: 36000`).
- **Runner vs. Boss Arena Modes:**
  - During exploration/combat along the road, movement speed is deliberate (`_MOVE_SPEED = 3.4`, air speed `5.0`) and the runner is bounded within `0` to `65%` of screen width (`_RUN_RIGHT_BOUND_RATIO = 0.65`) as the world scrolls horizontally.
  - When a **Boss** spawns, camera scrolling locks into an arena duel and the player gains full agile arena speed (`_BOSS_ARENA_MOVE_SPEED = 6.8`, air speed `7.5`).
- **Jumping & Physics:**
  - Gravity `0.8`, jump velocity `-25.5`, **double jump** (`_MAX_JUMPS = 2`, second jump `-24.0`), and `0.12s` coyote time.
  - Solid props placed above ground (e.g., platforms/ledges) dynamically update ground height under both player and enemies (`EnvironmentManager.get_ground_y_at`).

### 2.2 Controls (`game_data/controls_config.json` + Special Hotkeys)
| Action | Keyboard | Controller (`JOYSTICK`) | Notes |
| :--- | :--- | :--- | :--- |
| Move Left / Right | `Left` / `Right` | Left Stick X (`AXIS_0`) | Movement |
| Jump / Double Jump | `Space` | `Button 0` (A) | Costs `12` Stamina per jump |
| Thrust Attack (Light) | `Q` | `Button 1` (B) | `0` Stamina; `15 dmg` (`20` Demon) |
| Smash Attack (Medium) | `E` | `Button 3` (Y) | `35` Stamina; `25 dmg` (`35` Demon) |
| Power Attack (Heavy) | `W` | `Button 2` (X) | `48` Stamina; `25 dmg` (`40` Demon) |
| Special Attack | `F` | `Button 6` (Back/LB) | `60` Stamina, invincible during cast; `35 dmg` (`50` Demon) |
| Defend / Parry | `R` | `Button 7` (Start/RB) | Timed guard/shield stance |
| Roll (Invincible Dodge) | `Left Shift` | `Button 4` | `20` Stamina, grants i-frames |
| Dash (Burst Mobility) | `Left Ctrl` | `Button 5` | `20` Stamina, speed `14.0` (`21.0` Demon) |
| Demon Transformation | `T` | `Button 8` | Costs `15` Mana upfront, drains `1.5/s` while active |
| **Demon Time (`[V]`)** | `V` | `Buttons 8 / 10 / 11` | **Unlocks only after Boss 1 (`the_eye` relic)** |
| **Ruby Elixir (Heal)** | `H` or HUD Slot 0 click | — | `3` permanent charges; **usable only at `<= 30%` HP** |
| **Narrative Confirm / Advance** | `Space` / `Enter` | `Buttons 0 / 1 / 2 / 6 / 7` | Used in Prologue, Relics, Endings, Overlays |

### 2.3 Resources, Survival & Combat Systems
- **Health (`HP`):** Base `100 HP` (upgrades to `200 max HP` if the player accepts Andras's Demonic Pact upon near/first death).
- **Ruby Elixir (`src/game/states/game_state.py` + `hud_overlay.py`):**
  - The player starts every run with a permanent **`Ruby Elixir` (`3` charges)** visible in Slot 0 of the top-right HUD strip.
  - When HP drops to **`<= 30%`**, a subtle Critical Health hint lets the player press `[H]` (or click Slot 0) to restore **`+60 HP`** and gain **`1.5s` invincibility**. Does **not** touch Corruption.
- **Stamina (`100` max):**
  - Gates jumps (`12`), roll (`20`), dash (`20`), smash (`35`), power (`48`), and special (`60`), while light thrust (`Q`) is free (`0`).
  - Regenerates at `15.0/sec` after a `1.2s` delay following any spend.
- **Mana (`200` max) & Demon Transformation (`T`):**
  - Demon Form is a spendable burst mode: activating costs `15` Mana and drains `1.5 Mana/sec` while enhanced (regenerates at `12.0/sec` only while human).
  - Enhances attack damages (`15->20`, `25->35`, `25->40`, `35->50`) and dash speed (`14.0->21.0`).
- **Mid-Run Death Pact (Andras Second Chance — `game_state.py`):**
  - Once per run, if player HP reaches `0`, time freezes and Andras appears (`CinematicNarrativeOverlay`) offering:
    - **`[1] Embrace the Darkness`:** Revives the player in-place with `200` max HP and Demon Form enabled (`is_enhanced = True`), triggering a void explosion.
    - **`[2] Die with Honor`:** Rejects Andras and transitions to Game Over.

### 2.4 Enemies, Traps & Boss Encounters
- **Regular Waves (`spawn_zones` in `level_1.json`):**
  - Across Zones 1–4, waves of **Skeleton Minions** (and occasional bats / zombified/goblin variants) patrol the forest (`max_skeletons` scales from `3` up to `5`; spawn delay tightens from `4.2s` to `2.8s`).
  - **Key Lore/Mechanic Rule:** Killing mindless Skeletons grants **`+5 Souls`** and **strictly `0.0` Corruption** (`CorruptionManager._on_entity_died` excludes skeletons—corruption only comes from meaningful choices/boss relics or non-skeleton kills).
- **Destructible Environmental Hazard — The Hellfire Skull Trap (`12,201px`):**
  - Placed in Zone 2 (`Large Skull.png`, 40-frame sprite sheet at `10x4` grid): loops frames `0..29` while belching fire onto ground level (`y=568` aligned).
  - Frames `11..13` telegraph the blast with glowing fire; frames `14..23` activate a ground hazard hitbox.
  - Has **`45 HP`**: attacking it destroys it cleanly (frames `30..39` shadow dissolve), rewarding **`+75 Souls`** (no corruption cleanse).
- **Boss Encounters (`BossEncounterManager`):**
  - When a boss spawns (`4,500px`, `13,500px`, `25,500px`, `34,500px`), AI freezes for `0.5s`, scales stats based on current Corruption, and delivers **1 corruption-variant line + 2–3 `pre_fight` dialogue lines** (`3.5s` each) before combat starts.
  - During the fight, the boss barks `combat_taunts` every `14–18s`.
  - On boss defeat: delivers its `death_line`, awards big Souls (`150–350` or `"remaining"`), triggers **Relic Drop(s)** into the top-right HUD strip, and pauses gameplay cleanly in **`RelicRevealState`** so the player reads the memory before continuing.

### 2.5 Special Gameplay Systems Linked to Story
1. **Soul Harvest Counter (`soul_harvest` in `level_1.json`):**
   - **Starts at `8,500` Souls** with a **`10,000` Soul Target** displayed on the HUD (`Skeleton=5`, `Zombie=8`, `Goblin=3`, `Hellfire Skull=75`, `Elite Boss=150`, `Mini Boss=300`, `Final Boss=remaining`).
   - Reaching `10,000` triggers **`event_soul_quota_betrayal`**.
2. **Demon Time & The Eye of Andras (`src/game/systems/demon_time_system.py`):**
   - Strictly **locked at game start**. Unlocks *only* when the player defeats Boss 1 (`BloodZombie` at `4,500px`) and collects **`the_eye`** relic.
   - Pressing **`[V]`** warps the screen in a radial twilight vignette and slows enemies/scrolling to **`0.15x` speed** for **`5.5s`** (`16.0s` cooldown).
   - Summons **The EYE Familiar** hovering `180px` above the player, hunting targets autonomously (`3 shots/sec`, `55 dmg` void blasts) while allowing a bonus **`[SPACE / A / F]` QTE Void Barrage** (`65 dmg`).
3. **Relic Memory Overlay & HUD Strip (`RelicRevealState` + `HUDOverlay`):**
   - Every collected relic opens a full-screen card showing its sprite, title, subtitle, `memory_text`, `lore`, and current `corruption_variants` (`low`/`mid`/`high`).
   - Enforces a **`0.85s` read grace lock** before `[SPACE]` / `[ENTER]` / `[ESC]` / click can dismiss it, then pins the icon to the **6-slot top-right Relic HUD Strip** (`Ruby Elixir` in Slot 0 + 5 earned relics).

---

## 3. World Geography: The 4 Zones & Complete Level 1 Timeline (`0px -> 36,000px`)

Level 1 (`"Act I - The Elderwood & The Fallen Watch"`) divides cleanly into **4 zones (`9,000px` each)**, each with its own music track, yellow zone banner, lore landmarks, NPCs, and boss climax:

| Zone | Distance | Zone Banner | Music Track (`master_audio_config.json`) | Boss Climax |
| :--- | :--- | :--- | :--- | :--- |
| **Zone 1** | `0 – 9,000px` | *(Starts directly after Prologue)* | `zone_1_music`: `2. One Last Day on Earth - 110bpm` | `4,500px` — **Corporal Vane** (`BloodZombie`) |
| **Zone 2** | `9,000 – 18,000px` | `ACT II: THE HOLLOWED GRAVES` | `zone_2_music`: `1 Exploration TomMusic.ogg` | `13,500px` — **Garrick, The Iron Bulwark** (`Gatekeeper`) |
| **Zone 3** | `18,000 – 27,000px` | `ACT III: CANDORA'S MOON-SHRINES` | `zone_3_music`: `1. For Better Tomorrow - 120bpm` | `25,500px` — **Pyromancer Solen** (`FireWizard`) |
| **Zone 4** | `27,000 – 36,000px` | `ACT IV: THE BLEEDING THRESHOLD` | `zone_4_music`: `Abyssal_Descent.mp3` | `34,500px` — **Commander Kaelen** (`DarkRonin`) |

*(Bosses override music with `boss_combat_music` `157bpm`, and Commander Kaelen plays `final_boss_music` `140bpm`.)*

### Chronological Beat-by-Beat Timeline Across Level 1
- **`0px` — Prologue (`StoryState`, 3 Chapters)** + HUD popup `event_prologue_awakening` (*"The Harvester's Brand"*).
- **`~850px` — First Enemy Kill (`first_kill` flag):** Triggers `event_first_kill` (Andras speaks to you on your first kill).
- **`1,013px` — NPC Event #10: Chronicle of the Fourth Vanguard (Magic Book):**
  - Triggers `event_sealed_book_encounter` popup AND when touched triggers the **Book Opening Ritual** (`CinematicNarrativeOverlay`, ancient grimoire + Elder Futhark runes -> screen goes dark into the Void -> **Andras introduces himself directly**).
- **`1,056px` — Prop Lore:** *Carcass of the Sky-Drake* (dragon carcass felled by Commander Kaelen during the vanguard's entry charge).
- **`1,200px` — Checkpoint #1.**
- **`2,389px` — Prop Lore:** *Corporal Vane's Perimeter Torch* (triple-watch perimeter).
- **`3,200px` — Ambient Lore #101:** *Vane's Distress Cipher* (seven hash-marks carved into bleeding bark).
- **`4,500px` — BOSS 1 (Entity #14): Corporal Vane, The Weeping Husk (`BloodZombie`)**
  - Arena popup `event_boss_blood_zombie` -> pre-fight dialogue -> combat -> death line.
  - Drops **`bark_of_the_great_one`** (`+10` Corruption) & **`the_eye`** (`+12` Corruption).
- **`4,600px` — Event:** `event_demon_time_unlocked` (*"Ocular Prism: The Eye of Andras"* — unlocks `[V]` Demon Time).
- **`5,651px` — Prop Lore:** *Ashes of the Vanguard Bivouac* (four bedrolls & Watch kettle).
- **`8,391px` — Prop Lore:** *The Weeping Boundary Oak* (graves of past failed runners).
- **`9,000px` — Zone 2 Transition:** Banner `ACT II: THE HOLLOWED GRAVES`.
- **`9,650px` — Prop Lore:** *Cairn of the Shield-Brethren* (stacked stones + dented helmet).
- **`10,500px` — NPC Event #13: The Moonstone Keeper** (`event_moonstone_keeper`).
- **`12,201px` — Hazard Trap:** Animated **Large Hellfire Skull** (`45 HP`, destructible for `+75` Souls).
- **`13,500px` — BOSS 2 (Entity #1): Garrick, The Iron Bulwark (`Gatekeeper`)**
  - Arena popup `event_gatekeeper_encounter` -> pre-fight dialogue -> combat -> death line.
  - Drops **`shattered_gauntlet`** (`+8` Corruption) & **`tainted_sigil`** (`+10` Corruption).
- **`15,400px` — Prop Lore:** *Scribe Orin's Watchfire* (charred muster roll pages).
- **`16,500px` — NPC Event #21: Scribe Orin of the Watch** (speaks about recording the fallen; checks corruption).
- **`18,000px` — Zone 3 Transition:** Banner `ACT III: CANDORA'S MOON-SHRINES`.
- **`19,200px` — Prop Lore:** *Candora's Weeping Moon-Shrine* (consecrated statue by Lyra & Solen).
- **`19,800px` — Ambient Lore #103:** *Sanctuary of the Silver Moon* (white lilies & Solen's wildfire).
- **`~20,000px` (or whenever `10,000` Souls reached) — Milestone:** `event_soul_quota_betrayal` (*"Andras's True Design"*).
- **`21,200px` — NPC Event #22: Candora's Envoy (Moon Knight)** (warns you that Solen holds a purifying Tear).
- **`22,360px` — Prop Lore:** *Pyromancer Solen's Sanctuary Hearth*.
- **`24,600px` — Prop Lore:** *Altar of the Silver Tear* (scorched prayer beads).
- **`25,500px` — BOSS 3 (Entity #25): Pyromancer Solen, The Ash Keeper (`FireWizard`)**
  - Arena popup `event_pyromancer_solen` -> pre-fight dialogue -> combat -> death line.
  - Drops **`candoras_tear`** (**`-20` Corruption** — major purification turning point!).
- **`27,000px` — Zone 4 Transition:** Banner `ACT IV: THE BLEEDING THRESHOLD`.
- **`28,800px` — Ambient Lore #104:** *Trail of the First Vessel* (clean lightning-fast sword scars).
- **`30,200px` — NPC Event #28: Echo of Lieutenant Marek** (reveals Kaelen went ahead alone to spare the rest).
- **`31,100px` — Prop Lore:** *Commander Kaelen's Final Vigil* (scabbard & carved message).
- **`32,600px` — Ambient Lore #105:** *The Bleeding Great Tree* (wind dies before the final duel).
- **`33,600px` — Prop Lore:** *Sanctum of the Bleeding Great Tree*.
- **`34,500px` — FINAL BOSS (Entity #3): Commander Kaelen, The Hollowed Mentor (`DarkRonin`)**
  - Arena popup `event_fabricators_enforcer` -> pre-fight dialogue -> combat -> death line.
  - Drops **`amalgam_core`** (`+15` Corruption) + **`candoras_tear`** (`-20` Corruption). *(Note: currently `DarkRonin` in `relic_boss_map` grants both `amalgam_core` and a `candoras_tear` entry!)*
- **`36,000px` / Final Boss Defeat + Final Relics Dismissed:**
  - `EndingManager` checks final `corruption_value` (`<= 25` Light / `26..74` Ambiguous / `>= 75` Dark) -> plays `EndingState` (`title`, `lines`, `outro_speaker`, credits, save to `slot_auto.json`).
  - *(Note: `level_1.json` has `"next_level": "level_2.json"`, and reaching `36,000px` also shows `event_level_complete`. However, `game_data/level_2.json` is currently an unfinished 4-layer Hell stub with `"New NPC"` placeholder text `"..."`—Act I `level_1.json` is the complete game right now.)*

---

## 4. How the Story Is Wired Into Code & JSON Files

| Story Surface in Game | Source File / Key | Trigger & Presentation Style |
| :--- | :--- | :--- |
| **Opening Prologue (3 Pages)** | `src/game/states/story_state.py` (`_PROLOGUE_CHAPTERS`) | Plays before Level 1 starts; typewriter dialogue box + glow embers; `[SPACE]` completes/advances. |
| **Non-Blocking HUD Popups** | `game_data/scene_popups_config.json` + `game_data/notification_config.json` | Gold/crimson/arcane slide-in card (`SideNotification`, `default_hold_time: 8.5s`). |
| **Ambient World Landmarks** | `game_data/level_1.json` -> `world_events` (`ambient_lore`) & `environment.props` (`lore_title`/`lore_text`) | Fires on world distance proximity; gated behind `not side_notification.is_active` for props so cards don't pile up. |
| **Friendly/Lore NPC Encounters** | `game_data/level_1.json` -> `world_events` (`type: "npc"`) | Triggers near NPC (`radius: 160`); has `default` + `corruption_variants` (`low/mid/high`). |
| **Magic Book Ritual & Void Intro** | `src/game/states/game_state.py` (`lines 1845–1877`) | **Hardcoded in Python** (`ANCIENT GRIMOIRE [SEAL OF ANDRAS]` + `Andras, Marquis of Discord`). Pauses combat in full dark Void scrim (`CinematicNarrativeOverlay`). |
| **Near-Death Demon Pact** | `src/game/states/game_state.py` (`lines 2223–2238`) | **Hardcoded in Python.** First time HP hits `0`, offers `[1] Embrace the Darkness` or `[2] Die with Honor`. |
| **Boss Intro / Taunts / Death** | `game_data/storyline_config.json` -> `boss_dialogue` + `BossEncounterManager` | Boss freezes `0.5s`, delivers `corruption_variants` + `pre_fight` lines (`3.5s` each), barks `combat_taunts`, speaks `death_line`. |
| **Relic Memory Cards** | `game_data/storyline_config.json` -> `relics` & `relic_boss_map` + `RelicRevealState` | Fullscreen card (`0.85s` read lock). Displays `title`, `subtitle`, `memory_text`, `lore`, `corruption_variants` + updates Corruption. |
| **Two-Voice Whispers** | `game_data/storyline_config.json` -> `whisperer_barks` + `WhispererSystem` | Non-blocking barks on `on_relic`, `on_near_death`, `on_boss_spawn`, `on_threshold_crossed` (`33, 50, 66, 90%`). `COOLDOWN = 55.0s`. (`on_kill` is currently muted to stop spam.) |
| **3 Branching Endings** | `game_data/storyline_config.json` -> `endings` (`dark`, `light`, `ambiguous`) | Triggered after Final Boss + Final Relics close (`<=25`, `26–74`, `>=75`). 4 narrative lines + outro from `ANDRAS` or `MOON KNIGHT`. |

### ⚠️ Legacy Hardcoded Mismatches Still Inside `src/game/states/game_state.py`
ChatGPT should know about **two hardcoded Python strings** that still use old placeholder/contradictory framing and should be updated alongside any JSON rewrite:
1. **`game_state.py` line 871–875 (fallback for `event_soul_quota_betrayal`):** Still mentions *"The Arch-Fabricator's contract was a trap... Keep the Scythe... hunt the Holy Artifacts!"* (remnant of an older villain name before Andras became the sole antagonist).
2. **`game_state.py` line 1866–1869 (Magic Book void dialogue from Andras):** Still says *"The book in your hands is deadly, mortal—bound to this realm. You will wander blind without my flame. Keep the book, we'll talk soon warrior."* — which doesn't clearly connect to the Fourth Vanguard or why Andras branded the player!

---

## 5. Cast, Factions & Current Story Summary ("The Harvester's Key")

### Cast & Roles
- **The Player (The Last Watchman / Branded Harvester):** Only survivor of the Fourth Vanguard, wielding a giant scythe (Watch weapon or Andras-forged weapon—needs crystal-clear identity!). Starts with a cursed mark on the palm and `8,500` Souls already etched onto it (implying the prior battle/company slaughter already pushed the tally close to `10,000`!).
- **Andras, Marquis of Discord (`assets/Agis`):** Imprisoned demon beneath the Elderwood's Bleeding Great Tree. Voice in the HUD (`andras` whisperer), Book Ritual intruder, and Death Pact tempter.
- **Candora & The Moon Knight (`Moonstone Keeper` sprite):** Goddess of silver moonlight / mercy and her envoy guiding the player to stay human and remember their squad instead of feeding bloodlust.
- **The Four Bosses (Your Transformed Fourth Vanguard Officers):**
  1. **Corporal Vane (`BloodZombie` @ `4,500px`):** Scout/lookout at the Verge; drank crimson sap to stay awake on triple-watch until transformed. Drops `bark_of_the_great_one` (`+10` Corr) and `the_eye` (`+12` Corr).
  2. **Garrick (`Gatekeeper` @ `13,500px`):** Shield-brother fused to the Obsidian Arch; refused to abandon the rear line. Drops `shattered_gauntlet` (`+8` Corr) and `tainted_sigil` (`+10` Corr).
  3. **Pyromancer Solen (`FireWizard` @ `25,500px`):** Sanctifier at Candora's Moon-Shrines whose hearth-fire went wild; hid `candoras_tear` (`-20` Corr) beneath his robes to cleanse you.
  4. **Commander Kaelen (`DarkRonin` @ `34,500px`):** Your mentor who marched alone to the Bleeding Tree to hold the innermost seal. Drops `amalgam_core` (`+15` Corr) and currently also lists `candoras_tear` (`-20` Corr).
- **Supporting Voices (Props & World NPCs):**
  - **Scribe Orin** (NPC @ `16,500px`, Inkwell/Ledger relics)
  - **Medic Lyra** (referenced in Herbalist's Satchel relic & Moon-Shrine prop)
  - **Lieutenant Marek** (NPC @ `30,200px`, Kaelen's second-in-command)
  - **The Moonstone Keeper** (NPC @ `10,500px`) & **Candora's Envoy** (NPC @ `21,200px`)

### Current Premise Summary (What Exists Right Now)
- **Why Andras needs you:** Beneath the Elderwood's Bleeding Great Tree lies the Rift-Gate, sealed by the Citadel's Watch-forged **Star-Fire Seal**. No demon can break a Watch ward from the inside—only a living Guardian carrying a Watch oath can open it from outside. When Vane, Garrick, Solen, and Kaelen refused to break the Seal even under torment, they used their cursed bodies as living locks across the four thresholds. In fury, Andras spared **you** and burned a **Harvest Sigil** onto your palm so your scythe would reap `10,000` souls and slay the four captains—turning *you* into the key that opens his cage.
- **Why you fight forward:** The brand burns closer to your heart, the road home is sealed, and you march forward to free your four brothers from living armor, claim Candora's Silver Tear from Solen, and collapse the Rift on Andras's skull instead of opening it.

---

## 6. Why the User Still Wants ChatGPT to Fix/Elevate the Story

Even with the "Harvester's Key" update, key dramatic and logical questions remain open for a master storyteller to nail:
1. **The Opening Hook & Personal Stakes:** Why did the protagonist survive the Fourth Vanguard's massacre? Was the player knocked unconscious, betrayed, tricked into touching the Grimoire at `1,013px`, or forced to take a desperate pact *to save someone back at the Citadel*? Right now, starting at `8,500 / 10,000` Souls isn't explicitly explained in Chapter I!
2. **True Agency vs. Illusion of Choice:** If killing your four trapped captains is *what Andras wants* (to unlock the wards), how does fighting and killing them actually allow the Light ending instead of just doing Andras's dirty work? Right now the player *has* to kill all 4 bosses to finish Level 1—so the Light ending needs a sharp narrative twist explaining **why slaying them with Candora's Tear / Watch Oath *seals* rather than *opens* the gate**, whereas slaying them under high Corruption *unlocks* it!
3. **Cohesion of Mechanics & Narrative:**
   - Why do we pick up **The Eye of Andras** from Vane and use **Demon Time (`[V]`)** + **Demon Form (`[T]`)** + the **Scythe**? Should using Demon Form (`[T]`) or Demon Time (`[V]`) carry clear dramatic weight in the story?
   - Why does **Entity #10 (`Chronicle of the Fourth Vanguard`, Magic Book @ `1,013px`)** trigger an ancient Runic ritual that summons Andras in the Void? Right now that cutscene reads like an unrelated legacy encounter rather than the exact moment Andras reveals his snare (or tricks you).
   - How do the **3 Endings (`dark <= 25%?` wait: `light <= 25`, `ambiguous 26..74`, `dark >= 75`)** feel earned given that boss relics net `+8 +10 +10 +12 -20 +15 -20 = +15%` Corruption (Wait: notice `DarkRonin` drops `candoras_tear` `-20` right at the end too, which might accidentally swing Corruption down! Should `DarkRonin` drop only `amalgam_core`, or how should Corruption actually move across a playthrough?).
4. **Emotional Weight & Restraint:** Keeping popups brief, punchy, atmospheric, and character-driven so players feel grief, brotherhood, dread, and triumph *while running and fighting* instead of reading walls of exposition.

---

## 7. Strict UI, Schema & Test Rules (Read Before Rewriting!)

If ChatGPT generates rewritten dialogue, lore, or JSON blocks, it **must obey these rules** so nothing breaks in-engine or fails the automated `pytest` suite (`69` tests):

1. **Preserve Exact JSON Keys & IDs:**
   - **Relic IDs (`relics`):** `shattered_gauntlet`, `herbalists_satchel`, `tainted_sigil`, `voragis_inkwell`, `vial_of_void_blood`, `hollowed_ledger_page`, `candoras_tear`, `amalgam_core`, `bark_of_the_great_one`, `the_eye` (every relic **must** keep non-empty `memory_text`, `lore`, and `corruption_variants.low / mid / high`).
   - **Boss Keys (`boss_dialogue` & `relic_boss_map`):** Must keep `BloodZombie`, `Gatekeeper`, `FireWizard`, `DarkRonin` (plus their display titles `Corporal Vane, The Weeping Husk`, `Garrick, The Iron Bulwark`, `Pyromancer Solen, The Ash Keeper`, `Commander Kaelen, The Hollowed Mentor`), each with **`>= 2` `pre_fight` lines**, **`death_line`**, **`>= 2` `combat_taunts`**, and `corruption_variants.low / mid / high`.
   - **Ending Keys (`endings`):** `dark`, `light`, `ambiguous` (`title`, `lines` array of 4 lines, `andras_outro` or `moon_knight_outro`).
   - **4 Zone Coverage (`level_1.json`):** Each of the 4 zones (`0–9000`, `9000–18000`, `18000–27000`, `27000–36000`) must keep `>= 3` props, `>= 2` interactive `lore_text` props (including a prop with `"Vane"` in the title near `~2389px`), and `>= 3` `world_events`.
2. **Forbidden Legacy Strings (`tests/test_story_props_and_music_zones.py`):**
   - Never use: `"New custom spoken line"`, `"milk-livered bastard"`, `"Pure shite"`, `"The Fabricator's Enforcer"`, `"Clanking gears of malice"`, `"mortal demies"`, `"DONT LOSE YOURSELF TO THE FOREST WARRIOR"`.
   - Avoid Unicode em-dashes (`—`) where plain ASCII hyphens (`-`) keep pixel font `Abaddon Bold.ttf` rendering crisp (`StoryState`, HUD banners, side notifications).
3. **Word/Character Budgets per UI Box (Critical for Readability!):**
   - **`StoryState` Prologue Chapter (`box_w` ~`1160px`, `box_h` `280px`, 24pt font):** Max **~55–68 words per chapter** (3 chapters max, ~4–5 wrapped lines max so text never collides with `[ PRESS SPACE OR ENTER TO CONTINUE ]`).
   - **`SideNotification` (`scene_popups_config.json`, `ambient_lore`, `whisperer_barks`, `prop.lore_text`):** Tab width is `390px` at 1280x720 (`15px` body font). Keep popups crisp: **Title <= 35 chars**, **Body <= 130–160 chars (~22–28 words)** so players can read them mid-combat in a single glance.
   - **`BossEncounterManager` Intro Lines (`pre_fight` & `corruption_variants`):** Each line shows for **`3.5 seconds`** during combat freeze. Keep each line **<= 150 chars (~20–26 words)**!
   - **`RelicRevealState` (`memory_text` + `lore`):** Dedicated pause screen—can hold **~20–35 words** for `memory_text` and **~35–55 words** for `lore`, plus a `15–25 word` `corruption_variants` reflection.
   - **`EndingState` (`lines`):** Displays one line at a time (`3.0s` each) at `17px` font—keep each of the 4 `lines` **<= 120 chars (~16–22 words)**.

---

## 8. Suggested Prompt You Can Paste Into ChatGPT With This File

> *"Read this entire Game & Story Bible carefully. Keep all gameplay mechanics, 4 zones (`0–36,000px`), 4 bosses, Demon Time (`[V]`), Soul Harvest (`8,500->10,000`), and JSON/word-count rules intact. Fix the plot holes, sharpen Andras's true motive vs. the player's reason to fight (especially why killing the 4 corrupted captains leads to BOTH the Light seal ending and Dark betrayal ending), tie in the Book Ritual (`1,013px`) and Death Pact (`200 HP` revive), and rewrite: (1) the 3-chapter Prologue, (2) all `scene_popups_config.json` & Magic Book Void lines, (3) all 4 boss dialogues & death lines, (4) key `whisperer_barks`, and (5) the 3 Endings—fitting every exact word/character limit in Section 7."*

