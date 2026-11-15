#!/usr/bin/env python3
"""Build a web-installable PWA package for a completed Vibe Create project.

Outputs, inside <project>/web-export/:
  index.html          the playable game shell (copied quest HTML, or generated HTML5 sandbox)
  manifest.json       PWA manifest for "install to home screen" on any device
  service-worker.js   offline-first cache of the shell and game assets
  icon-192.png / icon-512.png  PWA icons derived from the project preview art
  README.md           install instructions for phone, tablet, and desktop

Pure Python standard library: no network, no Pillow, no external tools.
"""

from __future__ import annotations

import json
import shutil
import struct
import zlib
from pathlib import Path

PNG_SIG = b"\x89PNG\r\n\x1a\n"

# Image formats we treat as precachable game assets.
ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".json", ".txt", ".md"}


# ---------------------------------------------------------------------------
# Minimal PNG read / write / resize (RGBA, bit depth 8) -- stdlib only.
# ---------------------------------------------------------------------------

def _chunk(kind: bytes, content: bytes) -> bytes:
    payload = kind + content
    return struct.pack(">I", len(content)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)


def read_png(path: Path) -> tuple[bytes, int, int]:
    """Return (rgba_bytes, width, height) for a PNG (color type 2 or 6, depth 8)."""
    data = Path(path).read_bytes()
    if data[:8] != PNG_SIG:
        raise ValueError(f"{path} is not a PNG")
    pos = 8
    width = height = bit_depth = color_type = None
    idat = bytearray()
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        content = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _comp, _filt, _inter = struct.unpack(">IIBBBBB", content)
        elif kind == b"IDAT":
            idat.extend(content)
        elif kind == b"IEND":
            break
    if width is None or height is None:
        raise ValueError(f"{path} has no IHDR chunk")
    raw = zlib.decompress(bytes(idat))
    return _unfilter(raw, width, height, bit_depth, color_type), width, height


