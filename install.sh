#!/usr/bin/env bash
#
# Vibe Create — One-command installer
#
# Installs everything needed to run the Vibe Create local game workbench on
# this machine:
#   1. Ollama (local LLM runtime) — installed if missing, then started
#   2. Required LLM models — qwen3.5:2b (planner), qwen2.5vl:3b (vision),
#      qwen3.5:4b (Blender script repair)
#   3. Optional tool checks — Blender (for 3D concept stages), Godot 4.3+
#      (for running Godot sandbox builds natively)
#   4. Makes all Python generator scripts executable
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/thefortressentertainment-pixel/vibe-create/main/install.sh | bash
#   # or
#   bash install.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$REPO_ROOT/scripts"

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
info()  { printf '\033[1;36m[info]\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m[ok  ]\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
err()   { printf '\033[1;31m[err ]\033[0m %s\n' "$*" >&2; }

have()  { command -v "$1" >/dev/null 2>&1; }

os_name() {
  case "$(uname -s)" in
    Darwin*) echo "macos" ;;
    Linux*)  echo "linux" ;;
    *)       echo "unknown" ;;
  esac
}

# -----------------------------------------------------------------------------
# 1. Ollama
# -----------------------------------------------------------------------------
install_ollama() {
  if have ollama; then
    ok "Ollama already installed: $(ollama --version 2>/dev/null || echo unknown)"
    return 0
  fi

  info "Installing Ollama..."
  local os
  os="$(os_name)"
  if [[ "$os" == "macos" ]]; then
    if have brew; then
      brew install ollama || true
    else
      # Official Ollama install (macOS + Linux)
      curl -fsSL https://ollama.com/install.sh | sh
    fi
  elif [[ "$os" == "linux" ]]; then
    curl -fsSL https://ollama.com/install.sh | sh
  else
    err "Unsupported OS for automatic Ollama install. Install manually from https://ollama.com"
    return 1
  fi

  if ! have ollama; then
    err "Ollama installation did not place 'ollama' on PATH. Install manually from https://ollama.com"
    return 1
  fi
  ok "Ollama installed."
}

start_ollama() {
  info "Ensuring Ollama is running..."
  if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    ok "Ollama is already running on http://127.0.0.1:11434"
    return 0
  fi

  # Start ollama serve in the background (detached)
  nohup ollama serve >/tmp/vibe-create-ollama.log 2>&1 &
  local tries=0
  while [[ $tries -lt 30 ]]; do
    if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
      ok "Ollama is running."
      return 0
    fi
    sleep 1
    tries=$((tries + 1))
  done
  err "Ollama did not become reachable. Check /tmp/vibe-create-ollama.log"
  return 1
}

pull_models() {
  local models=(
    "qwen3.5:2b"      # local game-content planner (default)
    "qwen2.5vl:3b"    # local vision reviewer (pixel art / Blender renders)
    "qwen3.5:4b"      # Blender Python script generation & repair
  )
  info "Pulling required Ollama models (this may take several minutes)..."
  for model in "${models[@]}"; do
    info "Pulling $model ..."
    if ollama pull "$model" >/dev/null 2>&1; then
      ok "Pulled $model"
    else
      warn "Could not pull $model automatically. Run: ollama pull $model"
    fi
  done
}

# -----------------------------------------------------------------------------
# 2. Optional tools (Blender, Godot)
# -----------------------------------------------------------------------------
check_optional_tools() {
  info "Checking optional tools..."
  if have blender || [[ -x "/Applications/Blender.app/Contents/MacOS/Blender" ]]; then
    ok "Blender found (Blender concept stages available)."
  else
    warn "Blender not found. Blender 3D concept stages will be skipped unless installed."
    warn "  macOS: brew install --cask blender   or   https://blender.org"
  fi

  if have godot || have godot4 || [[ -x "/Applications/Godot.app/Contents/MacOS/Godot" ]]; then
    ok "Godot found (Godot 4.3+ sandbox runtime available)."
  else
    warn "Godot 4.3+ not found. Godot sandbox builds generate but need Godot to run locally."
    warn "  macOS: brew install --cask godot   or   https://godotengine.org"
    warn "  Set VIBE_GODOT_BIN to point at your Godot executable if installed elsewhere."
  fi
}

# -----------------------------------------------------------------------------
# 3. Make scripts executable
# -----------------------------------------------------------------------------
chmod_scripts() {
  info "Making generator scripts executable..."
  chmod +x "$SCRIPTS_DIR"/*.py 2>/dev/null || true
  ok "Scripts are executable."
}

# -----------------------------------------------------------------------------
# 4. Finish
# -----------------------------------------------------------------------------
print_next_steps() {
  cat <<EOF

================================================================================
Vibe Create is installed. Next steps:

  1. Start the local workbench:
     cd $(printf '%q' "$REPO_ROOT")
     python3 scripts/workbench_server.py

  2. Open the workbench in your browser:
     http://127.0.0.1:8765

  3. Enter a game idea, choose settings, and click "Generate game".

  4. When a project is complete, use "Export for web" to build a zip containing
     a playable PWA (index.html + manifest.json + service-worker.js). Unzip on
     any device and open index.html — no engine or install required.

Build modes:
  - 2D sandbox · Godot   — seeded side-scrolling sandbox (needs Godot 4.3+ to run natively)
  - Quest RPG · Browser  — offline top-down RPG vertical slice
  - Diablo 2 · Browser   — isometric action RPG with random dungeons, loot, skills

--------------------------------------------------------------------------------
Models pulled:
  - qwen3.5:2b   — local game-content planner (default)
  - qwen2.5vl:3b — local vision reviewer
  - qwen3.5:4b   — Blender script generation & repair

Optional tools (checked, not installed by this script):
  - Blender  — for Blender concept stages (.blend, .fbx exports)
  - Godot 4.3+ — to run Godot sandbox builds natively

All generation runs on this machine via Ollama. Nothing is sent to a hosted
service. See README.md for the full step-by-step guide.
================================================================================
EOF
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
main() {
  echo "================================================================"
  echo "  Vibe Create — one-command installer"
  echo "================================================================"
  install_ollama
  start_ollama
  pull_models
  check_optional_tools
  chmod_scripts
  print_next_steps
}

main "$@"
