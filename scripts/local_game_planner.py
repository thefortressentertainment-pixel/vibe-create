#!/usr/bin/env python3
"""Create validated game content using only Ollama on localhost."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request


LOCAL_OLLAMA = "http://127.0.0.1:11434/api/chat"


def fallback(idea: str, title: str) -> dict:
    text = idea.lower()
    if any(word in text for word in ("valtherion", "crypt", "medieval", "bog", "wraith", "zorvathax")):
        npc = {"name": "Old Man Thane", "role": "hamlet guide", "dialogue": "The crypt lanterns have gone dark. Gather three wisps and light the old beacon before nightfall."}
        enemy = {"name": "Crypt Warden", "role": "restless guardian", "health": 5, "attack": 1}
        collectible = {"name": "will-o-wisp", "count": 3, "color": "#86F1D1"}
        quest = {"name": "Light the Wraithmoor Beacon", "brief": "Gather three will-o-wisps and defeat the Crypt Warden.", "reward": "A safe road through the bog"}
        setting = "A foggy path from Murkfen Hamlet to the ruined Wraithmoor crypts."
        player = {"name": "The Wayfarer", "role": "Child of the Light"}
    elif "dragon" in text:
        npc = {"name": "Keeper Nima", "role": "beacon keeper", "dialogue": "The sky beacon has dimmed. Find three star shards and drive the cloud-stalker away."}
        enemy = {"name": "Cloud-stalker", "role": "island predator", "health": 5, "attack": 1}
        collectible = {"name": "star shard", "count": 3, "color": "#FFC65C"}
        quest = {"name": "Relight the Sky Beacon", "brief": "Collect three star shards and defeat the cloud-stalker.", "reward": "The beacon opens the next floating island"}
        setting = "A chain of small floating islands above a deep blue cloud sea."
        player = {"name": "Pip", "role": "young sky dragon"}
    else:
        npc = {"name": "Mira", "role": "trail guide", "dialogue": "The old signal is failing. Find three power fragments and clear the path."}
        enemy = {"name": "Path guardian", "role": "guardian", "health": 4, "attack": 1}
        collectible = {"name": "power fragment", "count": 3, "color": "#FFC65C"}
        quest = {"name": "Restore the Signal", "brief": "Collect three power fragments and defeat the path guardian.", "reward": "The trail to the next region opens"}
        setting = f"A compact adventure area inspired by this idea: {idea}"
        player = {"name": "Wayfarer", "role": "adventurer"}
    return {"title": title, "setting": setting, "objective": quest["brief"], "player": player,
            "npc": npc, "enemy": enemy, "collectible": collectible, "quest": quest}


def normalize(data: dict, idea: str, title: str) -> dict:
    base = fallback(idea, title)

    def phrase(value, default, limit=180):
        value = re.sub(r"\s+", " ", str(value or default)).strip()
        return value[:limit] or default

    def bounded_int(value, default, low, high):
        try:
            return max(low, min(high, int(value)))
        except (TypeError, ValueError):
            return default

    data = data if isinstance(data, dict) else {}
    normalized = {
        "title": phrase(data.get("title"), title, 80),
        "setting": phrase(data.get("setting"), base["setting"]),
        "objective": phrase(data.get("objective"), base["objective"]),
        "player": {"name": phrase((data.get("player") or {}).get("name"), base["player"]["name"], 48),
                   "role": phrase((data.get("player") or {}).get("role"), base["player"]["role"], 64)},
        "npc": {"name": phrase((data.get("npc") or {}).get("name"), base["npc"]["name"], 48),
                "role": phrase((data.get("npc") or {}).get("role"), base["npc"]["role"], 64),
                "dialogue": phrase((data.get("npc") or {}).get("dialogue"), base["npc"]["dialogue"], 240)},
        "enemy": {"name": phrase((data.get("enemy") or {}).get("name"), base["enemy"]["name"], 48),
                  "role": phrase((data.get("enemy") or {}).get("role"), base["enemy"]["role"], 64),
                  "health": bounded_int((data.get("enemy") or {}).get("health"), base["enemy"]["health"], 1, 10),
                  "attack": bounded_int((data.get("enemy") or {}).get("attack"), base["enemy"]["attack"], 1, 4)},
        "collectible": {"name": phrase((data.get("collectible") or {}).get("name"), base["collectible"]["name"], 48),
                        "count": bounded_int((data.get("collectible") or {}).get("count"), base["collectible"]["count"], 1, 8),
                        "color": str((data.get("collectible") or {}).get("color", base["collectible"]["color"]))},
        "quest": {"name": phrase((data.get("quest") or {}).get("name"), base["quest"]["name"], 80),
                  "brief": phrase((data.get("quest") or {}).get("brief"), base["quest"]["brief"], 200),
                  "reward": phrase((data.get("quest") or {}).get("reward"), base["quest"]["reward"], 100)}
    }
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", normalized["collectible"]["color"]):
        normalized["collectible"]["color"] = base["collectible"]["color"]
    return normalized


def generate_local_content(idea: str, title: str, model: str = "qwen3.5:2b") -> tuple[dict, str, str]:
    system = (
        "Design the content for a tiny original top-down RPG vertical slice from the user's idea. "
        "Return JSON only, no markdown. Use exactly these keys: title, setting, objective, player, npc, enemy, collectible, quest. "
        "player has name and role. npc has name, role, one short dialogue line. enemy has name, role, health integer 1-10, attack integer 1-4. "
        "collectible has name, count integer 1-8, color as #RRGGBB. quest has name, brief, reward. "
        "Keep the idea's genre and world, make one achievable encounter, and avoid copyrighted characters."
    )
    prompt = json.dumps({"title": title, "idea": idea}, ensure_ascii=False)
    payload = {"model": model, "stream": False, "think": False, "format": "json", "keep_alive": 0,
               "options": {"temperature": 0.5, "num_predict": 1000},
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
    request = urllib.request.Request(LOCAL_OLLAMA, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.loads(response.read())
        raw = result.get("message", {}).get("content", "")
        data = json.loads(raw)
        return normalize(data, idea, title), f"ollama:{model}", "Local model produced a structured encounter plan."
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
        return fallback(idea, title), "local-fallback", f"Local planner unavailable or invalid; used deterministic content. {type(exc).__name__}: {exc}"


if __name__ == "__main__":
    content, source, note = generate_local_content(sys.argv[1], sys.argv[2], os.environ.get("VIBE_GAME_MODEL", "qwen3.5:2b"))
    print(json.dumps({"source": source, "note": note, "content": content}, indent=2))
