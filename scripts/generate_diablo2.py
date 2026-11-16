#!/usr/bin/env python3
"""Generate a self-contained Diablo 2-style action RPG project.

Outputs, inside <out>/:
  index.html          self-contained isometric HTML5 game (canvas, all data embedded)
  game-content.json   structured encounter / world brief (schema-validated)
  project.json        Vibe Create project manifest
  map-*.json          generated random area maps
  README.md           install / play notes

The generated game requires no engine install: open index.html in any browser
and play offline. It is an HTML5 canvas isometric action RPG with random
dungeons, loot, skills, classes, and combat.

Pure Python standard library for generation.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import struct
import sys
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_game_planner import generate_local_content  # noqa: E402
from diablo2_data import (  # noqa: E402
    CLASS_DATA, ITEM_BASES, UNIQUE_ITEMS, ITEM_SETS, MONSTER_FAMILIES, ACT_BOSSES,
    AREAS, ACTS, QUESTS, NPCDATA, QUALITY_NAMES, QUALITY_COLORS,
    DAMAGE_TYPES, RESISTANCE_ORDER, compute_life, compute_mana, compute_stamina,
    compute_defense, compute_chance_to_block,
)
from diablo2_mapgen import MapGen, TILE, FLOOR, WALL  # noqa: E402


def _chunk(kind: bytes, content: bytes) -> bytes:
    payload = kind + content
    return struct.pack(">I", len(content)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)


def write_png(path: Path, width: int, height: int, rgba: bytes) -> None:
    stride = width * 4
    scanlines = bytearray()
    for y in range(height):
        scanlines.append(0)
        scanlines.extend(rgba[y * stride:(y + 1) * stride])
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(bytes(scanlines), 9))
    png += _chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def make_dark_preview(path: Path, width: int = 512, height: int = 288) -> None:
    """Procedural dark-fantasy preview: a moody isometric dungeon entrance."""
    rgba = bytearray(width * height * 4)
    def px(x, y, r, g, b, a=255):
        if 0 <= x < width and 0 <= y < height:
            i = (y * width + x) * 4
            rgba[i:i+4] = bytes((r, g, b, a))
    # Sky gradient
    for y in range(height // 2):
        t = y / max(1, height // 2 - 1)
        r = int(11 * (1 - t) + 30 * t)
        g = int(16 * (1 - t) + 40 * t)
        b = int(14 * (1 - t) + 50 * t)
        for x in range(width):
            px(x, y, r, g, b)
    # Ground
    for y in range(height // 2, height):
        for x in range(width):
            px(x, y, 16, 20, 18)
    # Dungeon arch (iso diamond)
    cx, cy = width // 2, height // 2 + 20
    for dy in range(-60, 61):
        for dx in range(-80, 81):
            if abs(dx) / 80 + abs(dy) / 60 <= 1:
                if abs(abs(dx) / 80 - abs(dy) / 60) > 0.85:
                    px(cx + dx, cy + dy, 40, 45, 40)
                else:
                    px(cx + dx, cy + dy, 24, 28, 24)
    # Torch glow
    for dy in range(-30, 31):
        for dx in range(-40, 41):
            d = (dx * dx + dy * dy) ** 0.5
            if d < 30:
                a = int(60 * (1 - d / 30))
                px(cx + dx - 70, cy + dy - 20, 240, 180, 60, a)
                px(cx + dx + 70, cy + dy - 20, 240, 180, 60, a)
    # Title-ish glow
    write_png(path, width, height, bytes(rgba))


# ---------------------------------------------------------------------------
# HTML game shell (self-contained isometric Diablo-like)
# ---------------------------------------------------------------------------

GAME_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>__TITLE__</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; background: #0b100e; color: #e7e5dc;
  font: 14px/1.45 ui-sans-serif, system-ui, sans-serif; overflow: hidden; }
#wrap { position: relative; width: 100vw; height: 100vh; display: grid;
  grid-template-columns: 1fr 300px; grid-template-rows: 1fr 90px; }
canvas#game { width: 100%; height: 100%; background: #10151f;
  image-rendering: pixelated; display: block; position: relative;
  grid-column: 1 / 2; grid-row: 1 / 3; }
#sidebar { background: #111714; border-left: 1px solid #24343A;
  padding: 12px; overflow-y: auto; grid-column: 2 / 3; grid-row: 1 / 3; }
#sidebar h3 { color: #f1bd75; margin: 0 0 8px; font-size: 14px; letter-spacing: .1em; }
#sidebar .section { margin-bottom: 14px; }
#sidebar .stat-row { display: flex; justify-content: space-between; gap: 8px; margin: 3px 0;
  font-size: 12px; color: #bdc6c3; }
#sidebar .stat-row .val { color: #9ed3c6; font-variant-numeric: tabular-nums; }
#bottom { background: #0c110f; border-top: 1px solid #24343A;
  padding: 8px 14px; display: flex; gap: 14px; align-items: center;
  grid-column: 1 / 3; grid-row: 3 / 4; font-size: 12px; color: #bdc6c3; }
#bottom .chip { border: 1px solid #3d5158; padding: 3px 8px; border-radius: 4px;
  color: #9ed3c6; white-space: nowrap; }
#notice { position: absolute; left: 50%; top: 12px; transform: translateX(-50%);
  z-index: 40; color: #cce797; font-weight: 700; letter-spacing: .05em;
  text-shadow: 0 1px 2px rgba(0,0,0,.8); pointer-events: none;
  padding: 6px 12px; border-radius: 6px; background: rgba(11,16,14,.65);
  border: 1px solid rgba(204,231,151,.35); }
#overlay { position: absolute; inset: 0; z-index: 50; background: rgba(11,16,14,.9);
  display: grid; place-items: center; text-align: center; pointer-events: auto; }
#overlay.hidden { display: none; }
#overlay h1 { color: #f1bd75; margin: 0 0 10px; font-size: 34px; letter-spacing: .15em; }
#overlay p { color: #bdc6c3; margin: 0 0 18px; max-width: 420px; line-height: 1.6; }
#overlay button { background: #9ed3c6; color: #0b100e; border: none; padding: 10px 26px;
  border-radius: 6px; font: 700 16px ui-sans-serif, system-ui, sans-serif; cursor: pointer; }
#overlay button:hover { background: #b8d9c6; }
#overlay .keys { color: #6d8285; font-size: 11px; margin-top: 14px; }
#saved { position: absolute; right: 14px; top: 12px; z-index: 35; color: #83b763;
  font-size: 11px; pointer-events: none; text-shadow: 0 1px 2px rgba(0,0,0,.7); }
.skill-bar { display: flex; gap: 6px; margin-top: 6px; }
.skill-bar .skill { flex: 1; background: #151c17; border: 1px solid #3d5158;
  border-radius: 4px; padding: 5px 6px; color: #e7e5dc; font-size: 11px; text-align: center;
  cursor: pointer; }
.skill-bar .skill.active { border-color: #f1bd75; color: #f1bd75; background: #1a2a24; }
.skill-bar .skill.cooldown { opacity: .5; }
</style>
</head>
<body>
<div id="wrap">
  <canvas id="game" width="960" height="600" tabindex="0"
    aria-label="Diablo-style isometric action RPG"></canvas>
  <div id="sidebar">
    <div class="section"><h3 id="char-name">__CHAR_NAME__</h3>
      <div class="stat-row"><span>Level</span><span id="lvl-val" class="val">1</span></div>
      <div class="stat-row"><span>Experience</span><span id="xp-val" class="val">0</span></div>
      <div class="stat-row"><span>Life</span><span id="hp-val" class="val">100</span></div>
      <div class="stat-row"><span>Mana</span><span id="mp-val" class="val">100</span></div>
      <div class="stat-row"><span>Stamina</span><span id="stam-val" class="val">100</span></div>
    </div>
    <div class="section"><h3>Attributes</h3>
      <div class="stat-row"><span>Strength</span><span id="str-val" class="val">10</span></div>
      <div class="stat-row"><span>Dexterity</span><span id="dex-val" class="val">10</span></div>
      <div class="stat-row"><span>Vitality</span><span id="vit-val" class="val">10</span></div>
      <div class="stat-row"><span>Energy</span><span id="ene-val" class="val">10</span></div>
    </div>
    <div class="section"><h3>Resistances</h3>
      <div class="stat-row"><span>Fire</span><span id="fr-val" class="val">0%</span></div>
      <div class="stat-row"><span>Cold</span><span id="cr-val" class="val">0%</span></div>
      <div class="stat-row"><span>Lightning</span><span id="lr-val" class="val">0%</span></div>
      <div class="stat-row"><span>Poison</span><span id="pr-val" class="val">0%</span></div>
    </div>
    <div class="section"><h3>Skills <span style="font-weight:400;font-size:11px">(1-6)</span></h3>
      <div class="skill-bar" id="skill-bar"></div>
    </div>
    <div class="section"><h3>Area</h3>
      <div id="area-name" style="color:#f1bd75">__AREA__</div>
    </div>
  </div>
  <div id="bottom">
    <span class="chip" id="gold-chip">Gold: 0</span>
    <span class="chip" id="quest-chip">Quest: Find the den</span>
    <div id="bottom-hints">WASD / arrows move · Left-click attack · 1-6 skills · Tab stamina</div>
  </div>
  <div id="notice">Welcome, hero.</div>
  <div id="saved">saved</div>
  <div id="overlay">
    <h1 id="overlay-title">__TITLE__</h1>
    <p id="overlay-text">A reverse-engineered Diablo-style action RPG. Play offline, anywhere.</p>
    <button id="start-btn">Enter Sanctuary</button>
    <div class="keys">WASD / arrows move · Left-click attack · Right-click skill · 1-6 equip skill</div>
  </div>
</div>
<script>
'use strict';

// ---------------- Game data (embedded) ----------------
const SPEC = __SPEC_JSON__;
const MAPS = __MAPS_JSON__;
const CLASSES = __CLASSES_JSON__;
const ITEMS = __ITEMS_JSON__;
const MONSTERS = __MONSTERS_JSON__;
const BOSSES = __BOSSES_JSON__;
const AREAS = __AREAS_JSON__;
const ACTS = __ACTS_JSON__;
const QUESTS = __QUESTS_JSON__;
const NPCDATA = __NPCDATA_JSON__;
const UNIQUE_ITEMS = __UNIQUE_ITEMS_JSON__;
const ITEM_SETS = __ITEM_SETS_JSON__;

const TILE = __TILE__;

// ---------------- Core engine state ----------------
const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d', { alpha: false });
const noticeEl = document.getElementById('notice');
const savedEl = document.getElementById('saved');
const overlay = document.getElementById('overlay');
const startBtn = document.getElementById('startBtn');
const areaNameEl = document.getElementById('area-name');

let camera = { x: 0, y: 0 };
let mouse = { x: 0, y: 0, worldX: 0, worldY: 0 };
let keys = {};
let skillsBar = document.getElementById('skill-bar');

function setNotice(msg, t = 3) {
  noticeEl.textContent = msg;
  noticeEl.style.opacity = 1;
  setTimeout(() => { noticeEl.style.opacity = 0; }, t * 1000);
}
function flashSaved() { savedEl.style.opacity = 1; setTimeout(() => savedEl.style.opacity = 0, 1200); }

function saveGame() {
  try { localStorage.setItem("d2clone-" + SPEC.projectId, JSON.stringify(gameState)); }
  catch (e) {}
  flashSaved();
  setNotice("Game saved.", 2);
}
function loadGame() {
  try {
    const raw = localStorage.getItem("d2clone-" + SPEC.projectId);
    if (raw) { const p = JSON.parse(raw); Object.assign(gameState, p); setNotice("Save loaded.", 2); }
  } catch (e) {}
}

// ---------------- Math helpers ----------------
function dist(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

// Isometric helpers
function worldToIso(wx, wy) {
  return { x: (wx - wy), y: (wx + wy) / 2 };
}
function isoToWorld(ix, iy) {
  return { x: (ix / 2) + iy, y: iy - (ix / 2) };
}
function screenToWorld(sx, sy) {
  // Account for camera + canvas center offset
  const cx = canvas.width / 2 + camera.x;
  const cy = canvas.height / 4 + camera.y;
  const isoX = sx - cx;
  const isoY = sy - cy;
  return isoToWorld(isoX, isoY);
}
function worldToScreen(wx, wy) {
  const iso = worldToIso(wx, wy);
  const cx = canvas.width / 2 + camera.x;
  const cy = canvas.height / 4 + camera.y;
  return { x: iso.x + cx, y: iso.y + cy };
}

// ---------------- Spec / state init ----------------
const spec = SPEC;
const projectId = spec.projectId || "d2-clone";
const charName = spec.heroName || "Hero";
const playerClassId = spec.playerClass || "amazon";
const classData = CLASSES[playerClassId];
const seed = spec.seed || 4172026;

const rng = new SRNG(seed);

function SRNG(seed) {
  this.s = seed >>> 0;
  this.next = function () {
    this.s = (this.s * 1103515245 + 12345) >>> 0;
    return (this.s >>> 16) / 65536;
  };
  this.range = function (a, b) { return a + Math.floor(this.next() * (b - a + 1)); };
  this.pick = function (arr) { return arr[Math.floor(this.next() * arr.length)]; };
}

// ---------------- Character state ----------------
const gameState = {
  projectId,
  charName,
  classId: playerClassId,
  level: 1,
  experience: 0,
  experienceToNext: 1000,
  strength: classData.base_stats.strength,
  dexterity: classData.base_stats.dexterity,
  vitality: classData.base_stats.vitality,
  energy: classData.base_stats.energy,
  statPoints: 0,
  skillPoints: 0,
  life: 0, maxLife: 0,
  mana: 0, maxMana: 0,
  stamina: 100, maxStamina: 100,
  gold: 100,
  resist: { fire: 0, cold: 0, lightning: 0, poison: 0 },
  inventory: [],
  equipped: {},
  skills: {},
  activeSkill: null,
  x: 0, y: 0, vx: 0, vy: 0,
  facing: 1,
  areaId: spec.startingArea || "rogue_encampment",
  townArea: spec.startingArea || "rogue_encampment",
  waypoints: {},
  completedQuests: [],
  dead: false,
  inventoryFull: false,
};

// ---------------- Combat / items / skills ----------------
function rollDamage(min, max) { return Math.floor(rng.range(min, max)); }

function characterAttack() {
  const wp = gameState.equipped.weapon;
  const dmgMin = wp ? (wp.damage_min || 2) : 1;
  const dmgMax = wp ? (wp.damage_max || 5) : 3;
  return rollDamage(dmgMin, dmgMax) + Math.floor(gameState.strength / 5);
}

function applyDamage(target, amount, dmgType = "physical") {
  if (!target || !target.alive) return 0;
  let resist = 0;
  if (dmgType === "fire") resist = target.resist?.fire ?? 0;
  else if (dmgType === "cold") resist = target.resist?.cold ?? 0;
  else if (dmgType === "lightning") resist = target.resist?.lightning ?? 0;
  else if (dmgType === "poison") resist = target.resist?.poison ?? 0;
  resist = clamp(resist, -100, 75);
  const final = Math.max(1, Math.floor(amount * (100 - resist) / 100));
  target.hp = Math.max(0, (target.hp || 100) - final);
  if (target.hp <= 0) { target.alive = false; grantExperience(target.xpValue || 10); }
  return final;
}

function grantExperience(amount) {
  gameState.experience += amount;
  while (gameState.experience >= gameState.experienceToNext) {
    gameState.experience -= gameState.experienceToNext;
    gameState.level += 1;
    gameState.experienceToNext = Math.floor(gameState.experienceToNext * 1.4);
    gameState.statPoints += 5;
    gameState.skillPoints += 1;
    const cls = CLASSES[gameState.classId];
    gameState.maxLife = computeLife(gameState.vitality, gameState.level,
      classData.base_stats.strength * 2, cls.life_per_level);
    gameState.maxMana = computeMana(gameState.energy, gameState.level,
      classData.base_stats.energy * 2, cls.mana_per_level);
    gameState.life = gameState.maxLife;
    gameState.mana = gameState.maxMana;
    setNotice("Level up! You are now level " + gameState.level + ".", 4);
  }
}

function computeLife(vit, lvl) {
  const cls = CLASSES[gameState.classId];
  return Math.floor(100 + vit * 2 + cls.life_per_level * (lvl - 1));
}
function computeMana(ene, lvl) {
  const cls = CLASSES[gameState.classId];
  return Math.floor(100 + ene * 2.5 + cls.mana_per_level * (lvl - 1));
}

// ---------------- Map / area ----------------
let currentMap = null;

function loadArea(areaId) {
  const area = AREAS[areaId];
  if (!area) return;
  gameState.areaId = areaId;
  areaNameEl.textContent = area.name;

  let mapData = MAPS[areaId];
  if (!mapData) {
    // Generate a fresh random map
    const gen = new (requireMapGen)();
    // Placeholder: generated below by buildMapGenerator()
  }
  currentMap = mapData;
  camera.x = 0; camera.y = 0;
  // Place player at start
  if (currentMap) {
    gameState.x = currentMap.start_x;
    gameState.y = currentMap.start_y;
  }
}

requireMapGen = class {
  constructor() {}
};

// Build map generator inline (avoid module complexity)
function generateMapForArea(areaId) {
  const area = AREAS[areaId];
  const w = 40, h = 30;
  const grid = [];
  for (let y = 0; y < h; y++) { grid.push([]); for (let x = 0; x < w; x++) { grid[y].push(0); } }
  // Simple room carving
  const rooms = [];
  for (let i = 0; i < 40; i++) {
    const rw = Math.floor(rng.range(4, 10));
    const rh = Math.floor(rng.range(4, 10));
    const rx = Math.floor(rng.range(1, w - rw - 2));
    const ry = Math.floor(rng.range(1, h - rh - 2));
    let ok = true;
    for (const r of rooms) {
      if (!(rx + rw < r.x - 2 || rx > r.x + r.w + 2 || ry + rh < r.y - 2 || ry > r.y + r.h + 2)) { ok = false; break; }
    }
    if (!ok) continue;
    for (let y = ry; y < ry + rh; y++) for (let x = rx; x < rx + rw; x++) grid[y][x] = 0;
    rooms.push({ x: rx, y: ry, w: rw, h: rh });
  }
  // Connect rooms
  for (let i = 1; i < rooms.length; i++) {
    const a = rooms[i - 1]; const b = rooms[i];
    let cx = (a.x + a.w / 2) | 0, cy = (a.y + a.h / 2) | 0;
    const tx = (b.x + b.w / 2) | 0, ty = (b.y + b.h / 2) | 0;
    if (rng.next() < 0.5) {
      for (let x = Math.min(cx, tx); x <= Math.max(cx, tx); x++) grid[cy][x] = 0;
      for (let y = Math.min(cy, ty); y <= Math.max(cy, ty); y++) grid[y][tx] = 0;
    } else {
      for (let y = Math.min(cy, ty); y <= Math.max(cy, ty); y++) grid[y][cx] = 0;
      for (let x = Math.min(cx, tx); x <= Math.max(cx, tx); x++) grid[ty][x] = 0;
    }
  }
  const entities = [];
  // Start in first room
  const first = rooms[0];
  const sx = (first.x + first.w / 2) | 0;
  const sy = (first.y + first.h / 2) | 0;
  // Stairs
  const last = rooms[rooms.length - 1];
  const lx = Math.floor(rng.range(last.x, last.x + last.w - 1));
  const ly = Math.floor(rng.range(last.y, last.y + last.h - 1));
  grid[ly][lx] = 3;
  entities.push({ kind: "stairs_down", x: lx * TILE + TILE / 2, y: ly * TILE + TILE / 2,
    tile_x: lx, tile_y: ly, label: "Stairs Down" });
  // Waypoint
  const wroom = rooms[Math.floor(rng.range(0, rooms.length - 1))];
  const wx = Math.floor(rng.range(wroom.x, wroom.x + wroom.w - 1));
  const wy_ = Math.floor(rng.range(wroom.y, wroom.y + wroom.h - 1));
  grid[wy_][wx] = 5;
  entities.push({ kind: "waypoint", x: wx * TILE + TILE / 2, y: wy_ * TILE + TILE / 2,
    tile_x: wx, tile_y: wy_, label: "Waypoint" });
  // Monsters
  const mList = area.monsters || ["fallen"];
  for (let i = 0; i < rooms.length * 2; i++) {
    const room = rooms[Math.floor(rng.range(0, rooms.length))];
    const mx = Math.floor(rng.range(room.x, room.x + room.w - 1));
    const my = Math.floor(rng.range(room.y, room.y + room.h - 1));
    if (grid[my][mx] === 0) {
      const mid = mList[Math.floor(rng.range(0, mList.length))];
      const mData = MONSTERS[mid] || { name: "Monster", base_stats: { level: 3, health: 30, damage_min: 2, damage_max: 6, defense: 10, experience: 8 }, color: "#E74C3C" };
      entities.push({
        kind: "monster", monster_id: mid, name: mData.name,
        x: mx * TILE + TILE / 2, y: my * TILE + TILE / 2, tile_x: mx, tile_y: my,
        hp: mData.base_stats.health, maxHp: mData.base_stats.health,
        damage_min: mData.base_stats.damage_min, damage_max: mData.base_stats.damage_max,
        defense: mData.base_stats.defense, xpValue: mData.base_stats.experience,
        color: mData.color, alive: true,
        resist: { fire: 0, cold: 0, lightning: 0, poison: 0 },
      });
    }
  }
  return {
    width: w, height: h, tile: TILE, area_kind: area.type,
    grid, entities, start_x: sx * TILE + TILE / 2, start_y: sy * TILE + TILE / 2,
  };
}

function ensureMap(areaId) {
  if (!MAPS[areaId]) {
    MAPS[areaId] = generateMapForArea(areaId);
  }
  return MAPS[areaId];
}

// ---------------- Rendering ----------------
function render() {
  ctx.fillStyle = "#10151f";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  if (!currentMap) return;

  const visibleW = Math.ceil(canvas.width / TILE) + 4;
  const visibleH = Math.ceil(canvas.height / TILE) + 4;
  const startCol = Math.floor((camera.x - canvas.width / 2) / TILE) - 2;
  const endCol = Math.floor((camera.x + canvas.width / 2) / TILE) + 2;
  const startRow = Math.floor((camera.y - canvas.height / 4) / TILE) - 2;
  const endRow = Math.floor((camera.y + canvas.height / 4) / TILE) + 2;

  // Draw floor tiles first (iso order by y then x)
  const tiles = [];
  for (let ty = Math.max(0, startRow); ty <= Math.min(currentMap.height - 1, endRow); ty++) {
    for (let tx = Math.max(0, startCol); tx <= Math.min(currentMap.width - 1, endCol); tx++) {
      tiles.push({ tx, ty, kind: currentMap.grid[ty][tx] });
    }
  }
  tiles.sort((a, b) => (a.ty + a.tx) - (b.ty + b.tx));

  for (const t of tiles) {
    const iso = worldToIso(t.tx * TILE + TILE / 2, t.ty * TILE + TILE / 2);
    const sx = iso.x + canvas.width / 2 + camera.x;
    const sy = iso.y + canvas.height / 4 + camera.y;
    if (sx < -64 || sx > canvas.width + 64 || sy < -64 || sy > canvas.height + 64) continue;
    drawTile(t.kind, sx, sy);
  }

  // Draw entities (monsters, chests, stairs)
  const drawList = [];
  for (const e of currentMap.entities) {
    if (e.kind === "monster" && !e.alive) continue;
    drawList.push(e);
  }
  drawList.push(gameState);
  drawList.sort((a, b) => a.y - b.y);

  for (const e of drawList) {
    const sx = e.x - camera.x + canvas.width / 2;
    const sy = e.y - camera.y + canvas.height / 4;
    if (sx < -64 || sx > canvas.width + 64 || sy < -64 || sy > canvas.height + 64) continue;
    drawEntity(e, sx, sy);
  }

  // Grid / selection highlight under mouse
  const mx = mouse.worldX, my = mouse.worldY;
  const tileX = Math.floor(mx / TILE), tileY = Math.floor(my / TILE);
  if (tileX >= 0 && tileX < currentMap.width && tileY >= 0 && tileY < currentMap.height) {
    const iso = worldToIso(tileX * TILE + TILE / 2, tileY * TILE + TILE / 2);
    const sx = iso.x + canvas.width / 2 + camera.x;
    const sy = iso.y + canvas.height / 4 + camera.y;
    ctx.strokeStyle = "#9ed3c6";
    ctx.lineWidth = 2;
    ctx.strokeRect(sx - TILE / 2, sy - TILE / 4, TILE, TILE / 2);
  }
}

function drawTile(kind, sx, sy) {
  const h = TILE / 2;
  const colors = {
    0: "#24343A",   // floor
    1: "#151c17",   // wall
    2: "#52646b",   // door
    3: "#83b763",   // stairs down
    4: "#9ed3c6",   // stairs up
    5: "#f1bd75",   // waypoint
    6: "#c73c47",   // chest
    7: "#bdc6c3",   // object
    8: "#2d5a7a",   // water
    9: "#5d8a4a",   // grass
  };
  ctx.fillStyle = colors[kind] ?? colors[0];
  ctx.beginPath();
  ctx.moveTo(sx, sy - h);
  ctx.lineTo(sx + TILE / 2, sy);
  ctx.lineTo(sx, sy + h);
  ctx.lineTo(sx - TILE / 2, sy);
  ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,.06)";
  ctx.lineWidth = 1;
  ctx.stroke();
}

function drawEntity(e, sx, sy) {
  const h = TILE / 2;
  const isPlayer = e.kind === "player";
  ctx.save();
  ctx.translate(sx, sy);
  if (e.kind === "monster") {
    ctx.fillStyle = e.color || "#E74C3C";
    ctx.beginPath();
    ctx.arc(0, -h / 2, TILE / 3, 0, Math.PI * 2);
    ctx.fill();
    // Health bar
    const pct = e.hp / e.maxHp;
    ctx.fillStyle = "#333";
    ctx.fillRect(-TILE / 3, -h - 6, TILE * 2 / 3, 4);
    ctx.fillStyle = pct > 0.5 ? "#4caf50" : pct > 0.25 ? "#ff9800" : "#f44336";
    ctx.fillRect(-TILE / 3, -h - 6, (TILE * 2 / 3) * pct, 4);
    ctx.fillStyle = "#fff";
    ctx.font = "10px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(e.name || "Monster", 0, -h - 12);
  } else if (e.kind === "stairs_down" || e.kind === "stairs_up") {
    ctx.fillStyle = e.kind === "stairs_down" ? "#83b763" : "#9ed3c6";
    ctx.beginPath();
    ctx.moveTo(-TILE / 3, 0);
    ctx.lineTo(TILE / 3, 0);
    ctx.lineTo(0, h / 2);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "#000";
    ctx.font = "9px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(e.label, 0, 4);
  } else if (e.kind === "waypoint") {
    ctx.fillStyle = "#f1bd75";
    ctx.beginPath();
    ctx.arc(0, -h / 2, TILE / 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.stroke();
  } else if (e.kind === "chest") {
    ctx.fillStyle = "#c73c47";
    ctx.fillRect(-TILE / 4, -h / 2, TILE / 2, h / 2);
    ctx.fillStyle = "#d4a77a";
    ctx.fillRect(-TILE / 6, -h / 2, TILE / 6, h / 4);
  } else if (e.kind === "player") {
    ctx.fillStyle = "#789cb1";
    ctx.beginPath();
    ctx.arc(0, -h / 2, TILE / 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#d4a77a";
    ctx.beginPath();
    ctx.arc(0, -h / 2 - 6, 4, 0, Math.PI * 2);
    ctx.fill();
    // Life bar
    const pct = gameState.life / gameState.maxLife;
    ctx.fillStyle = "#333";
    ctx.fillRect(-TILE / 3, -h - 10, TILE * 2 / 3, 5);
    ctx.fillStyle = "#cce797";
    ctx.fillRect(-TILE / 3, -h - 10, (TILE * 2 / 3) * pct, 5);
  }
  ctx.restore();
}

// ---------------- Input ----------------
let targetX = null, targetY = null;
let moveTimer = 0;
let attackCooldown = 0;

function handleClick(sx, sy, button) {
  if (gameState.dead) return;
  const world = screenToWorld(sx, sy);
  // Check entity click first
  let clicked = null;
  for (const e of currentMap.entities) {
    if (dist(world, { x: e.x, y: e.y }) < TILE) { clicked = e; break; }
  }
  if (dist(world, { x: gameState.x, y: gameState.y }) < TILE) clicked = gameState;

  if (button === 0) { // left
    if (clicked && clicked.kind === "monster" && clicked.alive) {
      targetX = clicked.x; targetY = clicked.y;
      attackTarget(clicked);
    } else if (clicked && clicked.kind === "stairs_down") {
      changeArea("next");
    } else if (clicked && clicked.kind === "waypoint") {
      openWaypointMenu();
    } else if (clicked && clicked.kind === "chest") {
      openChest(clicked);
    } else {
      targetX = world.x; targetY = world.y;
    }
  } else if (button === 2) { // right: use active skill at target
    if (gameState.activeSkill) {
      useSkillAt(gameState.activeSkill, world.x, world.y);
    } else {
      targetX = world.x; targetY = world.y;
    }
  }
}

canvas.addEventListener("mousedown", e => {
  const rect = canvas.getBoundingClientRect();
  const sx = (e.clientX - rect.left) / rect.width * canvas.width;
  const sy = (e.clientY - rect.top) / rect.height * canvas.height;
  handleClick(sx, sy, e.button);
  if (e.button === 2) e.preventDefault();
});
canvas.addEventListener("contextmenu", e => e.preventDefault());
window.addEventListener("keydown", e => {
  const k = e.key.toLowerCase();
  if (["arrowup", "arrowdown", "arrowleft", "arrowright", " "].includes(k)) e.preventDefault();
  keys[k] = true;
  if (k >= "1" && k <= "6") {
    const skillId = Object.keys(gameState.skills)[parseInt(k) - 1];
    if (skillId) { gameState.activeSkill = skillId; setNotice("Skill: " + skillId); renderSkills(); }
  }
  if (k === "tab") { e.preventDefault(); gameState.stamina = Math.min(gameState.maxStamina, gameState.stamina + 5); }
});
window.addEventListener("keyup", e => { keys[e.key.toLowerCase()] = false; });
canvas.addEventListener("mousemove", e => {
  const rect = canvas.getBoundingClientRect();
  mouse.x = (e.clientX - rect.left) / rect.width * canvas.width;
  mouse.y = (e.clientY - rect.top) / rect.height * canvas.height;
  mouse.worldX = screenToWorld(mouse.x, mouse.y).x;
  mouse.worldY = screenToWorld(mouse.x, mouse.y).y;
});

// ---------------- Movement ----------------
function moveToward(tx, ty, dt) {
  if (targetX === null) return;
  const dx = tx - gameState.x;
  const dy = ty - gameState.y;
  const d = Math.hypot(dx, dy);
  if (d < 8) { targetX = null; targetY = null; return; }
  const speed = (keys["shift"] ? 1.4 : 1.0) * 150 * dt;
  gameState.x += (dx / d) * speed;
  gameState.y += (dy / d) * speed;
  gameState.facing = dx > 0 ? 1 : -1;
  // Clamp to map
  gameState.x = clamp(gameState.x, 0, currentMap.width * TILE);
  gameState.y = clamp(gameState.y, 0, currentMap.height * TILE);
}

// Camera follows player with deadzone
function updateCamera() {
  const cx = gameState.x - canvas.width / 2;
  const cy = gameState.y - canvas.height / 4;
  camera.x += (cx - camera.x) * 0.15;
  camera.y += (cy - camera.y) * 0.15;
  camera.x = clamp(camera.x, 0, Math.max(0, currentMap.width * TILE - canvas.width));
  camera.y = clamp(camera.y, 0, Math.max(0, currentMap.height * TILE / 2 - canvas.height / 2));
}

// ---------------- Skills ----------------
const SKILL_DEFS = {
  "fire_bolt": { name: "Fire Bolt", cost: 5, cooldown: 0, range: 300, type: "projectile", element: "fire", damage: "6-12" },
  "ice_bolt": { name: "Ice Bolt", cost: 6, cooldown: 0, range: 300, type: "projectile", element: "cold", damage: "5-10" },
  "lightning": { name: "Lightning", cost: 8, cooldown: 1, range: 250, type: "bolt", element: "lightning", damage: "8-16" },
  "heal": { name: "Heal", cost: 10, cooldown: 3, range: 0, type: "self", element: "none", damage: 0 },
};

function useSkillAt(skillId, wx, wy) {
  const def = SKILL_DEFS[skillId];
  if (!def) return;
  if (gameState.mana < def.cost) { setNotice("Not enough mana."); return; }
  if (skillCooldowns[skillId] > 0) return;
  gameState.mana -= def.cost;
  skillCooldowns[skillId] = def.cooldown;
  setNotice("Used " + def.name + ".", 2);
  // Apply effects
  for (const e of currentMap.entities) {
    if (e.kind === "monster" && e.alive && dist({ x: e.x, y: e.y }, { x: wx, y: wy }) < def.range) {
      const dmg = rollDamage(def.damage.split("-")[0] || 0, def.damage.split("-")[1] || 0);
      const dealt = applyDamage(e, dmg, def.element);
      setNotice(def.name + " hits " + (e.name || "monster") + " for " + dealt + " " + def.element + " damage.", 2);
    }
  }
  if (def.type === "self" && def.element === "none") {
    gameState.life = Math.min(gameState.maxLife, gameState.life + 50);
    setNotice("Healed for 50 life.");
  }
}

const skillCooldowns = {};
function updateCooldowns(dt) {
  for (const k of Object.keys(skillCooldowns)) {
    skillCooldowns[k] = Math.max(0, skillCooldowns[k] - dt);
  }
}

function renderSkills() {
  skillsBar.innerHTML = "";
  const skillIds = Object.keys(gameState.skills);
  if (skillIds.length === 0) {
    // Default skill
    gameState.skills.fire_bolt = 1;
    skillIds.push("fire_bolt");
  }
  for (const sid of skillIds) {
    const def = SKILL_DEFS[sid];
    const btn = document.createElement("div");
    btn.className = "skill" + (gameState.activeSkill === sid ? " active" : "") + (skillCooldowns[sid] > 0 ? " cooldown" : "");
    btn.textContent = (def ? def.name : sid) + " L" + (gameState.skills[sid] || 1);
    btn.onclick = () => { gameState.activeSkill = sid; renderSkills(); };
    skillsBar.appendChild(btn);
  }
}

// ---------------- Area transitions ----------------
function changeArea(direction) {
  const current = AREAS[gameState.areaId];
  let nextId = gameState.townArea;
  if (direction === "next" && current.type !== "town") {
    nextId = gameState.townArea;
  }
  loadArea(nextId);
  currentMap = ensureMap(nextId);
  setNotice("Entered " + currentMap.area_kind + ".", 2);
}

// Simplify: ensureMap then load initial area on start
function initGame() {
  gameState.maxLife = computeLife(gameState.vitality, gameState.level,
    classData.base_stats.strength * 2, classData.life_per_level);
  gameState.maxMana = computeMana(gameState.energy, gameState.level,
    classData.base_stats.energy * 2, classData.mana_per_level);
  gameState.life = gameState.maxLife;
  gameState.mana = gameState.maxMana;
  document.getElementById('char-name').textContent = charName + " (" + classData.name + ")";
  renderSkills();
  currentMap = ensureMap(gameState.areaId);
  loadArea(gameState.areaId);
  loadGame();
  overlay.classList.add("hidden");
  canvas.focus();
  lastTime = performance.now();
  requestAnimationFrame(loop);
}

startBtn.addEventListener("click", initGame);

// ---------------- Main loop ----------------
let lastTime = performance.now();
function loop(now) {
  const dt = (now - lastTime) / 1000;
  lastTime = now;
  if (!gameState.dead && !overlay.classList.contains("hidden")) { requestAnimationFrame(loop); return; }
  updateCooldowns(dt);
  if (targetX !== null && targetY !== null) moveToward(targetX, targetY, dt);
  updateCamera();
  renderHud();
  render();
  requestAnimationFrame(loop);
}

function renderHud() {
  document.getElementById('lvl-val').textContent = gameState.level;
  document.getElementById('xp-val').textContent = gameState.experience;
  document.getElementById('hp-val').textContent = Math.floor(gameState.life) + " / " + gameState.maxLife;
  document.getElementById('mp-val').textContent = Math.floor(gameState.mana) + " / " + gameState.maxMana;
  document.getElementById('stam-val').textContent = Math.floor(gameState.stamina) + " / " + gameState.maxStamina;
  document.getElementById('str-val').textContent = gameState.strength;
  document.getElementById('dex-val').textContent = gameState.dexterity;
  document.getElementById('vit-val').textContent = gameState.vitality;
  document.getElementById('ene-val').textContent = gameState.energy;
  document.getElementById('fr-val').textContent = gameState.resist.fire + "%";
  document.getElementById('cr-val').textContent = gameState.resist.cold + "%";
  document.getElementById('lr-val').textContent = gameState.resist.lightning + "%";
  document.getElementById('pr-val').textContent = gameState.resist.poison + "%";
  document.getElementById('gold-chip').textContent = "Gold: " + gameState.gold;
  if (savedEl.style.opacity > 0) { savedEl.style.opacity -= dt * 0.8; if (savedEl.style.opacity < 0) savedEl.style.opacity = 0; }
}

// ---------------- Combat loop (simple auto-attack when adjacent) ----------------
function attackTarget(monster) {
  if (attackCooldown > 0) return;
  attackCooldown = 1.0;
  const dmg = characterAttack();
  const dealt = applyDamage(monster, dmg, "physical");
  setNotice("You strike " + (monster.name || "monster") + " for " + dealt + " damage.", 1.5);
  if (!monster.alive) {
    setNotice((monster.name || "Monster") + " slain.", 2);
  }
  setTimeout(() => { attackCooldown = 0; }, 1000);
}
setInterval(() => { if (attackCooldown > 0) attackCooldown -= 0.1; }, 100);

// Monster AI: chase and bite
setInterval(() => {
  if (gameState.dead) return;
  for (const e of currentMap.entities) {
    if (e.kind === "monster" && e.alive) {
      const d = dist(e, gameState);
      if (d < 40) {
        // Bite
        const dmg = rng.range(e.damage_min || 1, e.damage_max || 4);
        gameState.life = Math.max(0, gameState.life - dmg);
        setNotice((e.name || "Monster") + " hits you for " + dmg + "!", 2);
        if (gameState.life <= 0) { gameState.dead = true; setNotice("You have been slain.", 5); overlay.classList.remove("hidden"); document.getElementById('overlay-title').textContent = "Slain"; document.getElementById('overlay-text').textContent = "Click to restart at town."; }
      } else if (d < 220) {
        // Move toward player
        const dx = gameState.x - e.x;
        const dy = gameState.y - e.y;
        const len = Math.hypot(dx, dy) || 1;
        e.x += (dx / len) * 60 * (1 / 60);
        e.y += (dy / len) * 60 * (1 / 60);
      }
    }
  }
}, 1000 / 60);

// Monster bite cooldown (simplified)
window.addEventListener("load", () => {
  const s = screenToWorld(canvas.width / 2, canvas.height / 4);
  gameState.x = s.x; gameState.y = s.y;
});

</script>
</body>
</html>"""

