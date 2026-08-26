"""AI-driven auto-edit: sends the packed transcript + a user brief to Claude
via the Anthropic API and gets back a proposed cut list (EDL ranges).

This is the same job SKILL.md's "editor sub-agent" does inside a Claude Code
chat session — wired here as a direct API call so the visual editor can
trigger it without Claude Code running interactively. It only *proposes*
cuts; the UI always shows them for review before writing them into the
timeline (Hard Rule 11: strategy confirmation before execution).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pack_transcripts import pack_one_file, render_markdown

DEFAULT_MODEL = "claude-opus-5"
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def load_anthropic_key() -> str:
    for candidate in [_REPO_ROOT / ".env", Path(".env")]:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "ANTHROPIC_API_KEY":
                    return v.strip().strip('"').strip("'")
    v = os.environ.get("ANTHROPIC_API_KEY", "")
    if not v:
        raise RuntimeError("ANTHROPIC_API_KEY not found in .env or environment")
    return v


def pack_all_transcripts(edit_dir: Path) -> str:
    transcripts_dir = edit_dir / "transcripts"
    json_files = sorted(transcripts_dir.glob("*.json")) if transcripts_dir.is_dir() else []
    if not json_files:
        raise RuntimeError("no transcripts yet — transcribe your footage first")
    entries = [pack_one_file(p, 0.5) for p in json_files]
    return render_markdown(entries, 0.5)


BRIEF_TEMPLATE = """You are editing a video. Pick the best moments from the source \
transcripts below and assemble a cut that follows the user's brief.

USER BRIEF:
{brief}
{duration_line}

SOURCE TRANSCRIPTS (phrase-level, time-annotated, one section per source file):
{packed}

RULES:
- Every "source" value must be one of the section names above (e.g. "C0103"), exactly.
- start/end must fall on phrase boundaries visible in the transcript — never mid-word.
- Downstream padding (30-200ms) is applied automatically; do not add it yourself.
- Prefer cuts at silences or between phrases.
- If multiple sources cover the same moment, pick the cleanest delivery.
- Assemble chronologically by the story you're building, not by source file order.
- Skip verbal slips, false starts, and filler ("um", "uh", "like") unless removing \
them would cut a moment the brief asked you to keep.

Respond with ONLY a JSON array (no markdown fences, no prose before or after). Each \
element:
{{"source": "<source name from the transcripts above>", "start": <seconds, number>, \
"end": <seconds, number>, "beat": "<short label>", "reason": "<one line why>"}}
"""


def build_prompt(packed: str, brief: str, target_duration: float | None) -> str:
    duration_line = f"Target total runtime: ~{target_duration:.0f} seconds." if target_duration else ""
    return BRIEF_TEMPLATE.format(brief=brief.strip(), duration_line=duration_line, packed=packed)


def parse_ranges(text: str) -> list[dict]:
    text = text.strip()
    # Strip accidental markdown fences / stray prose if the model added them anyway.
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise RuntimeError(f"could not find a JSON array in the model's response: {text[:300]!r}")
    data = json.loads(match.group(0))
    if not isinstance(data, list):
        raise RuntimeError("model response was not a JSON array")
    ranges: list[dict] = []
    for item in data:
        ranges.append({
            "source": str(item["source"]),
            "start": float(item["start"]),
            "end": float(item["end"]),
            "beat": str(item.get("beat", "")),
            "reason": str(item.get("reason", "")),
        })
    return ranges


def run_auto_edit(
    edit_dir: Path,
    brief: str,
    target_duration: float | None = None,
    log: "callable[[str], None]" = print,
) -> list[dict]:
    import anthropic

    log("reading transcripts…")
    packed = pack_all_transcripts(edit_dir)

    log(f"asking {DEFAULT_MODEL} to propose a cut…")
    client = anthropic.Anthropic(api_key=load_anthropic_key())
    prompt = build_prompt(packed, brief, target_duration)
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    if not text.strip():
        raise RuntimeError("model returned no text output — check the API response for a refusal")

    log("parsing proposed cuts…")
    ranges = parse_ranges(text)
    log(f"got {len(ranges)} cut(s)")
    return ranges
