#!/usr/bin/env python3
"""Generate a self-contained HTML5 canvas sandbox from a world-spec.json.

This lets a Godot 4 side-scrolling slice play in any web browser, offline,
with no Godot installation or export templates required. The terrain,
player, enemy, mining, placement, crafting, and save/reload logic mirror the
Godot runtime exactly (deterministic from the same seed).

Emits a single index.html with embedded JSON spec + inline CSS/JS.
Pure Python standard library.
"""

from __future__ import annotations

import json
from pathlib import Path

TILE = 16
CHUNK_TILES = 32
WORLD_HEIGHT = 96

# Tile id -> palette key used by the Godot runtime atlas.
TILE_PALETTE_KEY = {
    0: "grass", 1: "dirt", 2: "stone", 3: "ore", 4: "moss",
    5: "wood", 6: "leaf", 7: "crystal", 8: "cave",
}

HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>__TITLE__</title>
<style>
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; height: 100%; background: #0b100e; color: #e7e5dc;
  font: 14px/1.4 ui-sans-serif, system-ui, sans-serif; overflow: hidden; }
#wrap { position: relative; width: 100vw; height: 100vh; display: grid; place-items: center; }
canvas#game { width: 100vw; height: 100vh; max-width: 1280px; max-height: 720px;
  background: #10151f; image-rendering: pixelated; display: block; margin: 0 auto;
  border: 2px solid #24343A; border-radius: 8px; box-shadow: 0 0 40px rgba(0,0,0,.6); }
canvas#game:focus { outline: 2px solid #9ed3c6; }
#hud { position: absolute; left: 14px; top: 14px; z-index: 10; pointer-events: none;
  text-shadow: 0 1px 2px rgba(0,0,0,.7); }
#hud .row { display: flex; gap: 10px; align-items: baseline; margin-bottom: 6px; }
#hud label { color: #9ed3c6; font-size: 11px; text-transform: uppercase; letter-spacing: .08em; }
#hud .value { color: #f1bd75; font-variant-numeric: tabular-nums; min-width: 28px; text-align: right; }
#notice { position: absolute; left: 50%; top: 14px; transform: translateX(-50%); z-index: 10;
  color: #cce797; font-weight: 700; letter-spacing: .05em; pointer-events: none;
  text-shadow: 0 1px 2px rgba(0,0,0,.8); }
#controls { position: absolute; right: 14px; bottom: 14px; z-index: 10; display: flex;
  flex-direction: column; gap: 8px; align-items: flex-end; pointer-events: auto; }
#controls button { background: #17232b; border: 1px solid #3d5158; color: #e7e5dc;
  padding: 7px 12px; border-radius: 6px; font: 12px/1.2 ui-sans-serif, system-ui, sans-serif;
  cursor: pointer; text-align: left; }
#controls button:hover { border-color: #9ed3c6; background: #1e3238; }
#controls button:disabled { opacity: .5; cursor: not-allowed; }
#controls .hint { color: #83b763; font-size: 11px; margin-top: 2px; white-space: nowrap; }
#overlay { position: absolute; inset: 0; z-index: 20; background: rgba(11,16,14,.85);
  display: grid; place-items: center; text-align: center; pointer-events: auto; }
#overlay.hidden { display: none; }
#overlay h1 { color: #f1bd75; margin: 0 0 8px; font-size: 28px; letter-spacing: .1em; }
#overlay p { color: #bdc6c3; margin: 0 0 16px; max-width: 320px; }
#overlay button.start { background: #9ed3c6; color: #0b100e; border: none; padding: 10px 22px;
  border-radius: 6px; font: 700 15px ui-sans-serif, system-ui, sans-serif; cursor: pointer; }
#overlay button.start:hover { background: #b8d9c6; }
#overlay .keys { color: #6d8285; font-size: 11px; margin-top: 10px; }
#saved { position: absolute; right: 14px; top: 14px; z-index: 10; color: #83b763;
  font-size: 11px; pointer-events: none; text-shadow: 0 1px 2px rgba(0,0,0,.7); }
