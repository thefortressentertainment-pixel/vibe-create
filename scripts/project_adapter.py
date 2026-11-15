#!/usr/bin/env python3
"""Inspect a game project and stage Vibe Create assets for its engine."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


def inspect_project(path: Path) -> dict:
    """Identify a project from its root markers without changing it."""
    path = path.expanduser().resolve()
    if path.is_file():
        if path.suffix.lower() == ".uproject":
            root = path.parent
            uprojects = [path]
        else:
            raise ValueError(f"Expected a project folder or .uproject file: {path}")
    elif path.is_dir():
        root = path
        uprojects = list(root.glob("*.uproject"))
        if not uprojects:
            uprojects = list(root.glob("*/*.uproject"))
            if uprojects:
                root = uprojects[0].parent
    else:
        raise ValueError(f"Project path does not exist: {path}")

    if uprojects:
        descriptor = uprojects[0]
        try:
            config = json.loads(descriptor.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Can't read Unreal project descriptor {descriptor}: {exc}") from exc
        modules = config.get("Modules", [])
        enabled_plugins = [plugin.get("Name") for plugin in config.get("Plugins", []) if plugin.get("Enabled")]
        source_root = root / "Source"
        source_files = sorted(p.relative_to(root).as_posix() for p in source_root.rglob("*")
                              if p.is_file() and p.suffix in {".h", ".hpp", ".cpp", ".cs"}) if source_root.is_dir() else []
        architecture_classes = set()
        for file in source_files:
            if file.endswith((".h", ".hpp", ".cpp")):
                source_text = (root / file).read_text(errors="ignore")
                architecture_classes.update(re.findall(
                    r"\b(?:class|struct)\s+(?:\w+_API\s+)?(\w*(?:GameMode|GameInstance|PlayerController|Character|Pawn|GameState)\w*)\b",
                    source_text))
        architecture_classes = sorted(architecture_classes)
        config_markers = []
        engine_config = root / "Config" / "DefaultEngine.ini"
        if engine_config.is_file():
            config_text = engine_config.read_text(errors="ignore")
            config_markers = [line.strip() for line in config_text.splitlines()
                              if any(key in line.lower() for key in ("defaultgamemode", "gameinstanceclass", "globaldefaultgame.ini"))][:20]
        return {
            "engine": "unreal",
            "projectName": descriptor.stem,
            "projectRoot": str(root),
            "descriptor": str(descriptor),
            "engineAssociation": config.get("EngineAssociation"),
            "contentDirectory": str(root / "Content"),
            "contentExists": (root / "Content").is_dir(),
            "sourceDirectories": sorted(p.name for p in (root / "Source").glob("*") if p.is_dir()) if (root / "Source").is_dir() else [],
            "moduleNames": [module.get("Name") for module in modules if module.get("Name")],
            "enabledPlugins": enabled_plugins,
            "sourceFileCount": len(source_files),
            "sourceFiles": source_files[:120],
            "architectureClasses": architecture_classes,
            "engineConfigMarkers": config_markers,
            "integrationMode": "unreal-content-import",
            "evidence": [descriptor.name, "Content/" + (" present" if (root / "Content").is_dir() else " will be created")]
        }

    markers = []
    if (root / "project.godot").is_file():
        markers.append("godot")
    if (root / "Assets").is_dir() and (root / "ProjectSettings").is_dir():
        markers.append("unity")
    if any(p.is_file() for p in (root / "requirements.txt", root / "pyproject.toml", root / "CLIENT_INTEGRATION.md")):
        markers.append("backend-or-tools")
    if (root / "app").is_dir() and (root / "main.py").is_file():
        markers.append("python-service")
    if "godot" in markers:
        engine = "godot"
    elif "unity" in markers:
        engine = "unity"
    elif "backend-or-tools" in markers or "python-service" in markers:
        engine = "backend-only"
    else:
        engine = "unknown"
    return {
        "engine": engine,
        "projectName": root.name,
        "projectRoot": str(root),
        "descriptor": None,
        "contentDirectory": None,
        "integrationMode": "asset-bundle-only",
        "evidence": markers or ["No recognized project markers found"]
    }


def stage_unreal_assets(project: dict, asset_dir: Path, slug: str) -> dict:
    """Copy the FBX and preview into Unreal Content; leave source scene untouched."""
    root = Path(project["projectRoot"])
    destination = root / "Content" / "VibeCreate" / slug
    destination.mkdir(parents=True, exist_ok=True)
    copied = []
    for filename in ("concept.fbx", "concept.png"):
        source = asset_dir / filename
        if not source.is_file():
            continue
        target = destination / filename
        shutil.copy2(source, target)
        copied.append({"source": str(source), "destination": str(target), "format": source.suffix[1:]})
    if not any(item["format"] == "fbx" for item in copied):
        raise ValueError(f"No Blender FBX export found in {asset_dir}")
    return {
        "status": "copied-awaiting-unreal-import",
        "engine": "unreal",
        "destination": str(destination),
        "copiedFiles": copied,
        "nextAction": "Open the .uproject in Unreal Editor and allow Content/VibeCreate to import. Then review scale, materials, and collision."
    }


def write_import_helper(output_dir: Path, title: str, bundle_dir: Path, slug: str) -> Path:
    """Write a small Unreal Editor Python helper for optional scripted import."""
    destination = output_dir / "import_into_unreal.py"
    code = f'''"""Optional Unreal Editor Python import helper for {title}."""
import unreal

FBX_FILE = r"{(bundle_dir / 'concept.fbx').as_posix()}"
DESTINATION = "/Game/VibeCreate/{slug}"

task = unreal.AssetImportTask()
task.filename = FBX_FILE
task.destination_path = DESTINATION
task.automated = True
task.replace_existing = True
task.save = True
options = unreal.FbxImportUI()
options.import_as_skeletal = False
options.import_mesh = True
options.import_materials = False
options.import_textures = False
options.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
options.static_mesh_import_data.combine_meshes = True
task.options = options
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
unreal.log("Vibe Create assets imported to " + DESTINATION)
'''
    destination.write_text(code)
    return destination
