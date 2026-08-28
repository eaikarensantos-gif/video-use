"""AI-driven auto-edit using OpenAI (preferred) or Anthropic (fallback).

This is the same job SKILL.md's "editor sub-agent" does inside a Claude Code
chat session — wired here as a direct API call so the visual editor can
trigger it without Claude Code running interactively. It proposes typed,
reviewable operations; the UI always asks before changing the timeline.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pack_transcripts import pack_one_file, render_markdown

DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def load_env_value(name: str) -> str:
    for candidate in [_REPO_ROOT / ".env", Path(".env")]:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == name:
                    return v.strip().strip('"').strip("'")
    return os.environ.get(name, "").strip()


def configured_provider() -> dict:
    if load_env_value("OPENAI_API_KEY"):
        return {"provider": "openai", "model": load_env_value("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL, "configured": True}
    if load_env_value("ANTHROPIC_API_KEY"):
        return {"provider": "anthropic", "model": load_env_value("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL, "configured": True}
    return {"provider": None, "model": None, "configured": False}


def pack_all_transcripts(edit_dir: Path) -> str:
    transcripts_dir = edit_dir / "transcripts"
    json_files = sorted(transcripts_dir.glob("*.json")) if transcripts_dir.is_dir() else []
    if not json_files:
        return "(No transcripts available. Visual-only operations can still be proposed.)"
    entries = [pack_one_file(p, 0.5) for p in json_files]
    return render_markdown(entries, 0.5)


BRIEF_TEMPLATE = """You are editing a video. Pick the best moments from the source \
transcripts below and assemble a cut that follows the user's brief.

USER BRIEF:
{brief}
{duration_line}
Current playhead: {playhead:.2f} seconds.
Current timeline duration: {timeline_duration:.2f} seconds.

SOURCE TRANSCRIPTS (phrase-level, time-annotated, one section per source file):
{packed}

RULES:
- First identify the requested operation. Do not propose cuts for a visual-only request.
- For requests to write/show/add a phrase on screen, create a text_overlays item with exactly the requested text.
- If the user does not specify timing for a text overlay, start it at the current playhead and show it for 3 seconds.
- Every "source" value must be one of the section names above (e.g. "C0103"), exactly.
- start/end must fall on phrase boundaries visible in the transcript — never mid-word.
- Downstream padding (30-200ms) is applied automatically; do not add it yourself.
- Prefer cuts at silences or between phrases.
- If multiple sources cover the same moment, pick the cleanest delivery.
- Assemble chronologically by the story you're building, not by source file order.
- Skip verbal slips, false starts, and filler ("um", "uh", "like") unless removing \
them would cut a moment the brief asked you to keep.