</style>
</head>
<body>
<div id="wrap">
  <canvas id="game" width="640" height="360" tabindex="0" aria-label="Sandbox world"></canvas>
  <div id="hud">
    <div class="row"><label>Health</label><span id="hp" class="value">5</span><span id="hpbartext" style="color:#83b763"></span></div>
    <div class="row"><label>Wood</label><span id="wood" class="value">0</span></div>
    <div class="row"><label>Stone</label><span id="stone" class="value">0</span></div>
    <div class="row"><label>Dirt</label><span id="dirt" class="value">10</span></div>
    <div class="row"><label>Ore</label><span id="ore" class="value">0</span></div>
    <div class="row"><label>Enemy</label><span id="enemyhp" class="value">--</span></div>
  </div>
  <div id="notice">Find a tree, mine four logs, then craft a wooden pickaxe.</div>
  <div id="saved">saved</div>
  <div id="controls">
    <button id="craft">Craft wooden pickaxe · 4 wood</button>
    <div class="hint">J · strike slime</div>
  </div>
  <div id="overlay">
    <h1>__TITLE__</h1>
    <p>A seeded side-scrolling sandbox. Play offline, anywhere.</p>
    <button class="start" id="start">Start playing</button>
    <div class="keys">A/D move &middot; Space jump &middot; Left-click mine &middot; Right-click place dirt &middot; J strike</div>
  </div>
</div>
<script>
'use strict';

const SPEC = __SPEC_JSON__;
const TILE = 16;
const CHUNK_TILES = 32;
const WORLD_HEIGHT = 96;

const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d', { alpha: false });
const hpEl = document.getElementById('hp');
const woodEl = document.getElementById('wood');
const stoneEl = document.getElementById('stone');
const dirtEl = document.getElementById('dirt');
const oreEl = document.getElementById('ore');
const enemyEl = document.getElementById('enemyhp');
const noticeEl = document.getElementById('notice');
const savedEl = document.getElementById('saved');
const craftBtn = document.getElementById('craft');
const overlay = document.getElementById('overlay');
const startBtn = document.getElementById('start');

const seed = SPEC.seed;
const chunks = SPEC.chunks;
const worldWidth = chunks * CHUNK_TILES * TILE;
const palette = SPEC.palette || {};
const projectId = SPEC.projectId || "sandbox-world";
const SAVE_KEY = "vibecreate-sandbox-" + projectId;

function mixSeed(value) {
  let n = (seed ^ (value * 374761393)) >>> 0;
  n = ((n ^ (n >>> 13)) * 1274126177) >>> 0;
  return (n ^ (n >>> 16)) >>> 0;
}
function surfaceAt(tx) {
  const phase = (seed % 100000) * 0.00013;
  return 24 + Math.round(Math.sin(tx * 0.045 + phase) * 3 + Math.sin(tx * 0.12 + phase * 0.5) * 1.3);
}
function caveAt(tx) {
  const phase = (seed % 100000) * 0.00013;
  const center = surfaceAt(tx) + 35 + Math.round(Math.sin(tx * 0.034 + phase) * 2);
  const radius = 8 + Math.round(Math.sin(tx * 0.071 + phase * 1.7) * 2);
  return { center, radius };
}
function inCave(tx, ty) {
  const entranceX = worldWidth / TILE / 2 | 0;
  const c = caveAt(tx);
  const shaft = Math.abs(tx - entranceX) <= 2 && ty >= surfaceAt(tx) && ty < c.center + c.radius;
  const tunnel = tx > 10 && tx < worldWidth / TILE - 10 && ty > surfaceAt(tx) + 10 && ty < WORLD_HEIGHT - 4 && Math.abs(ty - c.center) < c.radius;
  return shaft || tunnel;
}
function tileIdAt(tx, ty) {
  const surface = surfaceAt(tx);
  if (ty < surface || inCave(tx, ty)) return -1;
  if (ty === surface) return 0;
  if (ty <= surface + 5) return 1;
  const roll = mixSeed(tx * 131 + ty * 65537) % 149;
  if (ty > surface + 16 && roll < 3) return 3;
  if (ty > surface + 16 && roll === 3) return 7;
  return roll < 8 ? 4 : 2;
}
function paletteColor(key, fallback) {
  return palette[key] || fallback || "#555E62";
}