def _unfilter(raw: bytes, w: int, h: int, bit_depth: int, color_type: int) -> bytes:
    if bit_depth != 8 or color_type not in (2, 6):
        raise ValueError(f"unsupported PNG: bit_depth={bit_depth} color_type={color_type}")
    bpp = 3 if color_type == 2 else 4
    stride = w * bpp
    out = bytearray(h * stride)
    pos = 0
    prev = bytearray(stride)
    for y in range(h):
        f = raw[pos]
        pos += 1
        line = raw[pos:pos + stride]
        pos += stride
        cur = bytearray(line)
        if f == 1:  # Sub
            for i in range(bpp, stride):
                cur[i] = (cur[i] + cur[i - bpp]) & 0xFF
        elif f == 2:  # Up
            for i in range(stride):
                cur[i] = (cur[i] + prev[i]) & 0xFF
        elif f == 3:  # Average
            for i in range(stride):
                a = cur[i - bpp] if i >= bpp else 0
                cur[i] = (cur[i] + ((a + prev[i]) // 2)) & 0xFF
        elif f == 4:  # Paeth
            for i in range(stride):
                a = cur[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                cur[i] = (cur[i] + pr) & 0xFF
        out[y * stride:(y + 1) * stride] = cur
        prev = cur
    return bytes(out)


def write_png(path: Path, width: int, height: int, rgba: bytes) -> None:
    path = Path(path)
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


def resize_nearest(rgba: bytes, src_w: int, src_h: int, dst_w: int, dst_h: int) -> bytes:
    out = bytearray(dst_w * dst_h * 4)
    for dy in range(dst_h):
        sy = min(src_h - 1, dy * src_h // dst_h)
        src_row = sy * src_w * 4
        dst_row = dy * dst_w * 4
        for dx in range(dst_w):
            sx = min(src_w - 1, dx * src_w // dst_w)
            src = src_row + sx * 4
            dst = dst_row + dx * 4
            out[dst:dst + 4] = rgba[src:src + 4]
    return bytes(out)


def make_icons(src_png: Path, out_dir: Path) -> list[str]:
    """Derive 192x192 and 512x512 PWA icons from the project preview art."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rgba, w, h = read_png(src_png)
    produced = []
    for size in (192, 512):
        data = resize_nearest(rgba, w, h, size, size)
        out_path = out_dir / f"icon-{size}.png"
        write_png(out_path, size, size, data)
        produced.append(f"icon-{size}.png")
    return produced


# ---------------------------------------------------------------------------
# PWA files
# ---------------------------------------------------------------------------

def make_manifest(project_id: str, name: str, description: str, theme_color: str, out_dir: Path) -> str:
    manifest = {
        "name": name,
        "short_name": name[:12],
        "start_url": "./index.html",
        "display": "standalone",
        "orientation": "any",
        "background_color": theme_color,
        "theme_color": theme_color,
        "description": description,
        "lang": "en",
        "icons": [
            {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }
    out_path = out_dir / "manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return "manifest.json"


def make_service_worker(out_dir: Path, precache: list[str]) -> str:
    assets_js = json.dumps(precache, ensure_ascii=False)
    sw = f"""// Vibe Create offline service worker
const CACHE_NAME = "vibe-create-game-v1";
const PRECACHE = {assets_js};

self.addEventListener("install", event => {{
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE))
  );
  self.skipWaiting();
}});

self.addEventListener("activate", event => {{
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
}});

self.addEventListener("fetch", event => {{
  const url = new URL(event.request.url);
  if (url.origin !== location.origin) return;
  event.respondWith(
    caches.match(event.request).then(cached =>
      cached || fetch(event.request).then(response => {{
        if (response.ok && event.request.method === "GET") {{
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
        }}
        return response;
      }})
    )
  );
}});
"""
    out_path = out_dir / "service-worker.js"
    out_path.write_text(sw, encoding="utf-8")
    return "service-worker.js"


README_TEMPLATE = """# {name}

A Vibe Create game, ready to play in any web browser — no install of Godot or
any engine required. This folder is a complete, offline-first web app.

## Play right now

Open `index.html` in a browser. The game runs entirely offline.

## Install to your device (app-like)

This game is a Progressive Web App. "Installing" it adds it to your home screen
or applications list so it opens like a native app, works offline, and has no
browser address bar.

### iPhone / iPad (Safari)
1. Open `index.html` in Safari.
2. Tap the Share button (square with an arrow).
3. Scroll down and tap **Add to Home Screen**.
4. Tap **Add**. The game appears on your home screen.

### Android (Chrome)
1. Open `index.html` in Chrome.
2. Tap the menu (⋮) → **Add to Home screen**.
3. Tap **Add**.

### Desktop (Chrome / Edge)
1. Open `index.html`.
2. Click the install icon in the address bar, or menu → **Install this site as an app**.

## What's inside

- `index.html` — the complete playable game (HTML, CSS, JavaScript, all game data).
- `manifest.json` — PWA manifest used by browsers to install the app.
- `service-worker.js` — caches the game so it works offline.
- `icon-192.png` / `icon-512.png` — home-screen icons.
- `game-content.json` / `world-spec.json` — the generated world and encounter data.

This folder contains everything. Copy it to any device, unzip, and open
`index.html`. No network connection, account, or external service is needed.

Generated locally by Vibe Create — {project_id}
"""


def make_readme(project_id: str, name: str, out_dir: Path) -> str:
    out_path = out_dir / "README.md"
    out_path.write_text(README_TEMPLATE.format(name=name, project_id=project_id), encoding="utf-8")
    return "README.md"


# ---------------------------------------------------------------------------
# Main export
# ---------------------------------------------------------------------------

def _pick_preview_art(project_dir: Path) -> Path | None:
    """Find the best preview image to derive icons from."""
    candidates = [
        project_dir / "world-preview.png",
        project_dir / "blender-concept" / "concept.png",
        project_dir / "art-review.png",
        project_dir / "sandbox-game" / "Art" / "tiles.png",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _collect_game_assets(project_dir: Path, runtime: str, web_index_name: str) -> list[str]:
    """List relative asset paths the game HTML references, for precaching."""
    assets = [web_index_name, "manifest.json", "service-worker.js"]
    if runtime == "godot":
        art = project_dir / "sandbox-game" / "Art"
        for name in ("tiles.png", "player-sheet.png", "slime-sheet.png"):
            if (art / name).is_file():
                assets.append(f"sandbox-game/Art/{name}")
        if (project_dir / "world-preview.png").is_file():
            assets.append("world-preview.png")
        if (project_dir / "world-spec.json").is_file():
            assets.append("world-spec.json")
        if (project_dir / "game-content.json").is_file():
            assets.append("game-content.json")
    else:
        # Browser/quest prototype: index.html references blender-concept renders.
        if (project_dir / "game-content.json").is_file():
            assets.append("game-content.json")
        if (project_dir / "project.json").is_file():
            assets.append("project.json")
        concept = project_dir / "blender-concept" / "concept.png"
        closeup = project_dir / "blender-concept" / "character-closeup.png"
        if concept.is_file():
            assets.append("blender-concept/concept.png")
        if closeup.is_file():
            assets.append("blender-concept/character-closeup.png")
    # Deduplicate, preserve order.
    seen = set()
    result = []
    for a in assets:
        if a not in seen:
            seen.add(a)
            result.append(a)
    return result


def export_web_project(project_dir: Path) -> dict:
    """Create a web-installable PWA package under <project>/web-export/.

    Returns a dict describing what was produced.
    """
    project_dir = Path(project_dir)
    manifest_path = project_dir / "project.json"
    content_path = project_dir / "game-content.json"
    if not manifest_path.is_file() or not content_path.is_file():
        raise FileNotFoundError(f"{project_dir} is not a completed Vibe Create project")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    content = json.loads(content_path.read_text(encoding="utf-8"))
    project_block = manifest.get("project", {})
    name = project_block.get("name", project_dir.name)
    description = project_block.get("description", content.get("setting", ""))
    runtime = manifest.get("metadata", {}).get("runtime", "browser")
    palette_name = manifest.get("metadata", {}).get("paletteName", "")
    # Theme color from palette sky or a default.
    theme_color = "#10151f"
    if runtime == "godot" and "palette" in content:
        theme_color = content["palette"].get("sky_top", "#10151f")
    elif "theme" in content:
        theme_color = {"sky-dragon": "#38566D", "dark-fantasy": "#2a302e", "adventure": "#344039"}.get(
            content["theme"], "#10151f")

    web_root = project_dir / "web-export"
    web_root.mkdir(parents=True, exist_ok=True)

    # --- Determine the playable index.html --------------------------------
    if runtime == "godot":
        # Generate an HTML5 canvas sandbox so the Godot slice plays in-browser.
        from web_sandbox_export import generate_html
        spec_path = project_dir / "world-spec.json"
        if spec_path.is_file():
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            html = generate_html(spec)
            (web_root / "index.html").write_text(html, encoding="utf-8")
        else:
            raise FileNotFoundError("Godot project is missing world-spec.json; cannot build web sandbox")
        web_index = "index.html"
    else:
        # Quest browser prototype: copy the existing offline index.html.
        src_index = project_dir / "index.html"
        if not src_index.is_file():
            raise FileNotFoundError(f"{project_dir} has no playable index.html")
        shutil.copy2(src_index, web_root / "index.html")
        web_index = "index.html"

    # --- Icons from preview art ------------------------------------------
    preview = _pick_preview_art(project_dir)
    icon_files = []
    if preview is not None:
        icon_files = make_icons(preview, web_root)

    # --- PWA files --------------------------------------------------------
    make_manifest(project_dir.name, name, description, theme_color, web_root)
    precache = _collect_game_assets(project_dir, runtime, web_index)
    make_service_worker(web_root, precache)
    make_readme(project_dir.name, name, web_root)

    # --- Copy supporting asset files into web-export ----------------------
    copied = []
    if runtime == "godot":
        art = project_dir / "sandbox-game" / "Art"
        for name_file in ("tiles.png", "player-sheet.png", "slime-sheet.png"):
            src = art / name_file
            if src.is_file():
                dst = web_root / f"sandbox-game/Art/{name_file}"
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied.append(f"sandbox-game/Art/{name_file}")
        for name_file in ("world-preview.png", "world-spec.json", "game-content.json"):
            src = project_dir / name_file
            if src.is_file():
                shutil.copy2(src, web_root / name_file)
                copied.append(name_file)
    else:
        for name_file in ("game-content.json", "project.json"):
            src = project_dir / name_file
            if src.is_file():
                shutil.copy2(src, web_root / name_file)
                copied.append(name_file)
        blender = project_dir / "blender-concept"
        for name_file in ("concept.png", "character-closeup.png"):
            src = blender / name_file
            if src.is_file():
                dst = web_root / f"blender-concept/{name_file}"
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied.append(f"blender-concept/{name_file}")

    return {
        "web_root": str(web_root.resolve()),
        "index": web_index,
        "icons": icon_files,
        "assets": copied,
        "runtime": runtime,
        "name": name,
    }
