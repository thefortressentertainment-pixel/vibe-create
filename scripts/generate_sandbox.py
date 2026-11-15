#!/usr/bin/env python3
"""Generate a local, seeded Godot 4 side-scrolling sandbox slice."""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
import subprocess
import sys
import textwrap
import zlib
from datetime import datetime, timezone
from pathlib import Path

from local_game_planner import generate_local_content


TILE = 16
CHUNK_TILES = 32
WORLD_HEIGHT = 96

PALETTES = {
    "verdant": {
        "name": "Verdant Depths",
        "grass": "#78B56B", "grass_dark": "#477D53", "dirt": "#94634D",
        "dirt_light": "#BC8060", "stone": "#555E62", "stone_light": "#778184",
        "ore": "#D88B5D", "moss": "#4A785F", "wood": "#80533C",
        "wood_light": "#B27A4C", "leaf": "#4B8759", "leaf_light": "#83B763",
        "cave": "#18242B", "cave_light": "#24343A", "crystal": "#70D6C2",
        "sky": "#85B8C5", "sky_top": "#38566D", "sun": "#F6D78A",
    },
    "bog": {
        "name": "Murkfen Lanterns",
        "grass": "#91A36A", "grass_dark": "#56694D", "dirt": "#795E52",
        "dirt_light": "#A27A61", "stone": "#4D5658", "stone_light": "#6E7B76",
        "ore": "#C98C54", "moss": "#536F5A", "wood": "#6F5541",
        "wood_light": "#A17C52", "leaf": "#647B50", "leaf_light": "#A0AA62",
        "cave": "#1C2328", "cave_light": "#303735", "crystal": "#A4D6A0",
        "sky": "#9EAFA4", "sky_top": "#52656A", "sun": "#F3C577",
    },
    "frost": {
        "name": "Blueglass Frost",
        "grass": "#A4C9BD", "grass_dark": "#6D9A96", "dirt": "#786E72",
        "dirt_light": "#A19691", "stone": "#536778", "stone_light": "#8AA5B0",
        "ore": "#D99A70", "moss": "#54828A", "wood": "#6A5960",
        "wood_light": "#A07E70", "leaf": "#54817C", "leaf_light": "#91B9A8",
        "cave": "#182334", "cave_light": "#26384B", "crystal": "#82DBF0",
        "sky": "#A6D4E2", "sky_top": "#46698B", "sun": "#F4E7BA",
    },
    "ember": {
        "name": "Ashen Foundry",
        "grass": "#A68764", "grass_dark": "#685248", "dirt": "#72534C",
        "dirt_light": "#A06D56", "stone": "#515158", "stone_light": "#79777B",
        "ore": "#F08A50", "moss": "#68604D", "wood": "#684A3B",
        "wood_light": "#9A6645", "leaf": "#756349", "leaf_light": "#B18A51",
        "cave": "#211D25", "cave_light": "#34272A", "crystal": "#F0BA65",
        "sky": "#B39A85", "sky_top": "#544E61", "sun": "#F5C878",
    },
}

# Biome settings are separate from palette colors. They control terrain shape:
# surface amplitude, cave radius, and tree frequency.
BIOME_SETTINGS = {
    "temperate": {"surface_amp": 3.0, "surface_amp2": 1.3, "cave_radius": 8, "cave_amp": 2.0, "tree_freq": 47},
    "overgrown": {"surface_amp": 2.5, "surface_amp2": 1.1, "cave_radius": 7, "cave_amp": 1.8, "tree_freq": 35},
    "barren": {"surface_amp": 4.0, "surface_amp2": 1.6, "cave_radius": 9, "cave_amp": 2.2, "tree_freq": 70},
    "fractured": {"surface_amp": 3.0, "surface_amp2": 1.3, "cave_radius": 10, "cave_amp": 2.5, "tree_freq": 47},
}

# Enemy behavior tuning: walk speed and chase range.
ENEMY_BEHAVIOR = {
    "patrol": {"walk_speed": 54.0, "chase_range": 170.0},
    "stationary": {"walk_speed": 0.0, "chase_range": 170.0},
    "aggressive": {"walk_speed": 90.0, "chase_range": 260.0},
}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48] or "sandbox-world"


def choose_palette(idea: str) -> tuple[str, dict[str, str]]:
    lowered = idea.casefold()
    def mentions(*words: str) -> bool:
        alternatives = "|".join(re.escape(word) for word in words)
        return re.search(rf"\b(?:{alternatives})\b", lowered) is not None

    if mentions("bog", "swamp", "fen", "mire", "marsh"):
        key = "bog"
    elif mentions("ice", "frost", "snow", "glacier", "winter"):
        key = "frost"
    elif mentions("ash", "ember", "volcano", "lava", "forge"):
        key = "ember"
    else:
        key = "verdant"
    return key, PALETTES[key]


def rgb(color: str) -> tuple[int, int, int, int]:
    return tuple(bytes.fromhex(color.removeprefix("#"))) + (255,)


class PixelImage:
    def __init__(self, width: int, height: int, color: str = "#000000") -> None:
        self.width, self.height = width, height
        self.data = bytearray(width * height * 4)
        self.fill(color)

    def fill(self, color: str) -> None:
        value = bytes(rgb(color))
        self.data[:] = value * (self.width * self.height)

    def px(self, x: int, y: int, color: str) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            i = (y * self.width + x) * 4
            self.data[i:i + 4] = bytes(rgb(color))

    def rect(self, x: int, y: int, w: int, h: int, color: str) -> None:
        for yy in range(max(0, y), min(self.height, y + h)):
            for xx in range(max(0, x), min(self.width, x + w)):
                self.px(xx, yy, color)

    def line(self, x1: int, y1: int, x2: int, y2: int, color: str) -> None:
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        error = dx - dy
        while True:
            self.px(x1, y1, color)
            if x1 == x2 and y1 == y2:
                break
            twice = error * 2
            if twice > -dy:
                error -= dy
                x1 += sx
            if twice < dx:
                error += dx
                y1 += sy


FONT_3X5 = {
    "A": ("010", "101", "111", "101", "101"), "B": ("110", "101", "110", "101", "110"),
    "C": ("011", "100", "100", "100", "011"), "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"), "F": ("111", "100", "110", "100", "100"),
    "G": ("011", "100", "101", "101", "011"), "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"), "J": ("001", "001", "001", "101", "010"),
    "K": ("101", "101", "110", "101", "101"), "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"), "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"), "P": ("110", "101", "110", "100", "100"),
    "Q": ("010", "101", "101", "111", "011"), "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"), "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"), "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"), "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"), "Z": ("111", "001", "010", "100", "111"),
    "0": ("111", "101", "101", "101", "111"), "1": ("010", "110", "010", "010", "111"),
    "2": ("110", "001", "010", "100", "111"), "3": ("110", "001", "010", "001", "110"),
    "4": ("101", "101", "111", "001", "001"), "5": ("111", "100", "110", "001", "110"),
    "6": ("011", "100", "110", "101", "010"), "7": ("111", "001", "010", "010", "010"),
    "8": ("010", "101", "010", "101", "010"), "9": ("010", "101", "011", "001", "110"),
    ":": ("000", "010", "000", "010", "000"), ".": ("000", "000", "000", "000", "010"),
    "-": ("000", "000", "111", "000", "000"), "/": ("001", "001", "010", "100", "100"),
}


def draw_label(image: PixelImage, x: int, y: int, value: str, color: str, scale: int = 2) -> None:
    cursor = x
    for char in value.upper():
        glyph = FONT_3X5.get(char)
        if glyph:
            for row, bits in enumerate(glyph):
                for col, bit in enumerate(bits):
                    if bit == "1":
                        image.rect(cursor + col * scale, y + row * scale, scale, scale, color)
        cursor += 4 * scale


