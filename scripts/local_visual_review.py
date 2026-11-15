#!/usr/bin/env python3
"""Review a generated Blender render with the installed local vision model."""

from __future__ import annotations

import base64
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


ENDPOINT = "http://127.0.0.1:11434/api/chat"


def review(image_path: Path, title: str, model: str = "qwen2.5vl:3b", closeup_path: Path | None = None) -> dict:
    image = base64.b64encode(image_path.read_bytes()).decode("ascii")
    images = [image]
    if closeup_path and closeup_path.is_file():
        images.append(base64.b64encode(closeup_path.read_bytes()).decode("ascii"))
    prompt = (
        f"Review the Blender render for {title!r}. "
        + ("Image 1 is the full scene. Image 2 is a face close-up. " if len(images) > 1 else "")
        + "Report visible evidence only. On the face, count visible eyes and say whether they read as front-facing or side-placed. "
        "Use one short sentence for summary and face; use empty arrays when no concrete issue or edit exists. Return JSON only."
    )
    response_schema = {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 1, "maximum": 5},
            "summary": {"type": "string", "maxLength": 110},
            "visible_elements": {"type": "array", "maxItems": 5, "items": {"type": "string", "maxLength": 55}},
            "issues": {"type": "array", "maxItems": 3, "items": {"type": "string", "maxLength": 75}},
            "character_face": {"type": "string", "maxLength": 80},
            "recommended_edits": {"type": "array", "maxItems": 2, "items": {"type": "string", "maxLength": 75}},
        },
        "required": ["score", "summary", "visible_elements", "issues", "character_face", "recommended_edits"],
        "additionalProperties": False,
    }
    payload = {"model": model, "stream": False, "think": False, "format": response_schema, "keep_alive": 0,
               "options": {"temperature": 0.1, "num_predict": 350},
               "messages": [{"role": "user", "content": prompt, "images": images}]}
    request = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        result = json.loads(response.read())
    raw_content = result.get("message", {}).get("content", "{}")
    try:
        content = json.loads(raw_content)
    except json.JSONDecodeError:
        # Some small local vision models occasionally ignore constrained JSON.
        # Retry once with an even shorter request before recording a failure.
        retry_payload = dict(payload)
        retry_payload["messages"] = [{"role": "user", "content": "Briefly inspect this Blender render. Say if the face has two front-facing eyes or side-placed eyes. Return the required JSON only.", "images": images}]
        retry_payload["options"] = {"temperature": 0.0, "num_predict": 300}
        retry = urllib.request.Request(ENDPOINT, data=json.dumps(retry_payload).encode(),
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(retry, timeout=300) as response:
            result = json.loads(response.read())
        content = json.loads(result.get("message", {}).get("content", "{}"))
    if not isinstance(content, dict):
        raise ValueError("Vision model response must be a JSON object")
    issues = content.get("issues", [])
    edits = content.get("recommended_edits", [])
    score = max(1, min(5, int(content.get("score", 3))))
    summary = str(content.get("summary", ""))[:500]

    def complete_sentence(value: object, width: int) -> str:
        text = " ".join(str(value or "").split())[:width].rstrip(" -,:;")
        if not text or text.endswith((".", "!", "?", "…")):
            return text
        last_sentence = max(text.rfind("."), text.rfind("!"), text.rfind("?"))
        if last_sentence >= 0:
            return text[:last_sentence + 1]
        return text + "…"

    summary = complete_sentence(summary, 500)

    def concise_items(values: object, limit: int, width: int, kind: str) -> list[str]:
        if not isinstance(values, list):
            return []
        result = []
        for value in values[:limit]:
            item = str(value).strip()[:width]
            if not item or item.casefold() == summary.casefold():
                continue
            lowered = item.casefold()
            is_action = any(word in lowered for word in (
                "add ", "move ", "adjust ", "improve ", "make ", "increase ", "reduce ",
                "remove ", "raise ", "lower ", "show ", "refine ", "reposition ", "light ",
                "crop ", "widen ", "strengthen ", "ensure ", "align ", "adding ", "change ",
                "fix ", "rework "
            ))
            is_problem = any(word in lowered for word in (
                "not ", "missing", "unclear", "obscured", "cropped", "overlap", "misplaced",
                "side-placed", "poor ", "too ", "hard to see", "difficult to see", "cannot see",
                "flat ", "lack ", "basic ", "low contrast", "cluttered"
            ))
            is_praise = any(word in lowered for word in (
                "clear and detailed", "looks good", "well composed", "front-facing eyes"
            ))
            if score >= 4 and is_praise and not is_action and not is_problem:
                continue
            if score >= 4 and kind == "issues" and not is_problem:
                continue
            if score >= 4 and kind == "recommended_edits" and not is_action:
                continue
            if item not in result:
                result.append(item)
        return result

    return {
        "status": "reviewed",
        "reviewer": f"ollama:{model}",
        "score": score,
        "summary": summary,
        "visible_elements": concise_items(content.get("visible_elements", []), 12, 160, "visible_elements"),
        "issues": concise_items(issues, 12, 240, "issues"),
        "character_face": complete_sentence(content.get("character_face", "not reported"), 240),
        "recommended_edits": concise_items(edits, 3, 240, "recommended_edits"),
        "automatedChanges": False
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("title")
    parser.add_argument("output", type=Path)
    parser.add_argument("--closeup", type=Path)
    parser.add_argument("--model", default="qwen2.5vl:3b")
    args = parser.parse_args()
    try:
        result = review(args.image, args.title, args.model, args.closeup)
    except (OSError, urllib.error.URLError, TimeoutError, ValueError, TypeError, KeyError) as exc:
        result = {"status": "unavailable", "reviewer": f"ollama:{args.model}",
                  "reason": f"{type(exc).__name__}: {exc}", "automatedChanges": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
