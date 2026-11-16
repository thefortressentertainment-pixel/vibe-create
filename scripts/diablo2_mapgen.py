#!/usr/bin/env python3
"""Diablo-style random map generator.

Produces tile-based dungeon and town maps with:
  - Rooms of varying sizes connected by corridors
  - Stairs up/down, waypoints, chests, object spawners
  - Monster spawn zones keyed to area difficulty
  - A* pathfinding grid for collision/navigation

Pure Python standard library.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

TILE = 32  # pixel size of one map tile (isometric grid cell)

# Tile kinds
VOID = -1
FLOOR = 0
WALL = 1
DOOR = 2
STAIRS_DOWN = 3
STAIRS_UP = 4
WAYPOINT = 5
CHEST = 6
OBJECT = 7
WATER = 8
GRASS = 9


class MapGen:
    def __init__(self, width: int, height: int, seed: int | None = None,
                 area_kind: str = "dungeon") -> None:
        self.rng = random.Random(seed)
        self.width = width
        self.height = height
        self.area_kind = area_kind
        # Grid: tile kind per cell
        self.grid: list[list[int]] = [[VOID for _ in range(width)] for _ in range(height)]
        self.walkable: list[list[bool]] = [[False for _ in range(width)] for _ in range(height)]
        self.rooms: list[dict] = []
        self.entities: list[dict] = []
        self.start_x = 0
        self.start_y = 0

    # ------------------------------------------------------------------
    # Room / corridor carving
    # ------------------------------------------------------------------
    def _intersects(self, x1: int, y1: int, x2: int, y2: int, pad: int = 2) -> bool:
        for r in self.rooms:
            if not (x2 + pad < r["x1"] - pad or x1 - pad > r["x2"] + pad or
                    y2 + pad < r["y1"] - pad or y1 - pad > r["y2"] + pad):
                return True
        return False

    def _carve_room(self, x1: int, y1: int, x2: int, y2: int, floor_tile: int) -> None:
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                if 0 <= y < self.height and 0 <= x < self.width:
                    self.grid[y][x] = floor_tile
        # Walls around the room
        for y in range(max(0, y1 - 1), min(self.height, y2 + 2)):
            for x in range(max(0, x1 - 1), min(self.width, x2 + 2)):
                if self.grid[y][x] == VOID:
                    self.grid[y][x] = WALL

    def _carve_corridor(self, x1: int, y1: int, x2: int, y2: int) -> None:
        if self.rng.random() < 0.5:
            # Horizontal then vertical
            sx = min(x1, x2); ex = max(x1, x2)
            sy = min(y1, y2); ey = max(y1, y2)
            for x in range(sx, ex + 1):
                if 0 <= y1 < self.height:
                    self.grid[y1][x] = FLOOR
            for y in range(sy, ey + 1):
                if 0 <= y < self.height and 0 <= x2 < self.width:
                    self.grid[y][x2] = FLOOR
        else:
            # Vertical then horizontal
            sy = min(y1, y2); ey = max(y1, y2)
            sx = min(x1, x2); ex = max(x1, x2)
            for y in range(sy, ey + 1):
                if 0 <= y < self.height and 0 <= x1 < self.width:
                    self.grid[y][x1] = FLOOR
            for x in range(sx, ex + 1):
                if 0 <= y2 < self.height:
                    self.grid[y2][x] = FLOOR

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def generate(self, min_rooms: int = 4, max_rooms: int = 10,
                 min_size: int = 4, max_size: int = 9) -> None:
        floor_tile = GRASS if self.area_kind == "outdoor" else FLOOR

        # Carve rooms
        for _ in range(max_rooms * 4):
            if len(self.rooms) >= max_rooms:
                break
            w = self.rng.randint(min_size, max_size)
            h = self.rng.randint(min_size, max_size)
            x = self.rng.randint(1, self.width - w - 2)
            y = self.rng.randint(1, self.height - h - 2)
            if self._intersects(x, y, x + w, y + h):
                continue
            self._carve_room(x, y, x + w - 1, y + h - 1, floor_tile)
            self.rooms.append({"x1": x, "y1": y, "x2": x + w - 1, "y2": y + h - 1})

        # Connect rooms with corridors
        for i in range(1, len(self.rooms)):
            prev = self.rooms[i - 1]
            cur = self.rooms[i]
            px = (prev["x1"] + prev["x2"]) // 2
            py = (prev["y1"] + prev["y2"]) // 2
            cx = (cur["x1"] + cur["x2"]) // 2
            cy = (cur["y1"] + cur["y2"]) // 2
            self._carve_corridor(px, py, cx, cy)

        # If no rooms were carved (edge case), carve one big room
        if not self.rooms:
            self._carve_room(2, 2, self.width - 3, self.height - 3, floor_tile)
            self.rooms.append({"x1": 2, "y1": 2, "x2": self.width - 3, "y2": self.height - 3})

        # Compute walkable grid
        for y in range(self.height):
            for x in range(self.width):
                self.walkable[y][x] = self.grid[y][x] in {FLOOR, GRASS, DOOR, WAYPOINT, CHEST, OBJECT}

        # Place start position in first room
        first = self.rooms[0]
        self.start_x = (first["x1"] + first["x2"]) // 2 * TILE + TILE // 2
        self.start_y = (first["y1"] + first["y2"]) // 2 * TILE + TILE // 2

        # Place entities
        self._place_stairs()
        self._place_waypoint()
        self._place_chests()
        self._place_objects()
        self._place_monsters(min_rooms)

    def _place_stairs(self) -> None:
        if len(self.rooms) < 2:
            return
        # Stairs down in last room
        last = self.rooms[-1]
        sx = self.rng.randint(last["x1"], last["x2"])
        sy = self.rng.randint(last["y1"], last["y2"])
        self.grid[sy][sx] = STAIRS_DOWN
        self.entities.append({
            "kind": "stairs_down",
            "x": sx * TILE + TILE // 2,
            "y": sy * TILE + TILE // 2,
            "tile_x": sx, "tile_y": sy,
            "label": "Stairs Down",
        })
        # Stairs up in first room (unless town)
        first = self.rooms[0]
        ux = self.rng.randint(first["x1"], first["x2"])
        uy = self.rng.randint(first["y1"], first["y2"])
        if self.grid[uy][ux] != STAIRS_DOWN:
            self.grid[uy][ux] = STAIRS_UP
            self.entities.append({
                "kind": "stairs_up",
                "x": ux * TILE + TILE // 2,
                "y": uy * TILE + TILE // 2,
                "tile_x": ux, "tile_y": uy,
                "label": "Stairs Up",
            })

    def _place_waypoint(self) -> None:
        # Waypoints are usually outside in town/outdoor, occasionally in dungeons near start
        room = self.rng.choice(self.rooms)
        wx = self.rng.randint(room["x1"], room["x2"])
        wy = self.rng.randint(room["y1"], room["y2"])
        self.grid[wy][wx] = WAYPOINT
        self.entities.append({
            "kind": "waypoint",
            "x": wx * TILE + TILE // 2,
            "y": wy * TILE + TILE // 2,
            "tile_x": wx, "tile_y": wy,
            "label": "Waypoint",
        })

    def _place_chests(self) -> None:
        count = self.rng.randint(0, 3)
        for _ in range(count):
            room = self.rng.choice(self.rooms)
            cx = self.rng.randint(room["x1"], room["x2"])
            cy = self.rng.randint(room["y1"], room["y2"])
            if self.grid[cy][cx] not in {STAIRS_UP, STAIRS_DOWN, WAYPOINT}:
                self.grid[cy][cx] = CHEST
                self.entities.append({
                    "kind": "chest",
                    "x": cx * TILE + TILE // 2,
                    "y": cy * TILE + TILE // 2,
                    "tile_x": cx, "tile_y": cy,
                    "label": "Chest",
                    "locked": self.rng.random() < 0.3,
                })

    def _place_objects(self) -> None:
        """Breakable objects: barrels, corpses, shrines."""
        kinds = ["barrel", "corpse", "shrine", "well"]
        count = self.rng.randint(1, 5)
        for _ in range(count):
            room = self.rng.choice(self.rooms)
            ox = self.rng.randint(room["x1"], room["x2"])
            oy = self.rng.randint(room["y1"], room["y2"])
            if self.grid[oy][ox] in {FLOOR, GRASS}:
                self.grid[oy][ox] = OBJECT
                self.entities.append({
                    "kind": self.rng.choice(kinds),
                    "x": ox * TILE + TILE // 2,
                    "y": oy * TILE + TILE // 2,
                    "tile_x": ox, "tile_y": oy,
                    "label": self.rng.choice(kinds).title(),
                    "breakable": True,
                })

    def _place_monsters(self, min_rooms: int) -> None:
        """Spawn monster groups in rooms based on area kind."""
        base_count = {"town": 0, "outdoor": 2, "dungeon": 3}.get(self.area_kind, 2)
        monster_ids = {
            "town": [],
            "outdoor": ["fallen", "carver"],
            "dungeon": ["skeleton", "zombie", "soul_slasher"],
        }.get(self.area_kind, ["fallen"])
        for room in self.rooms:
            count = self.rng.randint(1, base_count) if base_count > 0 else 0
            for _ in range(count):
                mx = self.rng.randint(room["x1"], room["x2"])
                my = self.rng.randint(room["y1"], room["y2"])
                if self.grid[my][mx] in {FLOOR, GRASS}:
                    self.entities.append({
                        "kind": "monster",
                        "monster_id": self.rng.choice(monster_ids),
                        "x": mx * TILE + TILE // 2,
                        "y": my * TILE + TILE // 2,
                        "tile_x": mx, "tile_y": my,
                        "label": "Monster",
                        "alive": True,
                    })

    # ------------------------------------------------------------------
    # Pathfinding (A*)
    # ------------------------------------------------------------------
    def find_path(self, start_x: int, start_y: int, goal_x: int, goal_y: int) -> list[tuple[int, int]]:
        """Return list of (x, y) tile coords from start to goal, or empty."""
        import heapq
        start = (start_x // TILE, start_y // TILE)
        goal = (goal_x // TILE, goal_y // TILE)
        if not (0 <= start[0] < self.width and 0 <= start[1] < self.height):
            return []
        if not (0 <= goal[0] < self.width and 0 <= goal[1] < self.height):
            return []
        if not self.walkable[goal[1]][goal[0]]:
            return []

        open_set = [(0, start)]
        came_from: dict[tuple[int, int], Optional[tuple[int, int]]] = {}
        g_score = {start: 0}
        closed = set()

        while open_set:
            _, current = heapq.heappop(open_set)
            if current in closed:
                continue
            if current == goal:
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return path
            closed.add(current)
            cx, cy = current
            for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1),
                           (cx - 1, cy - 1), (cx + 1, cy - 1), (cx - 1, cy + 1), (cx + 1, cy + 1)):
                if not (0 <= nx < self.width and 0 <= ny < self.height):
                    continue
                if not self.walkable[ny][nx]:
                    continue
                if (nx, ny) in closed:
                    continue
                tentative_g = g_score[current] + (1.414 if nx != cx and ny != cy else 1.0)
                if tentative_g < g_score.get((nx, ny), float("inf")):
                    came_from[(nx, ny)] = current
                    g_score[(nx, ny)] = tentative_g
                    f = tentative_g + abs(nx - goal[0]) + abs(ny - goal[1])
                    heapq.heappush(open_set, (f, (nx, ny)))
        return []

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "tile": TILE,
            "area_kind": self.area_kind,
            "grid": self.grid,
            "entities": self.entities,
            "start_x": self.start_x,
            "start_y": self.start_y,
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n")
