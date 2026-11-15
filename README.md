# Vibe Create — Local Game Workbench

Turn a short game idea into a playable, offline-first game slice — all running
locally on your Mac via Ollama. Nothing is sent to a hosted service.

Vibe Create has two build modes:

| Mode | Output | Runs in browser? | Needs Godot? |
|------|--------|------------------|--------------|
| **Quest RPG · Browser** | Self-contained `index.html` (top-down RPG) | ✅ Yes | No |
| **2D sandbox · Godot** | Godot 4.3+ project + HTML5 canvas port | ✅ Yes (via web export) | No (native run needs Godot) |

Every completed project can be exported as a **web-installable PWA zip**:
`index.html` + `manifest.json` + `service-worker.js` + icons + `README.md`.
Unzip on any device (phone, tablet, desktop), open `index.html`, and play —
offline, with an "Add to Home Screen" option.

---

## Table of contents

1. [One-command install](#one-command-install)
2. [Step-by-step setup](#step-by-step-setup)
3. [Running the workbench](#running-the-workbench)
4. [Generating a game](#generating-a-game)
5. [Creation knobs & dials](#creation-knobs--dials)
6. [Exporting for the web](#exporting-for-the-web)
7. [Project structure](#project-structure)
8. [Troubleshooting](#troubleshooting)

---

## One-command install

```bash
curl -fsSL https://raw.githubusercontent.com/thefortressentertainment-pixel/vibe-create/main/install.sh | bash
```

Or clone and run locally:

```bash
git clone https://github.com/thefortressentertainment-pixel/vibe-create.git
cd vibe-create
bash install.sh
```

The installer:

1. Installs **Ollama** if missing (via Homebrew on macOS, or the official install
   script on Linux).
2. Starts the Ollama server on `http://127.0.0.1:11434`.
3. Pulls the required LLM models:
   - `qwen3.5:2b` — local game-content planner (default)
   - `qwen2.5vl:3b` — local vision reviewer
   - `qwen3.5:4b` — Blender Python script generation & repair
4. Checks for optional tools (**Blender**, **Godot 4.3+**) and reports status.
5. Makes all Python generator scripts executable.

### Optional tools

| Tool | Purpose | Install |
|------|---------|---------|
| Blender | Blender 3D concept stages (`.blend`, `.fbx`) | `brew install --cask blender` (macOS) or [blender.org](https://blender.org) |
| Godot 4.3+ | Run Godot sandbox builds natively | `brew install --cask godot` (macOS) or [godotengine.org](https://godotengine.org) |

These are optional — the workbench and all web exports function without them.
If Godot is installed elsewhere, set `VIBE_GODOT_BIN` to its executable path.

---

## Step-by-step setup

### 1. Clone the repo

```bash
git clone https://github.com/thefortressentertainment-pixel/vibe-create.git
cd vibe-create
```

### 2. Run the installer

```bash
bash install.sh
```

This installs/starts Ollama and pulls the three required models. First pull can
take several minutes depending on your connection.

### 3. Verify Ollama and models

```bash
ollama list
```

You should see `qwen3.5:2b`, `qwen2.5vl:3b`, and `qwen3.5:4b` listed.

### 4. Start the workbench

```bash
python3 scripts/workbench_server.py
```

You'll see:

```
Vibe Create local workbench: http://127.0.0.1:8765
```

### 5. Open the workbench

Open your browser to:

```
http://127.0.0.1:8765
```

The local-only workbench loads. The sidebar shows the status of Ollama, Blender,
and Godot.

---

## Generating a game

1. **Choose a build type:**
   - `2D sandbox · Godot` — seeded side-scrolling sandbox with terrain chunks,
     mining, placement, crafting, one enemy, and local save/reload. Exports to
     a playable HTML5 canvas via "Export for web".
   - `Quest RPG · Browser` — offline top-down RPG vertical slice with quest, NPC,
     collectibles, enemy, and altar. Already a self-contained `index.html`.

2. **Enter your world idea** in the creative brief (or click an idea chip).

3. **Adjust the knobs & dials** (see below) to shape generation.

4. **Click "Generate game."** A job panel shows progress through planning,
   asset generation, engine build, and visual review.

5. When complete, the project appears in "Latest Creation" and in the Projects
   view. Use the file links to download the world preview, art review sheet,
   game content, and project manifest.

---

## Creation knobs & dials

The sandbox composer exposes these knobs so you can collaborate with the local
agent shaping each generation:

| Knob | Values | Effect |
|------|--------|--------|
| **Palette** | Auto / Verdant Depths / Murkfen Lanterns / Blueglass Frost / Ashen Foundry | World color theme |
| **Difficulty** | Easy / Normal / Hard | Enemy health & attack (Easy −1, Hard +1, clamped) |
| **Biome / Mood** | Temperate / Overgrown / Barren / Fractured | Terrain shape: surface amplitude, cave radius, tree frequency |
| **Enemy Count** | 1 / 2 / 3 | Number of cave slimes spawned |
| **Enemy Behavior** | Patrol / Stationary / Aggressive | Walk speed and chase range |
| **Starting Wood** | 0–8 | Logs in starting inventory |
| **Starting Dirt** | 0–20 | Dirt blocks in starting inventory |
| **Gravity** | 600 / 920 / 1200 | Physics pull strength |
| **Jump Height** | -280 / -360 / -440 | Jump impulse |
| **Move Speed** | 120 / 185 / 260 | Player movement speed |
| **Camera Zoom** | 0.5 / 1.0 / 1.5 | Wide vs close-up view |
| **Save Interval** | 1 / 3 / 5 / 10 | Auto-save frequency (seconds) |
| **Chaos / Randomness** | 0 / 1 / 2 | Terrain perturbation multiplier |
| **Review Strictness** | Lenient / Standard / Strict | Local vision review bar |

All knob values are stored in the generated `world-spec.json`, so the same
settings reproduce the same world.

---

## Exporting for the web

Every completed project shows a **WEB READY** badge when a web export exists.

1. Select a completed project in the workbench.
2. Click **↗ Export for web** in the output card.
3. A `<project-id>-web.zip` downloads and the exported package opens in a new
   browser tab automatically.
4. To share: unzip the folder on any device and open `index.html`. The game runs
   entirely offline. On iPhone/iPad (Safari) or Android (Chrome), use "Add to
   Home Screen" to install it like a native app.

The zip contains:
- `index.html` — the complete playable game (HTML5 canvas sandbox for Godot
  projects, or the existing quest-prototype HTML for browser projects)
- `manifest.json` — PWA install manifest
- `service-worker.js` — offline-first cache
- `icon-192.png` / `icon-512.png` — home-screen icons derived from preview art
- `game-content.json` / `world-spec.json` — generated world & encounter data
- `sandbox-game/Art/*.png` — tile atlas and sprite sheets (sandbox mode)
- `README.md` — per-device install instructions

---

## Project structure

```
vibe-create/
├── install.sh              # One-command installer (Ollama + models + checks)
├── README.md               # This guide
├── .gitignore              # Excludes generated projects & binaries
├── docs/
│   └── game-creation-workbench.md
├── schemas/
│   ├── game-content.schema.json
│   └── game-project.schema.json
├── scripts/
│   ├── workbench_server.py     # Local HTTP workbench + API + export endpoints
│   ├── generate_sandbox.py     # Godot 4 side-scrolling sandbox + HTML5 port
│   ├── idea_to_game.py         # Quest RPG browser prototype
│   ├── local_game_planner.py   # Ollama game-content planner
│   ├── local_pixel_art_review.py # Local vision review of pixel art
│   ├── local_visual_review.py  # Local vision review of Blender renders
│   ├── project_adapter.py      # Unreal project inspection & staging
│   ├── pwa_export.py           # PWA package builder (manifest, SW, icons)
│   └── web_sandbox_export.py   # HTML5 canvas sandbox generator
└── web/
    ├── index.html    # Workbench UI
    ├── app.js        # Workbench frontend logic
    └── app.css       # Workbench styles
```

Generated projects live under `projects/` (gitignored — they contain per-user
artifacts and binaries).

---

## Troubleshooting

**Ollama not running**
```
ollama serve        # start in one terminal
ollama list         # verify models in another
```
Or restart via the workbench — it will suggest starting Ollama.

**Model pull fails**
```bash
ollama pull qwen3.5:2b
ollama pull qwen2.5vl:3b
ollama pull qwen3.5:4b
```

**Godot sandbox won't launch**
Install Godot 4.3+ and/or set `VIBE_GODOT_BIN`:
```bash
export VIBE_GODOT_BIN="/Applications/Godot.app/Contents/MacOS/Godot"
python3 scripts/workbench_server.py
```
The web export still produces a playable HTML5 canvas without Godot.

**Blender stages fail**
Install Blender and ensure it's on PATH or at the default macOS location
(`/Applications/Blender.app/Contents/MacOS/Blender`). Blender stages are
optional — the playable game is generated regardless.

**Port already in use**
The workbench defaults to port `8765`. No port flag is exposed; change
`WorkbenchHandler`/`main()` in `scripts/workbench_server.py` if needed.

**Generation errors**
Each project writes `workbench.log` in its folder. Open it from the workbench
job panel or read `projects/<id>/workbench.log` directly.

---

## License

MIT — generate, modify, and ship locally. No cloud required.