def write_png(path: Path, image: PixelImage) -> None:
    def chunk(kind: bytes, content: bytes) -> bytes:
        payload = kind + content
        return struct.pack(">I", len(content)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)

    scanlines = bytearray()
    stride = image.width * 4
    for y in range(image.height):
        scanlines.append(0)
        scanlines.extend(image.data[y * stride:(y + 1) * stride])
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", image.width, image.height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(scanlines), 9))
    png += chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def make_tile_atlas(p: dict[str, str], seed: int) -> PixelImage:
    atlas = PixelImage(8 * TILE, 2 * TILE, p["cave"])

    def tile(tile_id: int, draw) -> None:
        ox, oy = (tile_id % 8) * TILE, (tile_id // 8) * TILE
        draw(ox, oy)

    def grass(ox, oy):
        atlas.rect(ox, oy, 16, 16, p["dirt"])
        atlas.rect(ox, oy, 16, 4, p["grass_dark"])
        atlas.rect(ox, oy, 16, 3, p["grass"])
        for x in (2, 7, 12):
            atlas.rect(ox + x, oy + 1, 2, 2, p["leaf_light"])
        for x, y in ((3, 8), (11, 6), (8, 13), (14, 11), (5, 12)):
            atlas.px(ox + x, oy + y, p["dirt_light"])

    def dirt(ox, oy):
        atlas.rect(ox, oy, 16, 16, p["dirt"])
        for x, y in ((2, 3), (11, 5), (7, 10), (13, 14), (4, 14)):
            atlas.rect(ox + x, oy + y, 2, 2, p["dirt_light"])

    def stone(ox, oy):
        atlas.rect(ox, oy, 16, 16, p["stone"])
        atlas.line(ox + 2, oy + 5, ox + 6, oy + 3, p["stone_light"])
        atlas.line(ox + 6, oy + 3, ox + 9, oy + 5, p["stone_light"])
        atlas.line(ox + 10, oy + 12, ox + 14, oy + 10, p["stone_light"])
        atlas.px(ox + 4, oy + 11, p["cave_light"])

    def ore(ox, oy):
        stone(ox, oy)
        for x, y in ((5, 5), (6, 4), (7, 5), (9, 10), (10, 9), (11, 10)):
            atlas.px(ox + x, oy + y, p["ore"])
        atlas.px(ox + 6, oy + 6, p["sun"])

    def moss(ox, oy):
        stone(ox, oy)
        for x, y in ((1, 1), (2, 1), (3, 2), (8, 1), (9, 2), (13, 1), (14, 1)):
            atlas.px(ox + x, oy + y, p["moss"])

    def wood(ox, oy):
        atlas.rect(ox, oy, 16, 16, p["wood"])
        atlas.rect(ox + 3, oy, 3, 16, p["wood_light"])
        atlas.rect(ox + 10, oy, 2, 16, p["dirt"])
        atlas.line(ox + 1, oy + 4, ox + 3, oy + 4, p["dirt_light"])

    def leaves(ox, oy):
        atlas.rect(ox + 3, oy + 1, 10, 4, p["leaf"])
        atlas.rect(ox + 1, oy + 4, 14, 8, p["leaf"])
        atlas.rect(ox + 4, oy + 11, 8, 4, p["leaf"])
        atlas.rect(ox + 4, oy + 4, 4, 2, p["leaf_light"])
        atlas.px(ox + 10, oy + 8, p["leaf_light"])
        atlas.px(ox + 5, oy + 10, p["grass_dark"])

    def crystal(ox, oy):
        stone(ox, oy)
        atlas.line(ox + 4, oy + 12, ox + 7, oy + 5, p["crystal"])
        atlas.line(ox + 7, oy + 5, ox + 10, oy + 12, p["crystal"])
        atlas.line(ox + 10, oy + 12, ox + 4, oy + 12, p["crystal"])
        atlas.line(ox + 7, oy + 6, ox + 7, oy + 13, p["sun"])

    def cave(ox, oy):
        atlas.rect(ox, oy, 16, 16, p["cave"])
        atlas.rect(ox + 1, oy + 2, 5, 3, p["cave_light"])
        atlas.rect(ox + 9, oy + 9, 4, 2, p["cave_light"])
        atlas.px(ox + 3, oy + 12, p["stone"])

    for tile_id, draw in enumerate((grass, dirt, stone, ore, moss, wood, leaves, crystal, cave)):
        tile(tile_id, draw)
    # A seed-specific fleck makes art variations reproducible without changing tile readability.
    atlas.px(15, seed % 13 + 1, p["sun"])
    return atlas


def make_player_sheet(p: dict[str, str]) -> PixelImage:
    sheet = PixelImage(4 * 24, 32, "#000000")
    sheet.data[:] = bytes((0, 0, 0, 0)) * (sheet.width * sheet.height)
    for frame in range(4):
        ox = frame * 24
        leg_shift = (0, 1, 0, -1)[frame]
        # Soft silhouette, teal tunic, warm scarf, bright eyes.
        sheet.rect(ox + 7, 2, 10, 2, "#413B46")
        sheet.rect(ox + 5, 4, 14, 9, "#D4A77A")
        sheet.rect(ox + 6, 4, 12, 3, "#543E39")
        sheet.rect(ox + 4, 6, 3, 4, "#543E39")
        sheet.rect(ox + 7, 8, 2, 2, "#26323D")
        sheet.rect(ox + 15, 8, 2, 2, "#26323D")
        sheet.px(ox + 8, 8, "#F5E5BA")
        sheet.px(ox + 16, 8, "#F5E5BA")
        sheet.rect(ox + 7, 13, 10, 10, "#377E82")
        sheet.rect(ox + 7, 13, 10, 2, "#65B1A1")
        sheet.rect(ox + 5, 15, 3, 8, "#D4A77A")
        sheet.rect(ox + 16, 15, 3, 7, "#D4A77A")
        sheet.rect(ox + 8, 22 + leg_shift, 4, 7, "#394958")
        sheet.rect(ox + 13, 22 - leg_shift, 4, 7, "#394958")
        sheet.rect(ox + 7, 28 + leg_shift, 6, 2, "#2A303A")
        sheet.rect(ox + 12, 28 - leg_shift, 6, 2, "#2A303A")
        sheet.rect(ox + 5, 14, 3, 3, "#E7BA78")
    return sheet


def make_slime_sheet(p: dict[str, str]) -> PixelImage:
    sheet = PixelImage(48, 24, "#000000")
    sheet.data[:] = bytes((0, 0, 0, 0)) * (sheet.width * sheet.height)
    for frame in range(2):
        ox = frame * 24
        width = 16 if frame == 0 else 22
        left = ox + (24 - width) // 2
        height = 11 if frame == 0 else 6
        top = 13 - height
        sheet.rect(left + 4, top, width - 8, 2, p["crystal"])
        sheet.rect(left + 1, top + 2, width - 2, max(1, height - 4), p["leaf"])
        sheet.rect(left + 3, top + height - 2, width - 6, 2, p["grass_dark"])
        eye_y = top + (4 if frame == 0 else 2)
        eye_left = left + 5
        eye_right = left + width - 7
        for eye_x in (eye_left, eye_right):
            sheet.px(eye_x, eye_y, "#F3E9C8")
            sheet.px(eye_x + 1, eye_y, "#27333B")
    return sheet


def mix_seed(seed: int, value: int) -> int:
    n = (seed ^ (value * 374761393)) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return n ^ (n >> 16)


def biome_constants(biome: str, chaos: float) -> dict:
    base = BIOME_SETTINGS.get(biome, BIOME_SETTINGS["temperate"])
    c = max(0.1, float(chaos))
    return {
        "surface_amplitude": base["surface_amp"] * c,
        "surface_amplitude2": base["surface_amp2"] * c,
        "cave_radius_base": int(base["cave_radius"] * c),
        "cave_amplitude": base["cave_amp"] * c,
        "tree_frequency": max(12, int(base["tree_freq"])),
    }


def surface_at(x: int, seed: int, bc: dict | None = None) -> int:
    phase = (seed % 100000) * 0.00013
    bc = bc or {}
    return int(24 + round(math.sin(x * 0.045 + phase) * bc.get("surface_amplitude", 3.0)
                      + math.sin(x * 0.12 + phase * 0.5) * bc.get("surface_amplitude2", 1.3)))


def cave_at(x: int, seed: int, bc: dict | None = None) -> tuple[int, int]:
    phase = (seed % 100000) * 0.00013
    bc = bc or {}
    center = int(surface_at(x, seed, bc)) + 35 + round(math.sin(x * 0.034 + phase) * bc.get("cave_amplitude", 2.0))
    radius = int(bc.get("cave_radius_base", 8)) + round(math.sin(x * 0.071 + phase * 1.7) * bc.get("cave_amplitude", 2.0))
    return center, radius


def is_cave(x: int, y: int, seed: int, width: int, bc: dict | None = None) -> bool:
    center, radius = cave_at(x, seed, bc)
    entrance_x = width // 2
    shaft = abs(x - entrance_x) <= 2 and surface_at(x, seed, bc) <= y < center + radius
    tunnel = 10 < x < width - 10 and surface_at(x, seed, bc) + 10 < y < WORLD_HEIGHT - 4 and abs(y - center) < radius
    return shaft or tunnel


def tile_at(x: int, y: int, seed: int, width: int, bc: dict | None = None) -> int:
    surface = surface_at(x, seed, bc)
    if y < surface:
        return -1
    if is_cave(x, y, seed, width):
        return -1
    if y == surface:
        return 0
    if y <= surface + 5:
        return 1
    roll = mix_seed(seed, x * 131 + y * 65537) % 149
    if y > surface + 16 and roll < 3:
        return 3
    if y > surface + 16 and roll == 3:
        return 7
    if roll < 8:
        return 4
    return 2


def make_world_preview(path: Path, palette: dict[str, str], seed: int, chunks: int,
                       biome: str = "temperate", chaos: float = 1.0) -> None:
    width = chunks * CHUNK_TILES
    scale = 4
    preview = PixelImage(width * scale, WORLD_HEIGHT * scale, palette["sky"])
    for y in range(preview.height):
        t = y / max(1, preview.height - 1)
        c1, c2 = rgb(palette["sky_top"]), rgb(palette["sky"])
        color = "#%02X%02X%02X" % tuple(round(c1[i] * (1 - t) + c2[i] * t) for i in range(3))
        preview.rect(0, y, preview.width, 1, color)

    # Distant ridges and a small sun make the thumbnail read as a landscape at a glance.
    for x in range(0, preview.width, 5):
        ridge = 30 + round(math.sin(x * 0.017 + seed * 0.002) * 8)
        preview.rect(x, ridge, 5, preview.height // scale - ridge, palette["sky_top"])
    preview.rect(preview.width - 92, 28, 18, 18, palette["sun"])
    preview.rect(preview.width - 88, 24, 10, 2, palette["sun"])

    bc = biome_constants(biome, chaos)

    # The preview uses the same column/cave functions as the runtime generator.
    cell_map: dict[tuple[int, int], int] = {}
    for x in range(width):
        surface = surface_at(x, seed, bc)
        for y in range(surface, WORLD_HEIGHT):
            cell_map[(x, y)] = tile_at(x, y, seed, width, bc)

    # Place trees after all ground columns so canopies are not overwritten by later columns.
    tree_start = 19 + seed % 41
    for x in range(width):
        surface = surface_at(x, seed, bc)
        if 8 < x < width - 8 and (x - tree_start) % bc["tree_frequency"] == 0 and cell_map.get((x, surface)) == 0:
            for y in range(max(0, surface - 4), surface):
                cell_map[(x, y)] = 5
            for tx in range(x - 2, x + 3):
                for ty in range(surface - 7, surface - 3):
                    if abs(tx - x) + abs(ty - (surface - 5)) < 5 and cell_map.get((tx, ty), -1) < 0:
                        cell_map[(tx, ty)] = 6

    for x in range(width):
        surface = surface_at(x, seed, bc)
        for y in range(max(0, surface - 8), WORLD_HEIGHT):
            if (x, y) not in cell_map:
                continue
            if cell_map[(x, y)] < 0:
                if is_cave(x, y, seed, width, bc):
                    preview.rect(x * scale, y * scale, scale, scale, palette["cave"])
                continue
            if is_cave(x, y, seed, width, bc):
                color = palette["cave"]
            else:
                tile_id = cell_map[(x, y)]
                color = {
                    0: palette["grass"], 1: palette["dirt"], 2: palette["stone"],
                    3: palette["ore"], 4: palette["moss"], 5: palette["wood"],
                    6: palette["leaf"], 7: palette["crystal"],
                }.get(tile_id, palette["stone"])
            preview.rect(x * scale, y * scale, scale, scale, color)

    # A tiny player marker and one cave slime make the playable slice legible in the workbench.
    hero_x = min(width - 4, max(4, width // 8))
    hero_y = surface_at(hero_x, seed, bc) - 3
    preview.rect(hero_x * scale - 3, hero_y * scale - 4, 6, 10, "#377E82")
    preview.rect(hero_x * scale - 2, hero_y * scale - 8, 5, 5, "#D4A77A")
    slime_x = int(width * 0.67)
    slime_center, slime_radius = cave_at(slime_x, seed, bc)
    slime_y = min(WORLD_HEIGHT - 7, slime_center + slime_radius + 3)
    preview.rect(slime_x * scale - 4, slime_y * scale - 3, 8, 4, palette["leaf_light"])
    write_png(path, preview)


def make_art_review(path: Path, atlas: PixelImage, player: PixelImage, slime: PixelImage, p: dict[str, str]) -> None:
    tile_scale = 3
    sprite_scale = 2
    image = PixelImage(840, 340, "#10191B")
    image.rect(0, 0, image.width, 8, "#24343A")
    draw_label(image, 18, 17, "PIXEL ART REVIEW", "#B8D9C6", 2)
    # Tile atlas preview, laid out on a quiet grid.
    draw_label(image, 18, 38, "TERRAIN ATLAS / 16 PX TILES", "#83B763", 2)
    for tile_id in range(9):
        col, row = tile_id % 8, tile_id // 8
        src_x, src_y = col * 16, row * 16
        dst_x, dst_y = 18 + col * 58, 67 + row * 60
        image.rect(dst_x - 4, dst_y - 4, 56, 56, "#1B292C")
        image.rect(dst_x - 4, dst_y - 4, 56, 2, "#38534C")
        for y in range(16):
            for x in range(16):
                src = ((src_y + y) * atlas.width + src_x + x) * 4
                if atlas.data[src + 3] > 0:
                    color = "#%02X%02X%02X" % tuple(atlas.data[src:src + 3])
                    image.rect(dst_x + x * tile_scale, dst_y + y * tile_scale, tile_scale, tile_scale, color)
    # Sprite families sit in their own labeled rows with a clear gutter from the tile atlas.
    draw_label(image, 510, 17, "PLAYER / 4 FRAMES", "#83B763", 2)
    for frame in range(4):
        dst_x, dst_y = 520 + frame * 74, 46
        image.rect(dst_x - 7, dst_y - 6, 62, 78, "#24363B")
        image.rect(dst_x - 7, dst_y - 6, 62, 2, "#70D6C2")
        for y in range(player.height):
            for x in range(24):
                src = (y * player.width + frame * 24 + x) * 4
                if player.data[src + 3]:
                    color = "#%02X%02X%02X" % tuple(player.data[src:src + 3])
                    image.rect(dst_x + x * sprite_scale, dst_y + y * sprite_scale, sprite_scale, sprite_scale, color)
    draw_label(image, 510, 156, "CAVE SLIME / 2 FRAMES", "#83B763", 2)
    for frame in range(2):
        dst_x, dst_y = 570 + frame * 82, 184
        image.rect(dst_x - 8, dst_y - 8, 64, 64, "#24363B")
        image.rect(dst_x - 8, dst_y - 8, 64, 2, "#70D6C2")
        for y in range(slime.height):
            for x in range(24):
                src = (y * slime.width + frame * 24 + x) * 4
                if slime.data[src + 3]:
                    color = "#%02X%02X%02X" % tuple(slime.data[src:src + 3])
                    image.rect(dst_x + x * sprite_scale, dst_y + y * sprite_scale, sprite_scale, sprite_scale, color)
    write_png(path, image)


WORLD_GD = r'''extends Node2D

const TILE_SIZE := 16
const CHUNK_TILES := 32
const WORLD_HEIGHT := 96
const TILE_SOURCE := 0
const SAVE_DIR := "user://saves"

var spec: Dictionary = {}
var seed_value: int = 0
var chunk_count: int = 8
var world_width: int = 0
var ground: TileMapLayer
var backing: TileMapLayer
var player
var enemy
var removed: Dictionary = {}
var placed: Dictionary = {}
var tile_set_data: TileSet

func configure(world_spec: Dictionary) -> void:
	spec = world_spec
	seed_value = int(spec.get("seed", 4172026))
	chunk_count = int(spec.get("chunks", 8))
	world_width = chunk_count * CHUNK_TILES

func build() -> void:
	var tileset_atlas := TileSetAtlasSource.new()
	tileset_atlas.texture = load("res://Art/tiles.png")
	tileset_atlas.texture_region_size = Vector2i(TILE_SIZE, TILE_SIZE)
	tile_set_data = TileSet.new()
	tile_set_data.tile_size = Vector2i(TILE_SIZE, TILE_SIZE)
	tile_set_data.add_physics_layer()
	for tile_id in range(9):
		var atlas_coords := Vector2i(tile_id % 8, floori(float(tile_id) / 8.0))
		tileset_atlas.create_tile(atlas_coords)
	tile_set_data.add_source(tileset_atlas, TILE_SOURCE)
	for tile_id in range(9):
		var atlas_coords := Vector2i(tile_id % 8, floori(float(tile_id) / 8.0))
		if tile_id not in [6, 8]:
			var tile_data := tileset_atlas.get_tile_data(atlas_coords, 0)
			tile_data.set_collision_polygons_count(0, 1)
			tile_data.set_collision_polygon_points(0, 0, PackedVector2Array([
				Vector2(0, 0), Vector2(TILE_SIZE, 0),
				Vector2(TILE_SIZE, TILE_SIZE), Vector2(0, TILE_SIZE)
			]))
	backing = TileMapLayer.new()
	backing.name = "CaveBacking"
	backing.tile_set = tile_set_data
	backing.z_index = -2
	backing.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	ground = TileMapLayer.new()
	ground.name = "Terrain"
	ground.tile_set = tile_set_data
	ground.z_index = 0
	ground.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	add_child(backing)
	add_child(ground)
	generate_chunks()

func generate_chunks() -> void:
	# Heights and cave profiles use global x, so each chunk shares the same edge column.
	for chunk_index in range(chunk_count):
		var chunk_start := chunk_index * CHUNK_TILES
		var chunk_end := mini(world_width, chunk_start + CHUNK_TILES)
		for x in range(chunk_start, chunk_end):
			var surface := surface_at(x)
			for y in range(surface, WORLD_HEIGHT):
				backing.set_cell(Vector2i(x, y), TILE_SOURCE, Vector2i(0, 1))
				var tile_id := base_tile_at(x, y)
				if tile_id >= 0:
					set_ground_cell(Vector2i(x, y), tile_id)
				if y == WORLD_HEIGHT - 1:
					set_ground_cell(Vector2i(x, y), 2)
			if is_tree_column(x, surface):
				for y in range(maxi(1, surface - 4), surface):
					set_ground_cell(Vector2i(x, y), 5)
				for tx in range(x - 2, x + 3):
					for ty in range(surface - 7, surface - 3):
						if tx >= 0 and tx < world_width and absi(tx - x) + absi(ty - (surface - 5)) < 5 and base_tile_at(tx, ty) < 0:
							set_ground_cell(Vector2i(tx, ty), 6)
	for key in removed.keys():
		var cell := parse_cell_key(str(key))
		ground.erase_cell(cell)
	for key in placed.keys():
		var cell := parse_cell_key(str(key))
		set_ground_cell(cell, int(placed[key]))

func surface_at(x: int) -> int:
	var phase := float(seed_value % 100000) * 0.00013
	return 24 + roundi(sin(float(x) * 0.045 + phase) * 3.0 + sin(float(x) * 0.12 + phase * 0.5) * 1.3)

func cave_center_at(x: int) -> int:
	var phase := float(seed_value % 100000) * 0.00013
	return surface_at(x) + 35 + roundi(sin(float(x) * 0.034 + phase) * 2.0)

func cave_radius_at(x: int) -> int:
	var phase := float(seed_value % 100000) * 0.00013
	return 8 + roundi(sin(float(x) * 0.071 + phase * 1.7) * 2.0)

func in_cave(x: int, y: int) -> bool:
	var entrance_x := int(world_width / 2)
	var shaft: bool = abs(x - entrance_x) <= 2 and y >= surface_at(x) and y < cave_center_at(x) + cave_radius_at(x)
	var tunnel: bool = x > 10 and x < world_width - 10 and y > surface_at(x) + 10 and y < WORLD_HEIGHT - 4 and abs(y - cave_center_at(x)) < cave_radius_at(x)
	return shaft or tunnel

func base_tile_at(x: int, y: int) -> int:
	var surface := surface_at(x)
	if y < surface or in_cave(x, y):
		return -1
	if y == surface:
		return 0
	if y <= surface + 5:
		return 1
	var roll := hash_cell(x, y) % 149
	if y > surface + 16 and roll < 3:
		return 3
	if y > surface + 16 and roll == 3:
		return 7
	return 4 if roll < 8 else 2

func hash_cell(x: int, y: int) -> int:
	var value := x * 131 + y * 65537
	var n := int((seed_value ^ (value * 374761393)) & 0xFFFFFFFF)
	n = int(((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF)
	return n ^ (n >> 16)

func is_tree_column(x: int, surface: int) -> bool:
	return x > 8 and x < world_width - 8 and (x - 19 - (seed_value % 41)) % 47 == 0 and base_tile_at(x, surface) == 0

func set_ground_cell(cell: Vector2i, tile_id: int) -> void:
	ground.set_cell(cell, TILE_SOURCE, Vector2i(tile_id % 8, floori(float(tile_id) / 8.0)))

func cell_from_world(position: Vector2) -> Vector2i:
	return ground.local_to_map(ground.to_local(position))

func tile_id_at(cell: Vector2i) -> int:
	if ground.get_cell_source_id(cell) != TILE_SOURCE:
		return -1
	var coords := ground.get_cell_atlas_coords(cell)
	return coords.y * 8 + coords.x

func mine_at(world_position: Vector2) -> void:
	if player == null or player.global_position.distance_to(world_position) > 112.0:
		return
	var cell := cell_from_world(world_position)
	if cell.x < 0 or cell.x >= world_width or cell.y < 0 or cell.y >= WORLD_HEIGHT:
		return
	var tile_id := tile_id_at(cell)
	if tile_id < 0:
		return
	if tile_id in [2, 3, 4, 7] and not player.has_pickaxe:
		player.set_notice("Stone needs a pickaxe. Gather four wood from tree trunks.")
		return
	match tile_id:
		0, 1: player.inventory["dirt"] = int(player.inventory.get("dirt", 0)) + 1
		2, 4: player.inventory["stone"] = int(player.inventory.get("stone", 0)) + 1
		3: player.inventory["copper"] = int(player.inventory.get("copper", 0)) + 1
		5, 6: player.inventory["wood"] = int(player.inventory.get("wood", 0)) + 1
		7: player.inventory["crystal"] = int(player.inventory.get("crystal", 0)) + 1
	ground.erase_cell(cell)
	removed[cell_key(cell)] = true
	placed.erase(cell_key(cell))
	player.set_notice("Mined a block.")
	save_game()

func place_at(world_position: Vector2) -> void:
	if player == null or player.global_position.distance_to(world_position) > 112.0:
		return
	var cell := cell_from_world(world_position)
	if cell.x < 0 or cell.x >= world_width or cell.y < 0 or cell.y >= WORLD_HEIGHT:
		return
	if tile_id_at(cell) >= 0 or int(player.inventory.get("dirt", 0)) <= 0:
		return
	var cell_center := ground.to_global(ground.map_to_local(cell))
	if player.global_position.distance_to(cell_center) < 22.0:
		return
	player.inventory["dirt"] = int(player.inventory["dirt"]) - 1
	set_ground_cell(cell, 1)
	removed.erase(cell_key(cell))
	placed[cell_key(cell)] = 1
	player.set_notice("Placed a dirt block.")
	save_game()

func craft_pickaxe() -> bool:
	if player == null or player.has_pickaxe or int(player.inventory.get("wood", 0)) < 4:
		return false
	player.inventory["wood"] = int(player.inventory["wood"]) - 4
	player.has_pickaxe = true
	player.set_notice("Wooden pickaxe crafted. Stone and ore can now be mined.")
	save_game()
	return true

func attack_nearby(actor: CharacterBody2D) -> bool:
	if enemy == null or not is_instance_valid(enemy) or enemy.get_meta("defeated", false):
		return false
	if actor.global_position.distance_to(enemy.global_position) > 48.0:
		return false
	enemy.call("take_hit", 1)
	return true

func enemy_floor_position(x: int) -> Vector2:
	var floor_y := cave_center_at(x) + cave_radius_at(x)
	return Vector2(float(x * TILE_SIZE), float(floor_y * TILE_SIZE - 12))

func cell_key(cell: Vector2i) -> String:
	return "%d,%d" % [cell.x, cell.y]

func parse_cell_key(key: String) -> Vector2i:
	var parts := key.split(",")
	return Vector2i(int(parts[0]), int(parts[1])) if parts.size() == 2 else Vector2i.ZERO

func save_path() -> String:
	return SAVE_DIR.path_join(str(spec.get("projectId", "sandbox-world")) + ".json")

func save_game() -> void:
	if player == null:
		return
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(SAVE_DIR))
	var removed_cells: Array[String] = []
	for key in removed.keys():
		removed_cells.append(str(key))
	var placed_cells: Array[Dictionary] = []
	for key in placed.keys():
		var cell := parse_cell_key(str(key))
		placed_cells.append({"x": cell.x, "y": cell.y, "tile": int(placed[key])})
	var payload := {
		"seed": seed_value,
		"removed": removed_cells,
		"placed": placed_cells,
		"player": {"x": player.global_position.x, "y": player.global_position.y,
			"health": player.health, "inventory": player.inventory, "has_pickaxe": player.has_pickaxe},
		"enemy_defeated": enemy != null and is_instance_valid(enemy) and enemy.get_meta("defeated", false)
	}
	var file := FileAccess.open(save_path(), FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(payload))

func load_game() -> bool:
	if not FileAccess.file_exists(save_path()):
		return false
	var file := FileAccess.open(save_path(), FileAccess.READ)
	if file == null:
		return false
	var payload: Variant = JSON.parse_string(file.get_as_text())
	if not payload is Dictionary:
		return false
	removed.clear()
	placed.clear()
	for key in payload.get("removed", []):
		removed[str(key)] = true
	for block in payload.get("placed", []):
		if block is Dictionary:
			var cell := Vector2i(int(block.get("x", 0)), int(block.get("y", 0)))
			placed[cell_key(cell)] = int(block.get("tile", 1))
	# Regenerate from the saved seed first, then replay edits in stable chunk coordinates.
	seed_value = int(payload.get("seed", seed_value))
	for child in get_children():
		child.queue_free()
	ground = null
	backing = null
	await get_tree().process_frame
	build()
	var state: Dictionary = payload.get("player", {})
	if player != null:
		player.global_position = Vector2(float(state.get("x", player.global_position.x)), float(state.get("y", player.global_position.y)))
		player.health = int(state.get("health", 5))
		player.inventory = state.get("inventory", player.inventory)
		player.has_pickaxe = bool(state.get("has_pickaxe", false))
	if enemy != null and bool(payload.get("enemy_defeated", false)):
		enemy.set_meta("defeated", true)
		enemy.queue_free()
	return true
'''


PLAYER_GD = r'''extends CharacterBody2D

const SPEED := 185.0
const JUMP_SPEED := -360.0
const GRAVITY := 920.0

var world
var inventory: Dictionary = {"wood": 0, "stone": 0, "dirt": 10, "copper": 0, "crystal": 0}
var health := 5
var has_pickaxe := false
var notice := "Find a tree, mine four logs, then craft a wooden pickaxe."
var attack_cooldown := 0.0
var notice_time := 5.0
var sprite: Sprite2D

func _ready() -> void:
	add_to_group("player")
	world = get_parent().get_node("World")
	sprite = get_node("Sprite")
	var camera := Camera2D.new()
	camera.position_smoothing_enabled = true
	camera.position_smoothing_speed = 6.0
	camera.limit_left = 0
	camera.limit_top = 0
	camera.limit_right = world.world_width * 16
	camera.limit_bottom = 96 * 16
	add_child(camera)
	camera.make_current()

func _physics_process(delta: float) -> void:
	attack_cooldown = maxf(0.0, attack_cooldown - delta)
	notice_time = maxf(0.0, notice_time - delta)
	var direction := Input.get_axis("ui_left", "ui_right")
	if Input.is_key_pressed(KEY_A): direction -= 1.0
	if Input.is_key_pressed(KEY_D): direction += 1.0
	direction = clampf(direction, -1.0, 1.0)
	velocity.x = direction * SPEED
	if not is_on_floor():
		velocity.y += GRAVITY * delta
	elif Input.is_key_pressed(KEY_SPACE) or Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP):
		velocity.y = JUMP_SPEED
	if Input.is_key_pressed(KEY_J) and attack_cooldown <= 0.0:
		if world.attack_nearby(self):
			attack_cooldown = 0.42
	move_and_slide()
	if direction != 0.0:
		sprite.flip_h = direction < 0.0
		sprite.frame = 1 + (floori(float(Time.get_ticks_msec()) / 110.0) % 3) if absf(velocity.x) > 5 else 0
	else:
		sprite.frame = 0
	position.x = clampf(position.x, 12.0, world.world_width * 16.0 - 12.0)
	if position.y > 96.0 * 16.0:
		position = Vector2(10.0 * 16.0, (world.surface_at(10) - 2) * 16.0)
		velocity = Vector2.ZERO

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_LEFT:
			world.mine_at(get_global_mouse_position())
		elif event.button_index == MOUSE_BUTTON_RIGHT:
			world.place_at(get_global_mouse_position())

func set_notice(message: String) -> void:
	notice = message
	notice_time = 4.0

func take_damage(amount: int) -> void:
	health = maxi(0, health - amount)
	set_notice("The cave slime hit you. Find space, then strike with J.")
	if health <= 0:
		health = 5
		position = Vector2(10.0 * 16.0, (world.surface_at(10) - 2) * 16.0)
		velocity = Vector2.ZERO
		set_notice("You caught your breath and returned to the surface.")

func hud_notice() -> String:
	return notice if notice_time > 0.0 else ""
'''


SLIME_GD = r'''extends CharacterBody2D

const GRAVITY := 820.0
const WALK_SPEED := 54.0
var world
var player
var health := 4
var direction := -1.0
var bite_cooldown := 0.0
var sprite: Sprite2D

func _ready() -> void:
	world = get_parent().get_node("World")
	player = world.player
	sprite = get_node("Sprite")

func _physics_process(delta: float) -> void:
	if get_meta("defeated", false):
		return
	bite_cooldown = maxf(0.0, bite_cooldown - delta)
	if player != null and is_instance_valid(player) and absf(player.global_position.x - global_position.x) < 170.0:
		direction = signf(player.global_position.x - global_position.x)
	if not is_on_floor():
		velocity.y += GRAVITY * delta
	velocity.x = direction * WALK_SPEED
	move_and_slide()
	if is_on_wall():
		direction *= -1.0
	sprite.flip_h = direction > 0.0
	sprite.frame = floori(float(Time.get_ticks_msec()) / 340.0) % 2
	if player != null and is_instance_valid(player) and global_position.distance_to(player.global_position) < 27.0 and bite_cooldown <= 0.0:
		player.call("take_damage", 1)
		bite_cooldown = 1.1

func take_hit(damage: int) -> void:
	health -= damage
	if health <= 0:
		set_meta("defeated", true)
		world.save_game()
		queue_free()
'''


MAIN_GD = r'''extends Node2D

const WorldScript = preload("res://Scripts/world.gd")
const PlayerScript = preload("res://Scripts/player.gd")
const SlimeScript = preload("res://Scripts/slime.gd")

var spec: Dictionary = {}
var world
var player
var enemy
var hud_label: Label
var notice_label: Label
var craft_button: Button
var refresh_clock := 0.0
var save_clock := 0.0
var title_text := "Sandbox World"

func _ready() -> void:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://world-spec.json"))
	if parsed is Dictionary:
		spec = parsed
	title_text = str(spec.get("worldName", "Sandbox World"))
	add_sky()
	world = WorldScript.new()
	world.name = "World"
	world.configure(spec)
	add_child(world)
	world.build()
	player = make_actor()
	player.name = "Player"
	player.set_script(PlayerScript)
	add_child(player)
	world.player = player
	var start_x := 10
	player.global_position = Vector2(start_x * 16.0, world.surface_at(start_x) * 16.0 - 17.0)
	enemy = make_enemy()
	enemy.name = "CaveSlime"
	enemy.set_script(SlimeScript)
	add_child(enemy)
	world.enemy = enemy
	var slime_x := int(world.world_width * 0.68)
	enemy.global_position = world.enemy_floor_position(slime_x)
	make_hud()
	await world.load_game()
	refresh_hud()

func add_sky() -> void:
	var sky_layer := CanvasLayer.new()
	sky_layer.layer = -1
	add_child(sky_layer)
	var gradient := Gradient.new()
	var palette: Dictionary = spec.get("palette", {})
	gradient.set_color(0, Color(str(palette.get("sky_top", "#38566D"))))
	gradient.set_color(1, Color(str(palette.get("sky", "#85B8C5"))))
	var gradient_texture := GradientTexture2D.new()
	gradient_texture.gradient = gradient
	gradient_texture.width = 2
	gradient_texture.height = 256
	var sky := TextureRect.new()
	sky.texture = gradient_texture
	sky.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	sky.stretch_mode = TextureRect.STRETCH_SCALE
	sky.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	sky_layer.add_child(sky)

func make_actor() -> CharacterBody2D:
	var actor := CharacterBody2D.new()
	actor.collision_layer = 1
	actor.collision_mask = 1
	var collider := CollisionShape2D.new()
	var shape := CapsuleShape2D.new()
	shape.radius = 6.0
	shape.height = 24.0
	collider.shape = shape
	collider.position.y = -1.0
	actor.add_child(collider)
	var sprite := Sprite2D.new()
	sprite.name = "Sprite"
	sprite.texture = load("res://Art/player-sheet.png")
	sprite.hframes = 4
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sprite.position.y = -2.0
	actor.add_child(sprite)
	return actor

func make_enemy() -> CharacterBody2D:
	var actor := CharacterBody2D.new()
	actor.collision_layer = 2
	actor.collision_mask = 1
	var collider := CollisionShape2D.new()
	var shape := CapsuleShape2D.new()
	shape.radius = 7.0
	shape.height = 18.0
	collider.shape = shape
	actor.add_child(collider)
	var sprite := Sprite2D.new()
	sprite.name = "Sprite"
	sprite.texture = load("res://Art/slime-sheet.png")
	sprite.hframes = 2
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sprite.position.y = -4.0
	actor.add_child(sprite)
	return actor

func make_hud() -> void:
	var layer := CanvasLayer.new()
	layer.name = "HUD"
	add_child(layer)
	var panel := PanelContainer.new()
	panel.position = Vector2(12, 12)
	panel.custom_minimum_size = Vector2(360, 150)
	layer.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 3)
	panel.add_child(column)
	var heading := Label.new()
	heading.text = title_text + "  ·  SEED " + str(spec.get("seed", 4172026))
	heading.add_theme_font_size_override("font_size", 17)
	column.add_child(heading)
	var instruction := Label.new()
	instruction.text = "A/D move · Space jump · click mine · right-click place · J strike"
	instruction.add_theme_font_size_override("font_size", 11)
	column.add_child(instruction)
	hud_label = Label.new()
	hud_label.add_theme_font_size_override("font_size", 12)
	column.add_child(hud_label)
	notice_label = Label.new()
	notice_label.add_theme_color_override("font_color", Color("#cce797"))
	notice_label.add_theme_font_size_override("font_size", 11)
	column.add_child(notice_label)
	var buttons := HBoxContainer.new()
	column.add_child(buttons)
	craft_button = Button.new()
	craft_button.text = "Craft wooden pickaxe · 4 wood"
	craft_button.pressed.connect(_craft_pickaxe)
	buttons.add_child(craft_button)
	var save_button := Button.new()
	save_button.text = "Save"
	save_button.pressed.connect(_save_game)
	buttons.add_child(save_button)
	var load_button := Button.new()
	load_button.text = "Reload"
	load_button.pressed.connect(_load_game)
	buttons.add_child(load_button)

func _process(delta: float) -> void:
	refresh_clock += delta
	save_clock += delta
	if refresh_clock >= 0.2:
		refresh_clock = 0.0
		refresh_hud()
	if save_clock >= 3.0:
		save_clock = 0.0
		world.save_game()

func refresh_hud() -> void:
	if player == null or not is_instance_valid(player):
		return
	var inv: Dictionary = player.inventory
	var enemy_name := str(spec.get("enemyName", "Cave slime"))
	var enemy_state := "defeated" if enemy == null or not is_instance_valid(enemy) else "alive · %d hp" % int(enemy.get("health"))
	hud_label.text = "♥ %d/5    wood %d    stone %d    dirt %d    ore %d\n%s: %s    ·    chunks %d × %d tiles" % [
		player.health, inv.get("wood", 0), inv.get("stone", 0), inv.get("dirt", 0), inv.get("copper", 0),
		enemy_name, enemy_state, spec.get("chunks", 8), 32
	]
	notice_label.text = player.hud_notice()
	craft_button.disabled = player.has_pickaxe or int(inv.get("wood", 0)) < 4
	craft_button.text = "Wooden pickaxe crafted" if player.has_pickaxe else "Craft wooden pickaxe · 4 wood"

func _craft_pickaxe() -> void:
	world.craft_pickaxe()
	refresh_hud()

func _save_game() -> void:
	world.save_game()
	player.set_notice("World saved locally. Terrain edits and inventory will return on reload.")
	refresh_hud()

func _load_game() -> void:
	var loaded: bool = await world.load_game()
	player.set_notice("Save loaded." if loaded else "No save yet. Mine, place, or press Save first.")
	refresh_hud()
'''


def write_godot_project(root: Path, spec: dict, bc: dict, enemy_count: int,
                        enemy_behavior: str, starting_wood: int, starting_dirt: int,
                        gravity: float, jump_height: float, move_speed: float,
                        camera_zoom: float, save_interval: float) -> None:
    game = root / "sandbox-game"
    scripts = game / "Scripts"
    scenes = game / "Scenes"
    art = game / "Art"
    for folder in (scripts, scenes, art):
        folder.mkdir(parents=True, exist_ok=True)
    palette = spec["palette"]
    atlas = make_tile_atlas(palette, spec["seed"])
    player = make_player_sheet(palette)
    slime = make_slime_sheet(palette)
    write_png(art / "tiles.png", atlas)
    write_png(art / "player-sheet.png", player)
    write_png(art / "slime-sheet.png", slime)
    make_world_preview(root / "world-preview.png", palette, spec["seed"], spec["chunks"],
                       spec.get("biome", "temperate"), spec.get("chaos", 1.0))
    make_art_review(root / "art-review.png", atlas, player, slime, palette)
    print("Building Godot runtime and chunked terrain...", flush=True)
    (game / "world-spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n")

    eb = ENEMY_BEHAVIOR.get(enemy_behavior, ENEMY_BEHAVIOR["patrol"])

    def apply(template: str, replacements: dict[str, str]) -> str:
        for old, new in replacements.items():
            template = template.replace(old, new)
        return template

    world_repl = {
        "(x - 19 - (seed_value % 41)) % 47 == 0": f"(x - 19 - (seed_value % 41)) % {bc['tree_frequency']} == 0",
        "sin(float(x) * 0.045 + phase) * 3.0 + sin(float(x) * 0.12 + phase * 0.5) * 1.3":
        "sin(float(x) * 0.045 + phase) * %s + sin(float(x) * 0.12 + phase * 0.5) * %s" % (bc["surface_amplitude"], bc["surface_amplitude2"]),
        "return 8 + roundi(sin(float(x) * 0.071 + phase * 1.7) * 2.0)":
        "return %s + roundi(sin(float(x) * 0.071 + phase * 1.7) * %s)" % (bc["cave_radius_base"], bc["cave_amplitude"]),
    }
    player_repl = {
        "const SPEED := 185.0": "const SPEED := %s" % move_speed,
        "const JUMP_SPEED := -360.0": "const JUMP_SPEED := %s" % jump_height,
        "const GRAVITY := 920.0": "const GRAVITY := %s" % gravity,
        'var inventory: Dictionary = {"wood": 0, "stone": 0, "dirt": 10, "copper": 0, "crystal": 0}':
        'var inventory: Dictionary = {"wood": %d, "stone": 0, "dirt": %d, "copper": 0, "crystal": 0}' % (starting_wood, starting_dirt),
        "\tcamera.make_current()": "\tcamera.make_current()\n\tcamera.zoom = Vector2(%s, %s)" % (camera_zoom, camera_zoom),
    }
    slime_repl = {
        "const WALK_SPEED := 54.0": "const WALK_SPEED := %s" % eb["walk_speed"],
        "absf(player.global_position.x - global_position.x) < 170.0":
        "absf(player.global_position.x - global_position.x) < %s" % eb["chase_range"],
    }
    main_repl = {
        "save_clock >= 3.0:": "save_clock >= %s:" % save_interval,
        "\tenemy = make_enemy()\n\tenemy.name = \"CaveSlime\"\n\tenemy.set_script(SlimeScript)\n\tadd_child(enemy)\n\tworld.enemy = enemy\n\tvar slime_x := int(world.world_width * 0.68)\n\tenemy.global_position = world.enemy_floor_position(slime_x)":
        "\tvar enemy_count := %d\n" % enemy_count
        + "\tfor i in range(enemy_count):\n"
        + "\t\tvar slime = make_enemy()\n"
        + "\t\tslime.name = \"CaveSlime_\" + str(i)\n"
        + "\t\tslime.set_script(SlimeScript)\n"
        + "\t\tadd_child(slime)\n"
        + "\t\tvar slime_x := enemy_count == 1 ? int(world.world_width * 0.68) : int(world.world_width * (0.25 + 0.5 * i / (enemy_count - 1)))\n"
        + "\t\tslime.global_position = world.enemy_floor_position(slime_x)\n"
        + "\t\tif i == 0:\n"
        + "\t\t\tworld.enemy = slime\n",
    }
    (scripts / "world.gd").write_text(textwrap.dedent(apply(WORLD_GD, world_repl)).lstrip())
    (scripts / "player.gd").write_text(textwrap.dedent(apply(PLAYER_GD, player_repl)).lstrip())
    (scripts / "slime.gd").write_text(textwrap.dedent(apply(SLIME_GD, slime_repl)).lstrip())
    (scripts / "main.gd").write_text(textwrap.dedent(apply(MAIN_GD, main_repl)).lstrip())
    (scenes / "Main.tscn").write_text(
        '[gd_scene load_steps=2 format=3]\n\n'
        '[ext_resource type="Script" path="res://Scripts/main.gd" id="1_main"]\n\n'
        '[node name="Main" type="Node2D"]\nscript = ExtResource("1_main")\n'
    )
    game_title = " ".join(str(spec["worldName"]).split()).replace('"', "'").replace("\\", "/")
    project_godot = f'''config_version=5

[application]

config/name="{game_title}"
run/main_scene="res://Scenes/Main.tscn"
config/features=PackedStringArray("4.3", "GL Compatibility")

[display]

window/size/viewport_width=960
window/size/viewport_height=540
window/size/window_width_override=1280
window/size/window_height_override=720
window/stretch/mode="canvas_items"

[rendering]

renderer/rendering_method="gl_compatibility"
textures/default_filters/use_nearest_mipmap_filter=false
'''
    (game / "project.godot").write_text(project_godot)
    (game / "README.md").write_text(textwrap.dedent(f'''\
        # {game_title}

        A local Godot 4.3+ side-scrolling sandbox slice generated from the Vibe Create workbench.

        Open `project.godot` in Godot 4.3 or newer. The generated terrain is deterministic for seed `{spec['seed']}` and has {spec['chunks']} connected chunks of 32 tiles each. The runtime writes saves under `user://saves/{spec['projectId']}.json`.

        ## Controls

        - A/D or arrow keys: move
        - Space, W, or Up: jump
        - Left-click: mine a nearby block
        - Right-click: place a dirt block
        - J: strike the cave slime when close
        - Save / Reload buttons: persist or restore the local world

        Mine tree trunks for four wood, then craft a wooden pickaxe to mine stone and ore. Terrain edits auto-save. The project has no network dependencies.
    '''))


def write_pixel_review(root: Path, title: str, model: str, strictness: str = "standard") -> dict:
    output = root / "pixel-art-review.json"
    command = [sys.executable, str(Path(__file__).with_name("local_pixel_art_review.py")),
               str(root / "art-review.png"), title, str(output), "--model", model,
               "--strictness", strictness]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=195, check=False)
        if output.is_file():
            return json.loads(output.read_text())
        return {"status": "unavailable", "reviewer": f"ollama:{model}",
                "reason": (result.stderr or result.stdout or "The local vision review returned no report.")[-800:],
                "automatedChanges": False}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reviewer": f"ollama:{model}",
                "reason": f"{type(exc).__name__}: {exc}", "automatedChanges": False}


def generate(idea: str, title: str, out: Path, seed: int, chunks: int, model: str,
             vision_model: str, with_review: bool, palette_arg: str = "auto",
             difficulty: str = "normal", biome: str = "temperate",
             enemy_count: int = 2, enemy_behavior: str = "patrol",
             starting_wood: int = 4, starting_dirt: int = 10,
             gravity: float = 920.0, jump_height: float = -360.0,
             move_speed: float = 185.0, camera_zoom: float = 1.0,
             save_interval: float = 3.0, chaos: float = 1.0,
             review_strictness: str = "standard") -> None:
    out.mkdir(parents=True, exist_ok=True)
    palette_key, palette = choose_palette(idea)
    if palette_arg != "auto" and palette_arg in PALETTES:
        palette_key = palette_arg
        palette = PALETTES[palette_arg]
    bc = biome_constants(biome, chaos)
    print("Planning the world brief with the local model...", flush=True)
    planner_data, planner_source, planner_note = generate_local_content(idea, title, model)
    project_id = out.name
    enemy_name = planner_data.get("enemy", {}).get("name", "Cave Slime")
    hero_name = planner_data.get("player", {}).get("name", "Wayfarer")
    # Apply difficulty tuning to the planned encounter.
    enemy = planner_data.setdefault("enemy", {"name": "Cave Slime", "role": "cave dweller", "health": 4, "attack": 1})
    if difficulty == "easy":
        enemy["health"] = max(1, int(enemy.get("health", 4)) - 1)
        enemy["attack"] = max(1, int(enemy.get("attack", 1)) - 1)
    elif difficulty == "hard":
        enemy["health"] = min(10, int(enemy.get("health", 4)) + 1)
        enemy["attack"] = min(4, int(enemy.get("attack", 1)) + 1)
    world_spec = {
        "projectId": project_id,
        "worldName": title,
        "description": idea,
        "setting": planner_data.get("setting", "A seeded surface wilderness above a deep stone cave."),
        "heroName": hero_name,
        "enemyName": enemy_name,
        "seed": seed,
        "chunks": chunks,
        "chunkWidth": CHUNK_TILES,
        "worldHeight": WORLD_HEIGHT,
        "tileSize": TILE,
        "paletteName": palette["name"],
        "paletteKey": palette_key,
        "palette": palette,
        "biome": biome,
        "chaos": chaos,
        "difficulty": difficulty,
        "enemyCount": enemy_count,
        "enemyBehavior": enemy_behavior,
        "startingWood": starting_wood,
        "startingDirt": starting_dirt,
        "gravity": gravity,
        "jumpHeight": jump_height,
        "moveSpeed": move_speed,
        "cameraZoom": camera_zoom,
        "saveInterval": save_interval,
        "reviewStrictness": review_strictness,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    print("Generating 16px tile atlas, sprite sheets, and world preview...", flush=True)
    write_godot_project(out, world_spec, bc, enemy_count, enemy_behavior,
                        starting_wood, starting_dirt, gravity, jump_height,
                        move_speed, camera_zoom, save_interval)
    content = dict(planner_data)
    content.update({"theme": palette_key, "setting": world_spec["setting"], "seed": seed,
                    "chunks": chunks, "palette": palette, "runtime": "godot-sandbox"})
    (out / "game-content.json").write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n")
    (out / "world-spec.json").write_text(json.dumps(world_spec, ensure_ascii=False, indent=2) + "\n")
    (out / "idea.txt").write_text(idea.strip() + "\n")
    (out / "asset-style.json").write_text(json.dumps({
        "paletteName": palette["name"], "palette": palette, "tileSize": TILE,
        "spriteFrames": {"player": {"frameWidth": 24, "frameHeight": 32, "frames": 4},
                         "caveSlime": {"frameWidth": 24, "frameHeight": 24, "frames": 2}},
        "source": "Seeded local pixel-art renderer",
        "note": "All art uses the same bounded palette and pixel grid; edit the PNG sheets or palette manifest to art-direct the next pass."
    }, ensure_ascii=False, indent=2) + "\n")
    print("Pixel art review: running local vision..." if with_review else "Pixel art review: skipped by request", flush=True)
    review = write_pixel_review(out, title, vision_model, review_strictness) if with_review else {
        "status": "skipped", "automatedChanges": False, "reason": "Local visual review was disabled in the workbench."}
    (out / "pixel-art-review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n")

    assets = [
        {"id": "terrain-atlas", "kind": "tileset", "path": "sandbox-game/Art/tiles.png", "format": "png", "status": "generated"},
        {"id": "player-sheet", "kind": "sprite-animation", "path": "sandbox-game/Art/player-sheet.png", "format": "png", "status": "generated"},
        {"id": "slime-sheet", "kind": "sprite-animation", "path": "sandbox-game/Art/slime-sheet.png", "format": "png", "status": "generated"},
        {"id": "art-review", "kind": "review-sheet", "path": "art-review.png", "format": "png", "status": "generated"},
        {"id": "world-preview", "kind": "world-preview", "path": "world-preview.png", "format": "png", "status": "generated"},
    ]
    manifest = {
        "schemaVersion": "1.0",
        "project": {"id": project_id, "name": title, "description": idea,
                    "status": "in-progress", "target": {"engine": "Godot 4.3+", "runtime": "2D side-scrolling sandbox",
                    "assetFormats": ["godot", "png", "json"],
                    "constraints": ["Local execution only", "Fixed-seed terrain", "16px tiles", "Four connected chunks minimum"]},
                    "styleGuide": {"prompt": idea, "palette": [palette[key] for key in
                                                     ("sky_top", "sky", "grass", "grass_dark", "dirt", "dirt_light", "stone", "stone_light", "ore", "moss", "wood", "leaf", "cave", "crystal")],
                                   "paletteName": palette["name"], "notes": "All generated tile and sprite sheets use this shared bounded palette."}},
        "assets": assets,
        "stages": [
            {"id": "local-world-design", "kind": "brief", "status": "complete", "worker": {"name": planner_source, "execution": "local"}, "note": planner_note},
            {"id": "pixel-art", "kind": "asset-generation", "status": "complete", "outputs": assets, "worker": {"name": "Seeded local pixel-art renderer", "execution": "local"}},
            {"id": "godot-sandbox", "kind": "engine-project", "status": "complete", "outputs": [{"path": "sandbox-game/project.godot", "format": "godot"}], "worker": {"name": "generate_sandbox.py", "execution": "local"}},
            {"id": "pixel-art-review", "kind": "visual-review", "status": "complete" if review.get("status") == "reviewed" else review.get("status", "unavailable"), "outputs": [{"path": "pixel-art-review.json", "format": "json"}], "worker": {"name": review.get("reviewer", "local vision model"), "execution": "local"}, "automatedChanges": False},
        ],
        "deliverables": [{"id": "sandbox-slice", "name": "Seeded side-scrolling sandbox slice", "status": "generated",
                          "outputs": [{"path": "sandbox-game/project.godot", "format": "godot"},
                                      {"path": "world-preview.png", "format": "png"},
                                      {"path": "world-spec.json", "format": "json"}],
                          "acceptanceCriteria": ["Surface and cave are generated from a reproducible seed.",
                                                 "Chunks derive from global tile coordinates and meet at shared edges.",
                                                 "Move, jump, mine, place, craft one tool, encounter one enemy, and save or reload locally."]}],
        "metadata": {"generatedAt": datetime.now(timezone.utc).isoformat(), "generator": "scripts/generate_sandbox.py",
                     "localOnly": True, "contentPlanner": planner_source, "paletteName": palette["name"],
                     "visualReview": review, "runtime": "godot", "seed": seed, "chunks": chunks,
                     "notes": "The workbench renders the generated world and pixel-art sheets for review. Godot 4.3+ is required to launch the runtime project."}
    }
    (out / "project.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"Created Godot sandbox project: {out / 'sandbox-game' / 'project.godot'}")
    print(f"World: {chunks} chunks × {CHUNK_TILES} tiles, seed {seed}; palette {palette['name']}")
    print(f"Preview: {out / 'world-preview.png'}")
    print(f"Pixel art review: {review.get('status', 'unavailable')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("idea")
    parser.add_argument("--title", default="")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=4172026)
    parser.add_argument("--chunks", type=int, default=8)
    parser.add_argument("--model", default="qwen3.5:2b")
    parser.add_argument("--vision-model", default="qwen2.5vl:3b")
    parser.add_argument("--skip-vision-review", action="store_true")
    parser.add_argument("--palette", default="auto", choices=["auto", "verdant", "bog", "frost", "ember"],
                        help="Override the auto-detected world color theme")
    parser.add_argument("--difficulty", default="normal", choices=["easy", "normal", "hard"],
                        help="Adjust enemy strength: easy weakens, hard strengthens")
    parser.add_argument("--biome", default="temperate", choices=["temperate", "overgrown", "barren", "fractured"],
                        help="Terrain shape & density: hills, caves, trees")
    parser.add_argument("--enemy-count", type=int, default=2, choices=[1, 2, 3],
                        help="Number of cave slimes in the world")
    parser.add_argument("--enemy-behavior", default="patrol", choices=["patrol", "stationary", "aggressive"],
                        help="How the slime moves and chases")
    parser.add_argument("--starting-wood", type=int, default=4, choices=[0, 2, 4, 6, 8],
                        help="Logs the player begins with")
    parser.add_argument("--starting-dirt", type=int, default=10, choices=[0, 5, 10, 15, 20],
                        help="Dirt blocks the player begins with")
    parser.add_argument("--gravity", type=float, default=920.0, choices=[600.0, 920.0, 1200.0],
                        help="Gravity pull strength")
    parser.add_argument("--jump-height", type=float, default=-360.0, choices=[-280.0, -360.0, -440.0],
                        help="Jump impulse (negative = upward)")
    parser.add_argument("--move-speed", type=float, default=185.0, choices=[120.0, 185.0, 260.0],
                        help="Player movement speed")
    parser.add_argument("--camera-zoom", type=float, default=1.0, choices=[0.5, 1.0, 1.5],
                        help="Camera zoom: 0.5 wide, 1.5 close-up")
    parser.add_argument("--save-interval", type=float, default=3.0, choices=[1.0, 3.0, 5.0, 10.0],
                        help="Auto-save every N seconds")
    parser.add_argument("--chaos", type=float, default=1.0, choices=[0.0, 1.0, 2.0],
                        help="Terrain perturbation amplitude multiplier")
    parser.add_argument("--review-strictness", default="standard", choices=["lenient", "standard", "strict"],
                        help="How strictly the local vision review judges art")
    args = parser.parse_args()
    if not 0 <= args.seed <= 2**31 - 1:
        parser.error("Seed must be between 0 and 2147483647.")
    if not 4 <= args.chunks <= 16:
        parser.error("Chunk count must be between 4 and 16.")
    title = args.title.strip() or " ".join(args.idea.split()[:5]).strip(".,!?;:") or "Sandbox World"
    generate(args.idea, title, args.out, args.seed, args.chunks, args.model,
             args.vision_model, not args.skip_vision_review, palette_arg=args.palette, difficulty=args.difficulty,
             biome=args.biome, enemy_count=args.enemy_count, enemy_behavior=args.enemy_behavior,
             starting_wood=args.starting_wood, starting_dirt=args.starting_dirt,
             gravity=args.gravity, jump_height=args.jump_height, move_speed=args.move_speed,
             camera_zoom=args.camera_zoom, save_interval=args.save_interval, chaos=args.chaos,
             review_strictness=args.review_strictness)


if __name__ == "__main__":
    main()
