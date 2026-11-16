#!/usr/bin/env python3
"""Serve the local Vibe Create workbench and run local generation jobs."""

from __future__ import annotations

import argparse
import io
import json
import mimetypes
import os
import signal
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from pwa_export import export_web_project


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
PROJECTS_ROOT = ROOT / "projects"
GENERATOR = ROOT / "scripts" / "idea_to_game.py"
SANDBOX_GENERATOR = ROOT / "scripts" / "generate_sandbox.py"
DARK_FANTASY_GENERATOR = ROOT / "scripts" / "generate_dark_fantasy.py"
DEFAULT_BLENDER = Path("/Applications/Blender.app/Contents/MacOS/Blender")
OLLAMA_TAGS = "http://127.0.0.1:11434/api/tags"
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
GENERATION_STARTING = False


def within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def local_models() -> dict:
    models: list[str] = []
    running = False
    try:
        request = urllib.request.Request(OLLAMA_TAGS, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=2) as response:
            data = json.loads(response.read())
        models = [item.get("name", "") for item in data.get("models", []) if item.get("name")]
        running = True
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        pass
    if not models and shutil.which("ollama"):
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5, check=False)
            models = [line.split()[0] for line in result.stdout.splitlines()[1:] if line.split()]
        except (OSError, subprocess.TimeoutExpired):
            pass
    planner = "qwen3.5:2b" if "qwen3.5:2b" in models else next((m for m in models if "embed" not in m), "qwen3.5:2b")
    vision = "qwen2.5vl:3b" if "qwen2.5vl:3b" in models else next((m for m in models if "vl" in m.lower()), "qwen2.5vl:3b")
    return {"running": running, "models": models, "planner": planner, "vision": vision}


def godot_executable() -> Path | None:
    candidates = [os.environ.get("VIBE_GODOT_BIN", ""), os.environ.get("GODOT_BIN", ""),
                 shutil.which("godot"), shutil.which("godot4"),
                 "/Applications/Godot.app/Contents/MacOS/Godot",
                 str(Path.home() / "Applications/Godot.app/Contents/MacOS/Godot")]
    for value in candidates:
        if not value:
            continue
        path = Path(value).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return path.resolve()
    return None