const removed = {};
const placed = {};

const player = {
  x: 0, y: 0, vx: 0, vy: 0, onGround: false,
  health: 5, maxHealth: 5,
  inventory: { wood: 0, stone: 0, dirt: 10, copper: 0, crystal: 0 },
  hasPickaxe: false, facing: 1, swing: 0, notice: "", noticeTime: 0,
  attackCooldown: 0
};
const enemy = {
  x: 0, y: 0, health: 4, maxHealth: 4, alive: true, dir: -1, biteCooldown: 0,
  defeated: false
};
const keys = {};
let camX = 0;
let savedFlash = 0;

function setNotice(msg, t = 4) {
  player.notice = msg; player.noticeTime = t;
  noticeEl.textContent = msg;
}
function cellKey(tx, ty) { return tx + "," + ty; }
function saveGame() {
  const payload = {
    seed, removed, placed,
    player: { x: player.x, y: player.y, health: player.health,
              inventory: { ...player.inventory }, has_pickaxe: player.hasPickaxe },
    enemy_defeated: enemy.defeated
  };
  try { localStorage.setItem(SAVE_KEY, JSON.stringify(payload)); } catch (e) {}
  savedFlash = 20;
}
function loadGame() {
  try {
    const raw = localStorage.getItem(SAVEKey);
    if (!raw) return;
    const p = JSON.parse(raw);
    if (!p || typeof p !== "object") return;
    for (const k of (p.removed || [])) removed[k] = true;
    for (const [k, v] of Object.entries(p.placed || {})) placed[k] = v;
    const st = p.player || {};
    player.x = st.x ?? player.x;
    player.y = st.y ?? player.y;
    player.health = st.health ?? 5;
    player.inventory = { ...player.inventory, ...(st.inventory || {}) };
    player.hasPickaxe = !!st.has_pickaxe;
    enemy.defeated = !!p.enemy_defeated;
  } catch (e) {}
}
function respawnPlayer() {
  player.x = 10 * TILE;
  const s = surfaceAt(10);
  player.y = s * TILE - 17;
  player.vx = 0; player.vy = 0;
  player.health = 5;
}

function applyInput() {
  let dir = 0;
  if (keys["a"] || keys["arrowleft"]) dir -= 1;
  if (keys["d"] || keys["arrowright"]) dir += 1;
  player.facing = dir !== 0 ? dir : player.facing;
  player.vx = dir * 185;
  if (!player.onGround) player.vy += 920 * (1 / 60);
  else if (keys[" "] || keys["arrowup"] || keys["w"]) {
    player.vy = -360;
    player.onGround = false;
  }
  if (keys["j"] && player.attackCooldown <= 0) {
    attackEnemy();
    player.attackCooldown = 0.42 * 60;
  }
}
function attackEnemy() {
  if (!enemy.alive || enemy.defeated) return;
  const dx = player.x - enemy.x;
  const dy = player.y - enemy.y;
  if (Math.hypot(dx, dy) > 48) return;
  enemy.health -= 1;
  if (enemy.health <= 0) {
    enemy.health = 0; enemy.alive = false; enemy.defeated = true;
    saveGame();
    setNotice("The " + (SPEC.enemyName || "cave slime") + " falls.");
  } else {
    setNotice("Strike! " + (SPEC.enemyName || "cave slime") + " hp: " + enemy.health + "/4");
  }
}
function mineAt(wx, wy) {
  const tx = Math.floor(wx / TILE);
  const ty = Math.floor(wy / TILE);
  if (Math.hypot(wx - player.x, wy - player.y) > 112) return;
  if (tx < 0 || tx >= worldWidth / TILE || ty < 0 || ty >= WORLD_HEIGHT) return;
  const tid = tileIdAt(tx, ty);
  if (tid < 0) return;
  if ((tid === 2 || tid === 3 || tid === 4 || tid === 7) && !player.hasPickaxe) {
    setNotice("Stone needs a pickaxe. Gather four wood from tree trunks.");
    return;
  }
  const key = cellKey(tx, ty);
  if (tid === 0 || tid === 1) player.inventory.dirt = (player.inventory.dirt || 0) + 1;
  if (tid === 2 || tid === 4) player.inventory.stone = (player.inventory.stone || 0) + 1;
  if (tid === 3) player.inventory.copper = (player.inventory.copper || 0) + 1;
  if (tid === 5 || tid === 6) player.inventory.wood = (player.inventory.wood || 0) + 1;
  if (tid === 7) player.inventory.crystal = (player.inventory.crystal || 0) + 1;
  removed[key] = true; placed[key] = undefined;
  saveGame();
  setNotice("Mined a block.");
}
function placeAt(wx, wy) {
  const tx = Math.floor(wx / TILE);
  const ty = Math.floor(wy / TILE);
  if (Math.hypot(wx - player.x, wy - player.y) > 112) return;
  if (tx < 0 || tx >= worldWidth / TILE || ty < 0 || ty >= WORLD_HEIGHT) return;
  if (tileIdAt(tx, ty) >= 0 || (player.inventory.dirt || 0) <= 0) return;
  const centerX = tx * TILE + TILE / 2;
  const centerY = ty * TILE + TILE / 2;
  if (Math.hypot(centerX - player.x, centerY - player.y) < 22) return;
  player.inventory.dirt -= 1;
  placed[cellKey(tx, ty)] = 1;
  removed[cellKey(tx, ty)] = undefined;
  saveGame();
  setNotice("Placed a dirt block.");
}
function craftPickaxe() {
  if (player.hasPickaxe || (player.inventory.wood || 0) < 4) return false;
  player.inventory.wood -= 4;
  player.hasPickaxe = true;
  saveGame();
  setNotice("Wooden pickaxe crafted. Stone and ore can now be mined.");
  return true;
}