Respond with ONLY a JSON object containing both arrays:
{{"cuts": [{{"source": "<source>", "start": 0, "end": 1, "beat": "label", "reason": "why"}}],
"text_overlays": [{{"text": "exact text", "start": 0, "duration": 3, "position": "center",
"font_size": 64, "color": "white", "background": false, "reason": "why"}}]}}
"""


def build_prompt(packed: str, brief: str, target_duration: float | None, playhead: float = 0, timeline_duration: float = 0) -> str:
    duration_line = f"Target total runtime: ~{target_duration:.0f} seconds." if target_duration else ""
    return BRIEF_TEMPLATE.format(brief=brief.strip(), duration_line=duration_line, packed=packed,
                                 playhead=max(0, playhead), timeline_duration=max(0, timeline_duration))


def parse_plan(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
        if not match:
            raise RuntimeError(f"could not find JSON in the model response: {text[:300]!r}")
        data = json.loads(match.group(0))
    if isinstance(data, list):
        data = {"cuts": data, "text_overlays": []}
    if not isinstance(data, dict):
        raise RuntimeError("model response was not an edit plan")
    cuts = data.get("cuts", [])
    overlays = data.get("text_overlays", [])
    if not isinstance(cuts, list) or not isinstance(overlays, list):
        raise RuntimeError("edit plan arrays are invalid")
    return {"cuts": cuts, "text_overlays": overlays}


def parse_ranges(text: str) -> list[dict]:
    data = parse_plan(text)["cuts"]
    ranges: list[dict] = []
    for item in data:
        if not isinstance(item, dict) or not {"source", "start", "end"} <= item.keys():
            raise RuntimeError("each proposed cut must contain source, start, and end")
        source = str(item["source"])
        start, end = float(item["start"]), float(item["end"])
        if not source or start < 0 or end <= start:
            raise RuntimeError(f"invalid proposed cut: source={source!r}, start={start}, end={end}")
        ranges.append({"source": source, "start": start, "end": end,
                       "beat": str(item.get("beat", "")), "reason": str(item.get("reason", ""))})
    return ranges


def parse_text_overlays(text: str, timeline_duration: float = 0) -> list[dict]:
    overlays = []
    for item in parse_plan(text)["text_overlays"]:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str) or not item["text"].strip():
            raise RuntimeError("each text overlay must contain non-empty text")
        start, duration = float(item.get("start", 0)), float(item.get("duration", 3))
        position = str(item.get("position", "center"))
        if start < 0 or duration <= 0 or position not in {"top", "center", "bottom"}:
            raise RuntimeError("invalid text overlay timing or position")
        if timeline_duration > 0:
            start = min(start, timeline_duration)
            duration = min(duration, max(0.1, timeline_duration - start))
        overlays.append({
            "text": item["text"].strip(), "start": start, "duration": duration, "position": position,
            "font_size": max(12, min(240, int(item.get("font_size", 64)))), "color": str(item.get("color", "white")),
            "background": bool(item.get("background", False)), "reason": str(item.get("reason", "")),
        })
    return overlays


def validate_ranges(ranges: list[dict], transcripts_dir: Path) -> list[dict]:
    """Reject hallucinated sources and timestamps outside their transcripts."""
    limits: dict[str, float] = {}
    for path in transcripts_dir.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        ends = [float(w["end"]) for w in payload.get("words", []) if isinstance(w.get("end"), (int, float))]
        limits[path.stem] = max(ends, default=0.0)
    for item in ranges:
        source = item["source"]
        if source not in limits:
            raise RuntimeError(f"model proposed unknown source {source!r}")
        if item["end"] > limits[source] + 0.25:
            raise RuntimeError(f"model proposed timestamp outside {source!r}: {item['end']:.2f}s > {limits[source]:.2f}s")
    return ranges


def run_auto_edit(
    edit_dir: Path,
    brief: str,
    target_duration: float | None = None,
    playhead: float = 0,
    timeline_duration: float = 0,
    log: "callable[[str], None]" = print,
) -> dict:
    log("reading transcripts…")
    packed = pack_all_transcripts(edit_dir)
    prompt = build_prompt(packed, brief, target_duration, playhead, timeline_duration)
    provider = configured_provider()
    if not provider["configured"]:
        raise RuntimeError("Configure OPENAI_API_KEY (recommended) or ANTHROPIC_API_KEY in the .env file")

    log(f"asking {provider['provider']} / {provider['model']} to propose a cut…")
    if provider["provider"] == "openai":
        from openai import OpenAI

        cut_item = {
            "type": "object", "additionalProperties": False,
            "properties": {"source": {"type": "string"}, "start": {"type": "number"}, "end": {"type": "number"},
                           "beat": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["source", "start", "end", "beat", "reason"],
        }
        text_item = {
            "type": "object", "additionalProperties": False,
            "properties": {"text": {"type": "string"}, "start": {"type": "number"}, "duration": {"type": "number"},
                           "position": {"type": "string", "enum": ["top", "center", "bottom"]},
                           "font_size": {"type": "integer"}, "color": {"type": "string"},
                           "background": {"type": "boolean"}, "reason": {"type": "string"}},
            "required": ["text", "start", "duration", "position", "font_size", "color", "background", "reason"],
        }
        schema = {
            "type": "object", "additionalProperties": False,
            "properties": {"cuts": {"type": "array", "items": cut_item},
                           "text_overlays": {"type": "array", "items": text_item}},
            "required": ["cuts", "text_overlays"],
        }
        client = OpenAI(api_key=load_env_value("OPENAI_API_KEY"))
        response = client.responses.create(
            model=provider["model"], input=prompt,
            text={"format": {"type": "json_schema", "name": "video_edit_plan", "strict": True, "schema": schema}},
        )
        text = response.output_text
    else:
        import anthropic

        client = anthropic.Anthropic(api_key=load_env_value("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=provider["model"], max_tokens=8000, thinking={"type": "adaptive"},
            output_config={"effort": "high"}, messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
    if not text.strip():
        raise RuntimeError("model returned no text output — check the API response for a refusal")

    log("validating proposed operations…")
    ranges = validate_ranges(parse_ranges(text), edit_dir / "transcripts")
    overlays = parse_text_overlays(text, timeline_duration)
    if not ranges and not overlays:
        raise RuntimeError("the model returned an empty edit plan")
    log(f"got {len(ranges)} cut(s) and {len(overlays)} text overlay(s)")
    return {"ranges": ranges, "text_overlays": overlays}