def project_summary(folder: Path) -> dict | None:
    manifest_path = folder / "project.json"
    content_path = folder / "game-content.json"
    browser_game = folder / "index.html"
    godot_project = folder / "sandbox-game" / "project.godot"
    if not manifest_path.is_file() or not content_path.is_file() or not (browser_game.is_file() or godot_project.is_file()):
        return None
    try:
        manifest = json.loads(manifest_path.read_text())
        content = json.loads(content_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    project = manifest.get("project", {})
    review = manifest.get("metadata", {}).get("visualReview", {})
    target_engine = project.get("target", {}).get("engine", "")
    if godot_project.is_file():
        runtime = "godot"
    elif target_engine == "browser-dark-fantasy":
        runtime = "browser-dark-fantasy"
    else:
        runtime = "browser"
    files = {
        name: path.is_file()
        for name, path in {
            "game": godot_project if runtime == "godot" else browser_game,
            "godot": godot_project,
            "art": folder / "art-review.png",
            "atlas": folder / "sandbox-game" / "Art" / "tiles.png",
            "playerSheet": folder / "sandbox-game" / "Art" / "player-sheet.png",
            "slimeSheet": folder / "sandbox-game" / "Art" / "slime-sheet.png",
            "worldPreview": folder / "world-preview.png",
            "pixelReview": folder / "pixel-art-review.json",
            "blend": folder / "blender-concept" / "concept.blend",
            "fbx": folder / "blender-concept" / "concept.fbx",
            "render": folder / "blender-concept" / "concept.png",
            "closeup": folder / "blender-concept" / "character-closeup.png",
            "review": folder / "vision-review.json",
        }.items()
    }
    try:
        created = datetime.fromtimestamp(folder.stat().st_mtime).astimezone().isoformat(timespec="minutes")
    except OSError:
        created = ""
    return {
        "id": folder.name,
        "name": project.get("name", folder.name),
        "description": project.get("description", ""),
        "theme": content.get("theme", "adventure"),
        "setting": content.get("setting", ""),
        "runtime": runtime,
        "seed": content.get("seed"),
        "chunks": content.get("chunks"),
        "paletteName": manifest.get("metadata", {}).get("paletteName", ""),
        "planner": manifest.get("metadata", {}).get("contentPlanner", "local fallback"),
        "created": created,
        "files": files,
        "review": review,
        "integration": manifest.get("metadata", {}).get("targetIntegration"),
        "stages": [{"id": stage.get("id"), "status": stage.get("status")}
                   for stage in manifest.get("stages", [])],
        "folder": str(folder.resolve()),
        "url": f"/project/{folder.name}/index.html" if runtime == "browser" else "",
        "renderUrl": (f"/project/{folder.name}/world-preview.png" if files["worldPreview"]
                      else f"/project/{folder.name}/blender-concept/concept.png" if files["render"] else ""),
        "artUrl": f"/project/{folder.name}/art-review.png" if files["art"] else "",
        "closeupUrl": f"/project/{folder.name}/blender-concept/character-closeup.png" if files["closeup"] else "",
        "webReady": (folder / "web-export" / "index.html").is_file(),
    }


def list_projects() -> list[dict]:
    if not PROJECTS_ROOT.is_dir():
        return []
    result = [summary for item in PROJECTS_ROOT.iterdir() if item.is_dir()
              if (summary := project_summary(item)) is not None]
    return sorted(result, key=lambda item: item["created"], reverse=True)


def job_snapshot(job: dict) -> dict:
    log_path: Path = job["log_path"]
    try:
        with log_path.open("rb") as stream:
            stream.seek(max(0, log_path.stat().st_size - 12000))
            log = stream.read().decode("utf-8", errors="replace")
    except OSError:
        log = ""
    lower_log = log.lower()
    if job["status"] in {"complete", "complete_with_warnings", "failed", "cancelled"}:
        phase = job["status"]
    elif "pixel art review:" in lower_log or "local visual review:" in lower_log:
        phase = "review"
    elif "building godot runtime" in lower_log:
        phase = "engine"
    elif "created godot sandbox project:" in lower_log:
        phase = "engine"
    elif "generating tile atlas" in lower_log:
        phase = "assets"
    elif "building the local low-poly blender" in lower_log:
        phase = "blender"
    elif "created " in lower_log and "index.html" in lower_log:
        phase = "browser"
    else:
        phase = "planning"
    return {
        "id": job["id"], "status": job["status"], "phase": phase,
        "projectId": job["project_id"], "projectName": job["project_name"],
        "startedAt": job["started_at"], "returnCode": job.get("return_code"),
        "log": log, "withBlender": job["with_blender"],
        "mode": job.get("mode", "quest"),
    }


class WorkbenchHandler(BaseHTTPRequestHandler):
    server_version = "VibeCreateWorkbench/1.0"

    def log_message(self, format: str, *args) -> None:
        # Keep the background desktop app's log quiet; generation output has its own log.
        return

    def _send(self, status: int, body: bytes, content_type: str, headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: dict) -> None:
        self._send(status, json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _body_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise ValueError("Request is too large")
        value = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(value, dict):
            raise ValueError("Expected a JSON object")
        return value

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urlparse(origin)
        return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}

    def do_GET(self) -> None:
        if not self._host_ok():
            self._json(403, {"error": "This workbench is available only through localhost"})
            return
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/api/status":
            self._json(200, {
                "localOnly": True,
                "ollama": local_models(),
                "blender": {"available": DEFAULT_BLENDER.is_file(), "path": str(DEFAULT_BLENDER)},
                "godot": {"available": godot_executable() is not None,
                          "path": str(godot_executable()) if godot_executable() else ""},
                "projectCount": len(list_projects()),
                "version": "1.0",
            })
            return
        if path == "/api/projects":
            self._json(200, {"projects": list_projects()})
            return
        if path == "/api/jobs":
            with JOBS_LOCK:
                active = [job_snapshot(job) for job in JOBS.values() if job["status"] in {"queued", "running"}]
            self._json(200, {"jobs": active})
            return
        if path.startswith("/api/jobs/"):
            job_id = path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if not job:
                self._json(404, {"error": "Generation job not found"})
                return
            self._json(200, job_snapshot(job))
            return
        if path.startswith("/api/export/") and path.endswith(".zip"):
            project_id = path.removeprefix("/api/export/").removesuffix(".zip")
            project_dir = PROJECTS_ROOT / project_id
            if not within(project_dir, PROJECTS_ROOT) or project_summary(project_dir) is None:
                self._json(404, {"error": "A completed project was not found."})
                return
            self._export_project(project_dir)
            return
        if path.startswith("/api/export-web/") and path.endswith(".zip"):
            project_id = path.removeprefix("/api/export-web/").removesuffix(".zip")
            project_dir = PROJECTS_ROOT / project_id
            if not within(project_dir, PROJECTS_ROOT) or project_summary(project_dir) is None:
                self._json(404, {"error": "A completed project was not found."})
                return
            self._export_web_project(project_dir)
            return
        if path.startswith("/project/"):
            self._serve_project(path)
            return
        if path == "/" or path == "/index.html":
            self._serve_file(WEB_ROOT / "index.html", WEB_ROOT)
            return
        if path.startswith("/assets/"):
            relative = Path(path.removeprefix("/assets/"))
            self._serve_file(WEB_ROOT / relative, WEB_ROOT)
            return
        self._json(404, {"error": "Not found"})

    def _serve_project(self, url_path: str) -> None:
        parts = url_path.split("/")[2:]
        if len(parts) < 2 or not parts[0] or any(part in {".", ".."} for part in parts):
            self._json(404, {"error": "Project artifact not found"})
            return
        candidate = PROJECTS_ROOT.joinpath(*parts)
        if not within(candidate, PROJECTS_ROOT) or not candidate.is_file():
            self._json(404, {"error": "Project artifact not found"})
            return
        download = parse_qs(urlparse(self.path).query).get("download") == ["1"]
        headers = {"Content-Disposition": f'attachment; filename="{candidate.name}"'} if download else None
        self._serve_file(candidate, PROJECTS_ROOT, headers)

    def _export_project(self, project_dir: Path) -> None:
        """Package the portable project source and generated assets, excluding editor caches."""
        archive = io.BytesIO()
        ignored = {".godot", "__pycache__", "node_modules", ".git"}
        try:
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
                for candidate in sorted(project_dir.rglob("*")):
                    if not candidate.is_file():
                        continue
                    relative = candidate.relative_to(project_dir)
                    if any(part in ignored for part in relative.parts):
                        continue
                    if candidate.name in {".DS_Store", "workbench.log"} or candidate.suffix in {".pyc", ".tmp"}:
                        continue
                    bundle.write(candidate, (Path(project_dir.name) / relative).as_posix())
        except OSError as exc:
            self._json(500, {"error": f"Could not package this project: {exc}"})
            return
        self._send(200, archive.getvalue(), "application/zip", {
            "Content-Disposition": f'attachment; filename="{project_dir.name}.zip"',
            "Cache-Control": "no-store",
        })

    def _export_web_project(self, project_dir: Path) -> None:
        """Package a web-installable PWA playable in any browser, offline."""
        archive = io.BytesIO()
        try:
            info = export_web_project(project_dir)
            web_root = Path(info["web_root"])
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
                for candidate in sorted(web_root.rglob("*")):
                    if not candidate.is_file():
                        continue
                    relative = candidate.relative_to(web_root)
                    bundle.write(candidate, (Path("web") / relative).as_posix())
            filename = f"{project_dir.name}-web.zip"
        except (OSError, FileNotFoundError, ValueError) as exc:
            self._json(500, {"error": f"Could not build the web export: {exc}"})
            return
        self._send(200, archive.getvalue(), "application/zip", {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-VibeCreate-Web-Export": "1",
        })

    def _serve_file(self, path: Path, allowed_root: Path, headers: dict | None = None) -> None:
        if not within(path, allowed_root) or not path.is_file():
            self._json(404, {"error": "File not found"})
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        elif path.suffix in {".html", ".css", ".json"}:
            content_type += "; charset=utf-8"
        try:
            self._send(200, path.read_bytes(), content_type, headers)
        except OSError:
            self._json(404, {"error": "File not found"})

    def do_POST(self) -> None:
        if not self._host_ok() or not self._origin_ok():
            self._json(403, {"error": "This local workbench accepts requests only from its own page"})
            return
        try:
            data = self._body_json()
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})
            return
        path = urlparse(self.path).path
        if path == "/api/generate":
            self._start_generation(data)
        elif path == "/api/cancel":
            self._cancel_generation(data)
        elif path == "/api/open":
            self._open_local_item(data)
        elif path == "/api/pick-target":
            self._pick_target_project()
        elif path == "/api/shutdown":
            self._json(200, {"status": "shutting-down"})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self._json(404, {"error": "Not found"})

    def _start_generation(self, data: dict) -> None:
        idea = str(data.get("idea", "")).strip()
        title = str(data.get("title", "")).strip()
        if not idea:
            self._json(400, {"error": "Describe the game idea first."})
            return
        if len(idea) > 4000 or len(title) > 100:
            self._json(400, {"error": "The idea or title is too long."})
            return
        mode = str(data.get("mode", "sandbox")).strip().lower()
        if mode not in {"sandbox", "quest", "dark-fantasy"}:
            self._json(400, {"error": "Choose the sandbox world, quest RPG, or dark fantasy action RPG build mode."})
            return
        if not title:
            title = " ".join(idea.split()[:5]).strip(".,!?;:") or "Idea Game"
        with_blender = mode == "quest" and bool(data.get("withBlender", True))
        with_review = bool(data.get("withReview", True))
        try:
            seed = int(data.get("seed", 4172026))
            chunks = int(data.get("chunks", 8))
        except (TypeError, ValueError):
            self._json(400, {"error": "Seed and chunk count must be whole numbers."})
            return
        if not 0 <= seed <= 2**31 - 1:
            self._json(400, {"error": "Seed must be between 0 and 2147483647."})
            return
        if not 4 <= chunks <= 16:
            self._json(400, {"error": "Chunk count must be between 4 and 16."})
            return
        target_project = str(data.get("targetProject", "")).strip()
        palette = str(data.get("palette", "auto")).strip().lower()
        difficulty = str(data.get("difficulty", "normal")).strip().lower()
        biome = str(data.get("biome", "temperate")).strip().lower()
        try:
            enemy_count = int(data.get("enemyCount", 2))
            starting_wood = int(data.get("startingWood", 4))
            starting_dirt = int(data.get("startingDirt", 10))
            gravity = float(data.get("gravity", 920))
            jump_height = float(data.get("jumpHeight", -360))
            move_speed = float(data.get("moveSpeed", 185))
            camera_zoom = float(data.get("cameraZoom", 1.0))
            save_interval = float(data.get("saveInterval", 3))
            chaos = float(data.get("chaos", 1))
        except (TypeError, ValueError):
            self._json(400, {"error": "Knob values must be numbers."})
            return
        enemy_behavior = str(data.get("enemyBehavior", "patrol")).strip().lower()
        review_strictness = str(data.get("reviewStrictness", "standard")).strip().lower()
        if mode == "quest" and target_project:
            target_path = Path(target_project).expanduser()
            if not target_path.exists() or (not target_path.is_dir() and target_path.suffix.lower() != ".uproject"):
                self._json(400, {"error": "Choose an existing project folder or .uproject file."})
                return
        global GENERATION_STARTING
        with JOBS_LOCK:
            if GENERATION_STARTING or any(job["status"] in {"queued", "running"} for job in JOBS.values()):
                self._json(409, {"error": "A local generation is already running. Wait for it to finish first."})
                return
            GENERATION_STARTING = True
        stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        safe_title = "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in title).split())[:36].strip("-") or "idea-game"
        project_id = f"{safe_title}-{stamp}-{time.monotonic_ns() % 1000000000:09d}"
        out_dir = PROJECTS_ROOT / project_id
        try:
            out_dir.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            with JOBS_LOCK:
                GENERATION_STARTING = False
            self._json(500, {"error": f"Could not create the output project: {exc}"})
            return
        log_path = out_dir / "workbench.log"
        if mode == "sandbox":
            command = [sys.executable, "-u", str(SANDBOX_GENERATOR), idea, "--title", title,
                       "--out", str(out_dir), "--seed", str(seed), "--chunks", str(chunks),
                       "--model", str(data.get("plannerModel") or "qwen3.5:2b"),
                       "--vision-model", str(data.get("visionModel") or "qwen2.5vl:3b"),
                       "--palette", palette,
                       "--difficulty", difficulty,
                       "--biome", biome,
                       "--enemy-count", str(enemy_count),
                       "--enemy-behavior", enemy_behavior,
                       "--starting-wood", str(starting_wood),
                       "--starting-dirt", str(starting_dirt),
                       "--gravity", str(gravity),
                       "--jump-height", str(jump_height),
                       "--move-speed", str(move_speed),
                       "--camera-zoom", str(camera_zoom),
                       "--save-interval", str(save_interval),
                       "--chaos", str(chaos),
                       "--review-strictness", review_strictness]
            if not with_review:
                command.append("--skip-vision-review")
        elif mode == "dark-fantasy":
            command = [sys.executable, "-u", str(DARK_FANTASY_GENERATOR), idea, "--title", title,
                       "--out", str(out_dir), "--seed", str(seed),
                       "--model", str(data.get("plannerModel") or "qwen3.5:2b"),
                       "--vision-model", str(data.get("visionModel") or "qwen2.5vl:3b")]
            if not with_review:
                command.append("--skip-vision-review")
        else:
            command = [sys.executable, "-u", str(GENERATOR), idea, "--title", title,
                       "--out", str(out_dir), "--model", str(data.get("plannerModel") or "qwen3.5:2b"),
                       "--vision-model", str(data.get("visionModel") or "qwen2.5vl:3b")]
            if with_blender:
                command.append("--with-blender")
                if not with_review:
                    command.append("--skip-vision-review")
        if mode == "quest" and target_project:
            command.extend(["--target-project", str(Path(target_project).expanduser())])
        environment = os.environ.copy()
        environment["PYTHONUNBUFFERED"] = "1"
        job_id = f"job-{stamp}-{time.monotonic_ns()}"
        try:
            with log_path.open("wb") as log:
                process = subprocess.Popen(command, cwd=ROOT, env=environment,
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as exc:
            with JOBS_LOCK:
                GENERATION_STARTING = False
            self._json(500, {"error": f"Could not start the local generator: {exc}"})
            return
        job = {
            "id": job_id, "status": "running", "project_id": project_id,
            "project_name": title, "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "with_blender": with_blender, "process": process, "log_path": log_path,
            "out_dir": out_dir, "return_code": None, "cancel_requested": False,
            "mode": mode, "seed": seed, "chunks": chunks,
        }
        with JOBS_LOCK:
            JOBS[job_id] = job
            GENERATION_STARTING = False
        threading.Thread(target=self._watch_job, args=(job_id,), daemon=True).start()
        self._json(202, job_snapshot(job))

    @staticmethod
    def _watch_job(job_id: str) -> None:
        with JOBS_LOCK:
            job = JOBS.get(job_id)
        if not job:
            return
        code = job["process"].wait()
        manifest_path = job["out_dir"] / "project.json"
        pipeline_warning = False
        try:
            manifest = json.loads(manifest_path.read_text())
            stage_status = {stage.get("id"): stage.get("status") for stage in manifest.get("stages", [])}
            pipeline_warning = (stage_status.get("blender-concept") == "failed"
                                or stage_status.get("render-review") == "blocked"
                                or stage_status.get("unreal-integration") == "blocked")
        except (OSError, json.JSONDecodeError):
            pass
        with JOBS_LOCK:
            job["return_code"] = code
            if job["cancel_requested"]:
                job["status"] = "cancelled"
            elif code != 0 or not ((job["out_dir"] / "sandbox-game" / "project.godot").is_file()
                                   if job.get("mode") == "sandbox"
                                   else (job["out_dir"] / "index.html").is_file()):
                job["status"] = "failed"
            elif pipeline_warning:
                job["status"] = "complete_with_warnings"
            else:
                job["status"] = "complete"

    def _cancel_generation(self, data: dict) -> None:
        with JOBS_LOCK:
            job = JOBS.get(str(data.get("jobId", "")))
            if not job or job["status"] != "running":
                self._json(404, {"error": "No active generation job found."})
                return
            job["cancel_requested"] = True
            try:
                os.killpg(job["process"].pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                job["process"].terminate()
        self._json(200, {"status": "cancelling"})

    def _open_local_item(self, data: dict) -> None:
        project_id = str(data.get("projectId", ""))
        project_dir = PROJECTS_ROOT / project_id
        if not within(project_dir, PROJECTS_ROOT) or not project_dir.is_dir():
            self._json(404, {"error": "Project not found"})
            return
        action = data.get("action")
        target = project_dir
        args: list[str] | None = None
        if action == "blender":
            target = project_dir / "blender-concept" / "concept.blend"
            if not target.is_file():
                self._json(404, {"error": "This project has no Blender scene yet."})
                return
        elif action in {"game", "godot-editor"}:
            godot_project = project_dir / "sandbox-game"
            if not (godot_project / "project.godot").is_file():
                self._json(404, {"error": "This project does not contain a Godot game."})
                return
            executable = godot_executable()
            if executable is None:
                self._json(503, {"error": "Godot 4.3 or newer is not installed. The generated project and art preview are ready; install Godot or set VIBE_GODOT_BIN to its executable to launch it."})
                return
            args = [str(executable)]
            if action == "godot-editor":
                args.append("--editor")
            args.extend(["--path", str(godot_project)])
        elif action != "folder":
            self._json(400, {"error": "Choose a project folder, Blender scene, or Godot runtime."})
            return
        try:
            if args is not None:
                subprocess.Popen(args, cwd=project_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            self._json(500, {"error": f"Could not open the selected item: {exc}"})
            return
        self._json(200, {"status": "opened"})

    def _pick_target_project(self) -> None:
        if sys.platform != "darwin" or not shutil.which("osascript"):
            self._json(400, {"error": "The project file picker is available on macOS. Paste the project path here instead."})
            return
        script = 'POSIX path of (choose file with prompt "Choose an Unreal .uproject file")'
        try:
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            self._json(500, {"error": f"Could not open the file picker: {exc}"})
            return
        if result.returncode != 0:
            self._json(200, {"cancelled": True})
            return
        chosen = result.stdout.strip()
        if not chosen.lower().endswith(".uproject") or not Path(chosen).is_file():
            self._json(400, {"error": "Choose a valid .uproject file."})
            return
        self._json(200, {"path": chosen})

    def _host_ok(self) -> bool:
        host = self.headers.get("Host", "").split(":", 1)[0].strip("[]").lower()
        return host in {"127.0.0.1", "localhost"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Local address only by default")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error("The workbench may bind only to localhost")
    server = ThreadingHTTPServer((args.host, args.port), WorkbenchHandler)
    print(f"Vibe Create local workbench: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