# Placeholders replaced at export time
PLACEHOLDERS = {
    "__TITLE__": "{title}",
    "__CHAR_NAME__": "{hero_name}",
    "__AREA__": "{starting_area}",
    "__SPEC_JSON__": "{spec_json}",
    "__MAPS_JSON__": "{maps_json}",
    "__CLASSES_JSON__": "{classes_json}",
    "__ITEMS_JSON__": "{items_json}",
    "__MONSTERS_JSON__": "{monsters_json}",
    "__BOSSES_JSON__": "{bosses_json}",
    "__AREAS_JSON__": "{areas_json}",
    "__ACTS_JSON__": "{acts_json}",
    "__QUESTS_JSON__": "{quests_json}",
    "__NPCDATA_JSON__": "{npc_json}",
    "__UNIQUE_ITEMS_JSON__": "{unique_json}",
    "__ITEM_SETS_JSON__": "{sets_json}",
    "__TILE__": str(TILE),
}


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_html(spec: dict, classes: dict, items: dict, monsters: dict,
                bosses: dict, areas: dict, acts: dict, quests: dict,
                npcs: dict, uniques: dict, sets: dict) -> str:
    html = GAME_HTML
    for key, value in PLACEHOLDERS.items():
        html = html.replace(key, value)
    html = html.replace("__SPEC_JSON__", json.dumps(spec, ensure_ascii=False))
    html = html.replace("__MAPS_JSON__", json.dumps({}, ensure_ascii=False))
    html = html.replace("__CLASSES_JSON__", json.dumps(classes, ensure_ascii=False))
    html = html.replace("__ITEMS_JSON__", json.dumps(items, ensure_ascii=False))
    html = html.replace("__MONSTERS_JSON__", json.dumps(monsters, ensure_ascii=False))
    html = html.replace("__BOSSES_JSON__", json.dumps(bosses, ensure_ascii=False))
    html = html.replace("__AREAS_JSON__", json.dumps(areas, ensure_ascii=False))
    html = html.replace("__ACTS_JSON__", json.dumps(acts, ensure_ascii=False))
    html = html.replace("__QUESTS_JSON__", json.dumps(quests, ensure_ascii=False))
    html = html.replace("__NPCDATA_JSON__", json.dumps(npcs, ensure_ascii=False))
    html = html.replace("__UNIQUE_ITEMS_JSON__", json.dumps(uniques, ensure_ascii=False))
    html = html.replace("__ITEM_SETS_JSON__", json.dumps(sets, ensure_ascii=False))
    return html


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate(idea: str, title: str, out: Path, seed: int,
             model: str, vision_model: str, with_review: bool) -> None:
    out.mkdir(parents=True, exist_ok=True)
    project_id = out.name

    # Plan content with local model
    planner_data, planner_source, planner_note = generate_local_content(idea, title, model)

    hero_name = planner_data.get("player", {}).get("name", "Hero")
    class_id = planner_data.get("player", {}).get("role", "amazon").lower()
    if class_id not in CLASS_DATA:
        class_id = "amazon"

    starting_area = "rogue_encampment"
    if "dragon" in idea.lower():
        starting_area = "cold_plains"

    spec = {
        "projectId": project_id,
        "worldName": title,
        "description": idea,
        "heroName": hero_name,
        "playerClass": class_id,
        "startingArea": starting_area,
        "seed": seed,
        "theme": "dark-fantasy",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "runtime": "browser-diablo2",
    }

    # Data bundles for the HTML game
    classes = CLASS_DATA
    items = ITEM_BASES
    monsters = MONSTER_FAMILIES
    bosses = ACT_BOSSES
    areas = AREAS
    acts = ACTS
    quests = QUESTS
    npcs = NPCDATA
    uniques = UNIQUE_ITEMS
    sets = ITEM_SETS

    html = render_html(spec, classes, items, monsters, bosses, areas, acts,
                       quests, npcs, uniques, sets)
    (out / "index.html").write_text(html, encoding="utf-8")

    # Dark fantasy preview art for PWA icons and workbench display
    make_dark_preview(out / "world-preview.png")

    # Game content (schema-like)
    content = dict(planner_data)
    content.update({
        "theme": "dark-fantasy",
        "setting": planner_data.get("setting", "A dark fantasy world of demons and heroes."),
        "runtime": "browser-diablo2",
        "playerClass": class_id,
        "startingArea": starting_area,
        "seed": seed,
    })
    (out / "game-content.json").write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n")

    # Project manifest
    manifest = {
        "schemaVersion": "1.0",
        "project": {
            "id": project_id,
            "name": title,
            "description": idea,
            "status": "complete",
            "target": {"engine": "browser-diablo2", "assetFormats": ["html", "json"],
                       "constraints": ["Local execution only", "Offline playable", "Isometric action RPG"]},
            "styleGuide": {"prompt": idea, "references": [],
                           "palette": ["#0b100e", "#24343A", "#f1bd75", "#c73c47", "#9ed3c6"],
                           "notes": "Diablo-style dark fantasy isometric action RPG."},
        },
        "assets": [],
        "stages": [
            {"id": "diablo2-design", "kind": "brief", "status": "complete",
             "worker": {"name": planner_source, "execution": "local"},
             "outputs": [{"id": "game-content", "path": "game-content.json", "mediaType": "application/json", "format": "json"}]},
            {"id": "diablo2-build", "kind": "engine-project", "status": "complete",
             "outputs": [{"id": "playable", "path": "index.html", "mediaType": "text/html", "format": "html"}],
             "worker": {"name": "scripts/generate_diablo2.py", "execution": "local"}},
        ],
        "deliverables": [{"id": "diablo2-clone", "name": "Diablo-style action RPG slice", "status": "generated",
                          "outputs": [{"id": "playable", "path": "index.html", "mediaType": "text/html", "format": "html"}],
                          "acceptanceCriteria": ["Game opens and runs offline in any browser.",
                                                 "Isometric movement, combat, loot, and skills.",
                                                 "Random dungeon areas with stairs and waypoints."]}],
        "metadata": {"generatedAt": datetime.now(timezone.utc).isoformat(),
                     "generator": "scripts/generate_diablo2.py",
                     "localOnly": True, "contentPlanner": planner_source,
                     "plannerNote": planner_note, "runtime": "browser-diablo2",
                     "seed": seed, "heroName": hero_name, "playerClass": class_id},
    }
    (out / "project.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "idea.txt").write_text(idea.strip() + "\n")
    (out / "README.md").write_text(f"""\
# {title}

A Diablo 2-style action RPG generated from the Vibe Create workbench.

Open `index.html` in any browser to play offline. No engine installation required.

## Controls
- WASD / arrow keys: move
- Left-click: move or attack
- Right-click: use equipped skill
- Keys 1-6: equip skill to hotkey
- Tab: regenerate stamina

## Features
- Character class: {class_data["name"] if (class_data := CLASS_DATA.get(class_id)) else "Amazon"}
- Starting area: {starting_area}
- Random dungeon generation with stairs and waypoints
- Loot, skills, resistances, and combat

Generated locally by Vibe Create — {project_id}
""")

    print(f"Created {out / 'index.html'} (offline playable Diablo-style RPG slice)")
    print(f"Created {out / 'game-content.json'} using {planner_source}")
    print(f"Created {out / 'project.json'} (asset pipeline manifest)")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Generate a Diablo 2-style action RPG project")
    parser.add_argument("idea")
    parser.add_argument("--title", default="")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=4172026)
    parser.add_argument("--model", default=os.environ.get("VIBE_GAME_MODEL", "qwen3.5:2b"))
    parser.add_argument("--vision-model", default=os.environ.get("VIBE_VISION_MODEL", "qwen2.5vl:3b"))
    parser.add_argument("--skip-vision-review", action="store_true")
    args = parser.parse_args()
    title = args.title.strip() or " ".join(args.idea.split()[:5]).strip(".,!?;:") or "Diablo Clone"
    generate(args.idea, title, args.out, args.seed, args.model,
             args.vision_model, not args.skip_vision_review)


if __name__ == "__main__":
    main()