window.addEventListener("keydown", e => {
  const k = e.key.toLowerCase();
  if (["arrowup", "arrowdown", "arrowleft", "arrowright", " "].includes(k)) e.preventDefault();
  keys[k] = true;
  if (k === "j") { /* handled in applyInput via cooldown */ }
});
window.addEventListener("keyup", e => { keys[e.key.toLowerCase()] = false; });
canvas.addEventListener("mousedown", e => {
  const rect = canvas.getBoundingClientRect();
  const sx = canvas.width / rect.width;
  const sy = canvas.height / rect.height;
  const mx = (e.clientX - rect.left) * sx;
  const my = (e.clientY - rect.top) * sy;
  const wx = mx + camX;
  const wy = my; // canvas y == world y (top-aligned)
  if (e.button === 0) mineAt(wx, wy);
  else if (e.button === 2) { e.preventDefault(); placeAt(wx, wy); }
});
canvas.addEventListener("contextmenu", e => e.preventDefault());
craftBtn.addEventListener("click", () => { craftPickaxe(); });

function update() {
  if (player.attackCooldown > 0) player.attackCooldown -= 1;
  if (player.swing > 0) player.swing -= 1;
  if (savedFlash > 0) savedFlash -= 1;
  if (player.noticeTime > 0) player.noticeTime -= 1;
  else { noticeEl.textContent = ""; }

  applyInput();

  const nextY = player.y + player.vy;
  const floorY = surfaceAt(Math.floor(player.x / TILE)) * TILE - 12;
  if (nextY + 12 >= floorY) {
    player.y = floorY - 12;
    player.vy = 0;
    player.onGround = true;
  } else {
    player.y = nextY;
    player.onGround = false;
  }
  player.x += player.vx;
  player.x = Math.max(12, Math.min(worldWidth - 12, player.x));
  if (player.y > WORLD_HEIGHT * TILE) respawnPlayer();

  // Enemy AI
  if (!enemy.defeated && enemy.alive) {
    if (enemy.biteCooldown > 0) enemy.biteCooldown -= 1;
    const dx = player.x - enemy.x;
    enemy.dir = dx > 0 ? 1 : -1;
    const floorE = surfaceAt(Math.floor(enemy.x / TILE)) * TILE - 12;
    if (enemy.y + 12 >= floorE) { enemy.y = floorE - 12; enemy.vy = 0; }
    else { enemy.y += enemy.vy || 0; enemy.vy = (enemy.vy || 0) + 820 * (1 / 60); }
    enemy.x += enemy.dir * 54;
    const exf = Math.floor(enemy.x / TILE);
    const eyf = Math.floor(enemy.y / TILE);
    if (tileIdAt(exf, eyf + 1) < 0 && !inCave(exf, eyf + 1)) enemy.dir *= -1; // wall/turn
    enemy.x = Math.max(0, Math.min(worldWidth, enemy.x));
    if (Math.hypot(dx, player.y - enemy.y) < 27 && enemy.biteCooldown <= 0) {
      player.health = Math.max(0, player.health - 1);
      enemy.biteCooldown = 66;
      setNotice((SPEC.enemyName || "cave slime") + " hit you.");
      if (player.health <= 0) { player.health = 5; respawnPlayer(); setNotice("You caught your breath and returned to the surface."); }
    }
  }

  // Camera centers player
  camX = player.x - canvas.width / 2;
  camX = Math.max(0, Math.min(worldWidth - canvas.width, camX));

  renderHud();
}
function renderHud() {
  hpEl.textContent = player.health;
  woodEl.textContent = player.inventory.wood || 0;
  stoneEl.textContent = player.inventory.stone || 0;
  dirtEl.textContent = player.inventory.dirt || 0;
  oreEl.textContent = player.inventory.copper || 0;
  enemyEl.textContent = enemy.defeated ? "defeated" : (enemy.alive ? enemy.health + "/4" : "--");
  craftBtn.disabled = player.hasPickaxe || (player.inventory.wood || 0) < 4;
  craftBtn.textContent = player.hasPickaxe ? "Wooden pickaxe crafted" : "Craft wooden pickaxe · 4 wood";
  if (savedFlash > 0) {
    savedEl.textContent = "saved";
    savedEl.style.opacity = 1;
  } else {
    savedEl.style.opacity = 0;
  }
}
function drawTile(tx, ty, color) {
  ctx.fillStyle = color;
  ctx.fillRect(tx * TILE - camX, ty * TILE, TILE, TILE);
}
function drawPlayer() {
  const px = player.x - camX;
  const py = player.y;
  const s = player.swing > 0 ? 1 : 0;
  ctx.fillStyle = player.invulnerable > 0 ? "#f1d7b0" : "#D4A77A";
  ctx.fillRect(px + 5, py + 4, 14, 9);
  ctx.fillStyle = "#543E39";
  ctx.fillRect(px + 6, py + 4, 12, 3);
  ctx.fillStyle = "#26323D";
  ctx.fillRect(px + 7, py + 8, 2, 2);
  ctx.fillRect(px + 15, py + 8, 2, 2);
  ctx.fillStyle = "#F5E5BA";
  ctx.fillRect(px + 8, py + 8, 1, 1);
  ctx.fillRect(px + 16, py + 8, 1, 1);
  ctx.fillStyle = "#377E82";
  ctx.fillRect(px + 7, py + 13, 10, 10);
  ctx.fillStyle = "#65B1A1";
  ctx.fillRect(px + 7, py + 13, 10, 2);
  ctx.fillStyle = "#D4A77A";
  ctx.fillRect(px + 5, py + 15, 3, 8);
  ctx.fillRect(px + 16, py + 15, 3, 7);
  const ls = 22 + s, rs = 22 - s;
  ctx.fillStyle = "#394958";
  ctx.fillRect(px + 8, py + ls, 4, 7);
  ctx.fillRect(px + 13, py + rs, 4, 7);
  ctx.fillStyle = "#2A303A";
  ctx.fillRect(px + 7, py + 28 + s, 6, 2);
  ctx.fillRect(px + 12, py + 28 - s, 6, 2);
  if (player.swing > 0) {
    ctx.strokeStyle = "#ffe294";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(px + 12, py + 8, 48, -1.5, 1.0);
    ctx.stroke();
  }
}
function drawEnemy() {
  if (enemy.defeated || !enemy.alive) return;
  const ex = enemy.x - camX;
  const ey = enemy.y;
  ctx.fillStyle = "#401f27";
  ctx.beginPath();
  ctx.arc(ex, ey, 19, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#b74f4d";
  ctx.beginPath();
  ctx.moveTo(ex - 16, ey - 5);
  ctx.lineTo(ex - 21, ey - 22);
  ctx.lineTo(ex - 6, ey - 14);
  ctx.lineTo(ex + 1, ey - 25);
  ctx.lineTo(ex + 8, ey - 13);
  ctx.lineTo(ex + 22, ey - 19);
  ctx.lineTo(ex + 17, ey - 3);
  ctx.lineTo(ex + 14, ey + 13);
  ctx.lineTo(ex, ey + 20);
  ctx.lineTo(ex - 14, ey + 12);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = "#d44d4b";
  ctx.fillRect(ex - 18, ey - 30, 36 * (enemy.health / enemy.maxHealth), 4);
  ctx.fillStyle = "#f2ddd1";
  ctx.font = "11px ui-sans-serif, system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(SPEC.enemyName || "Slime", ex, ey - 36);
}
function render() {
  ctx.fillStyle = paletteColor("sky_top", "#38566D");
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  const sky = paletteColor("sky", "#85B8C5");
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, canvas.width, 26 * TILE - camX % 0); // top band hint
  ctx.fillStyle = "#10151f";
  ctx.fillRect(0, 28 * TILE, canvas.width, canvas.height);

  const startCol = Math.floor(camX / TILE) - 1;
  const endCol = Math.floor((camX + canvas.width) / TILE) + 1;
  for (let tx = startCol; tx <= endCol; tx++) {
    const surface = surfaceAt(tx);
    const c = caveAt(tx);
    // cave backing
    for (let ty = surface + 1; ty < WORLD_HEIGHT; ty++) {
      if (inCave(tx, ty)) {
        const key = cellKey(tx, ty);
        if (!removed[key] && !placed[key]) {
          ctx.fillStyle = paletteColor("cave", "#18242B");
          ctx.fillRect(tx * TILE - camX, ty * TILE, TILE, TILE);
        }
      }
    }
    // ground tiles
    for (let ty = surface; ty < WORLD_HEIGHT; ty++) {
      const key = cellKey(tx, ty);
      if (removed[key]) continue;
      const forced = placed[key];
      if (forced !== undefined) {
        const color = paletteColor(TILE_PALETTE_KEY[forced] || "stone", "#555E62");
        ctx.fillStyle = color;
        ctx.fillRect(tx * TILE - camX, ty * TILE, TILE, TILE);
        continue;
      }
      const tid = tileIdAt(tx, ty);
      if (tid < 0) continue;
      ctx.fillStyle = paletteColor(TILE_PALETTE_KEY[tid] || "#555E62", "#555E62");
      ctx.fillRect(tx * TILE - camX, ty * TILE, TILE, TILE);
    }
  }

  drawEnemy();
  drawPlayer();
}
function loop() {
  update();
  render();
  requestAnimationFrame(loop);
}

startBtn.addEventListener("click", () => {
  overlay.classList.add("hidden");
  canvas.focus();
  init();
  loop();
});

// Seed player start after first render frame so canvas is ready.
window.addEventListener("load", () => {
  const s = surfaceAt(10);
  player.x = 10 * TILE;
  player.y = s * TILE - 17;
  const slimeX = Math.floor(worldWidth * 0.68);
  const c = caveAt(slimeX);
  enemy.x = slimeX * TILE;
  enemy.y = (c.center + c.radius) * TILE - 12;
  loadGame();
});
</script>
</body>
</html>"""

# A small placeholder used to inject the game-data JSON at export time.
SPEC_PLACEHOLDER = "__SPEC_JSON__"


def generate_html(spec: dict) -> str:
    spec_json = json.dumps(spec, ensure_ascii=False)
    html = HTML_TEMPLATE.replace(SPEC_PLACEHOLDER, spec_json)
    return html.replace("__TITLE__", str(spec.get("worldName", "Sandbox World")))
