#!/usr/bin/env python3
"""Ask an installed Ollama vision model for advisory feedback on generated pixel art."""

from __future__ import annotations

import argparse
import base64
import json
import re
import urllib.error
import urllib.request
from pathlib import Path


ENDPOINT = "http://127.0.0.1:11434/api/chat"


def review(image_path: Path, title: str, model: str, strictness: str = "standard") -> dict:
    image = base64.b64encode(image_path.read_bytes()).decode("ascii")
    schema = {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 1, "maximum": 5},
            "summary": {"type": "string", "maxLength": 140},
            "visible_assets": {"type": "array", "maxItems": 6, "items": {"type": "string", "maxLength": 60}},
            "issues": {"type": "array", "maxItems": 2, "items": {"type": "string", "maxLength": 90}},
            "recommended_edits": {"type": "array", "maxItems": 2, "items": {"type": "string", "maxLength": 90}},
        },
        "required": ["score", "summary", "visible_assets", "issues", "recommended_edits"],
        "additionalProperties": False,
    }
    strictness_guidance = {
        "lenient": "Be forgiving — only flag clear, severe readability problems that would make the game unplayable.",
        "standard": "Judge what is visible: readability at small pixel size, palette consistency, separation of terrain materials, and whether the frames read as coherent animations.",
        "strict": "Be thorough — flag even minor readability, palette consistency, material separation, or animation clarity issues. The bar for a clean review is high.",
    }.get(strictness, strictness_guidance["standard"])
    prompt = (
        f"Review this pixel-art sheet for the game {title!r}. It shows a terrain tile atlas on the left, "
        "four player animation frames at upper right, and two cave-enemy frames below. " + strictness_guidance +
        " Give up to two distinct, concrete issues and matching edits. "
        "Write every value in plain ASCII English with complete short sentences. Do not copy text labels from the image. "
        "If no clear issue is visible, return empty issue and edit arrays. Do not guess. Return the required JSON."
    )
    payload = {"model": model, "stream": False, "think": False, "format": schema,
               "keep_alive": 0, "options": {"temperature": 0.1, "num_predict": 300},
               "messages": [{"role": "user", "content": prompt, "images": [image]}]}
    request = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=175) as response:
        result = json.loads(response.read())
    content = json.loads(result.get("message", {}).get("content", "{}"))
    values_to_check = [content.get("summary", "")]
    for key in ("visible_assets", "issues", "recommended_edits"):
        if isinstance(content.get(key), list):
            values_to_check.extend(content[key])
    if any(any(ord(char) > 127 for char in str(value)) for value in values_to_check):
        return {
            "status": "unavailable",
            "reviewer": f"ollama:{model}",
            "reason": "The local vision model returned non-English text; its advisory report was omitted.",
            "automatedChanges": False,
        }

    def concise_list(values: object, count: int, width: int) -> list[str]:
        if not isinstance(values, list):
            return []
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = " ".join(str(value).split()).strip()
            if len(item) > width:
                prefix = item[:width]
                item = prefix.rsplit(" ", 1)[0].rstrip(" ,;:") + "…" if " " in prefix else prefix.rstrip(" ,;:") + "…"
            folded = item.casefold()
            if item and folded not in seen:
                cleaned.append(item)
                seen.add(folded)
            if len(cleaned) >= count:
                break
        return cleaned

    summary_text = " ".join(str(content.get("summary", "")).split()).strip()
    sentences = re.split(r"(?<=[.!?])\s+", summary_text)
    complete = ""
    for sentence in sentences:
        if not sentence.endswith((".", "!", "?")):
            break
        candidate = f"{complete} {sentence}".strip()
        if len(candidate) > 140:
            break
        complete = candidate
    summary = complete or summary_text[:140].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return {
        "status": "reviewed",
        "reviewer": f"ollama:{model}",
        "score": max(1, min(5, int(content.get("score", 3)))),
        "summary": summary,
        "visible_assets": concise_list(content.get("visible_assets", []), 6, 60),
        "issues": concise_list(content.get("issues", []), 2, 90),
        "recommended_edits": concise_list(content.get("recommended_edits", []), 2, 90),
        "automatedChanges": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("title")
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", default="qwen2.5vl:3b")
    parser.add_argument("--strictness", default="standard", choices=["lenient", "standard", "strict"],
                        help="How strictly the vision review judges the art")
    args = parser.parse_args()
    try:
        result = review(args.image, args.title, args.model, args.strictness)
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, TypeError, ValueError) as exc:
        result = {"status": "unavailable", "reviewer": f"ollama:{args.model}",
                  "reason": f"{type(exc).__name__}: {exc}", "automatedChanges": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
