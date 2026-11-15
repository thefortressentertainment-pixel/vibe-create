# Vibe Create local workbench

Double-click **Vibe Create** on the Desktop. It starts a small server bound to `127.0.0.1` and opens the browser workbench. The generation pipeline calls Ollama on localhost and does not send prompts or images to a hosted service.

## Seeded sandbox build

Choose **2D sandbox · Godot**, enter an idea, choose a fixed seed, and select 4–16 connected chunks. The default is eight chunks of 32 tiles each. Press **Generate game** to create the world and art files. The workbench displays a world preview and a separate art review sheet, with direct links to each generated atlas, sprite sheet, specification, and review report.

Install Godot 4.3 or newer to run a generated sandbox. The workbench detects the app or a `godot` executable on `PATH`; `VIBE_GODOT_BIN` can point to a custom executable. Use **Run in Godot** to launch the game or **Open Godot project** to open its editor. Without Godot, the project and all preview artifacts still generate and remain reviewable from the workbench.

In the game, use A/D or arrow keys to move, Space/W/Up to jump, left-click to mine, right-click to place dirt, and J to strike the cave slime. Mine four tree blocks to craft a wooden pickaxe. Terrain edits save immediately, player position and inventory auto-save, and the in-game Save and Reload buttons operate on a project-specific file under Godot's `user://saves` directory.

The terrain seed is stored in `world-spec.json`. Surface and cave profiles use global tile coordinates while generation proceeds in chunks, so a fixed seed recreates the same world and chunk boundaries share the same terrain columns. Art uses 16-pixel cells and one named palette selected from the idea's biome cues.

## Project iteration and sharing

The current sandbox generator builds from a fixed Godot template. Its local planner fills in the world brief, but it does not yet invent arbitrary gameplay systems or apply natural-language tweak requests to an existing project. There is no per-project revision history or test-and-rollback panel yet.

Use **Download shareable ZIP** on a selected project to package its source, art, project brief, and manifest under one folder. The archive omits Godot's `.godot` editor cache and local workbench log so another person can open the included project in Godot without receiving machine-specific cache files.

The ZIP is a source project, not a device-specific executable. Desktop, web, and mobile exports need target-specific Godot presets and export templates; some targets also require their platform SDKs. Device builds are a separate next step after the project has a reliable revision and validation loop.

## Quest build

Choose **Quest RPG · Browser** to use the earlier top-down browser prototype. Blender scene generation and local render review are optional in that mode. An Unreal `.uproject` can still be selected to stage the concept assets.

## Project files

Projects are stored in `projects/` in this repository. A sandbox project contains:

- `sandbox-game/project.godot` and `sandbox-game/Scenes/Main.tscn`: Godot 4.3+ project entry point.
- `sandbox-game/Scripts/`: chunk terrain, mining and placement, movement, crafting, enemy behavior, and save/reload logic.
- `sandbox-game/Art/tiles.png`, `player-sheet.png`, and `slime-sheet.png`: generated 16-pixel atlas and animation frames.
- `world-preview.png` and `art-review.png`: generated workbench previews.
- `world-spec.json`, `asset-style.json`, and `game-content.json`: reproducible world inputs, shared palette, and local content plan.
- `pixel-art-review.json`: optional local vision feedback. It is advisory and does not edit art.
- `project.json` and `workbench.log`: pipeline manifest and local build log.

## Local implementation

The Desktop app runs [`scripts/workbench_server.py`](../scripts/workbench_server.py), which serves [`web/index.html`](../web/index.html) and starts either [`scripts/generate_sandbox.py`](../scripts/generate_sandbox.py) or the earlier [`scripts/idea_to_game.py`](../scripts/idea_to_game.py). The sandbox's PNG artwork is drawn with the Python standard library; the runtime uses Godot's `TileMapLayer` and tile collision. The local vision reviewer is [`scripts/local_pixel_art_review.py`](../scripts/local_pixel_art_review.py).

The current milestone is one compact sandbox slice: seeded surface and cave, connected chunks, player movement and jumping, mining and block placement, a wooden-pickaxe recipe, one cave enemy, and local save/reload. A project-aware tweak loop, revision snapshots, play-test notes, platform export presets, larger worlds, refined terrain transitions, inventory screens, more recipes and enemies, combat depth, weather, richer animation, and image-model-generated production art remain future work.
