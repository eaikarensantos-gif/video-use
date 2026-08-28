"""Translate a source's transcript into another language for burned-in
captions, via Claude — kept out of helpers/render.py on purpose, since
that script has no Anthropic dependency and is also the chat flow's/CLI's
render path, which shouldn't suddenly require an API key it doesn't use.

LLM translation doesn't preserve word count or order, so exact per-word
timestamps aren't meaningful across languages the way they are within one
language. What *is* meaningful: phrase (sentence) boundaries — Claude
translates one phrase at a time, and each phrase's translated words are
spread evenly across that phrase's real (original-language) time span.
Good enough for word-burst captions; not claiming perfect sync.

The output is written in the exact same {"words": [...]} shape ElevenLabs
Scribe produces, so helpers/render.py's existing SRT builder (which reads
transcripts/<name>.json normally) can read a translated transcript at
transcripts/<name>.<lang>.json without any changes of its own.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def translate_transcript(
    transcript_path: Path,
    target_language: str,
    api_key: str,
    cache_path: Path,
) -> Path:
    """Translate transcript_path into target_language, caching the result
    at cache_path. Returns cache_path (existing or freshly written)."""
    if cache_path.exists():
        return cache_path

    from pack_transcripts import group_into_phrases  # same dir on sys.path

    transcript = json.loads(transcript_path.read_text())
    words = transcript.get("words", [])
    phrases = group_into_phrases(words, silence_threshold=0.5)

    out_words: list[dict] = []
    if phrases:
        out_words = _translate_phrases(phrases, target_language, api_key)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({"words": out_words, "language": target_language}, indent=2))
    return cache_path


def _translate_phrases(phrases: list[dict], target_language: str, api_key: str) -> list[dict]:
    import anthropic

    numbered = "\n".join(f"{i + 1}. {p['text']}" for i, p in enumerate(phrases))
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-opus-5",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": (
                f"Translate each numbered line into {target_language}. Reply with "
                "the same numbering, one translation per line, nothing else — no "
                "preamble, no notes, no quotes around the text. Keep the tone "
                "casual/spoken, matching the original.\n\n" + numbered
            ),
        }],
    )
    text = "".join(block.text for block in message.content if getattr(block, "type", None) == "text")

    translated: dict[int, str] = {}
    for line in text.strip().splitlines():
        m = re.match(r"^\s*(\d+)[.\)]\s*(.+)$", line.strip())
        if m:
            translated[int(m.group(1))] = m.group(2).strip()

    out_words: list[dict] = []
    for i, p in enumerate(phrases, start=1):
        phrase_text = translated.get(i, p["text"])  # missing line -> keep original as fallback
        word_texts = phrase_text.split()
        if not word_texts:
            continue
        duration = max(0.05, p["end"] - p["start"])
        step = duration / len(word_texts)
        for j, wt in enumerate(word_texts):
            out_words.append({
                "type": "word",
                "text": wt,
                "start": p["start"] + j * step,
                "end": p["start"] + (j + 1) * step,
                "speaker_id": p.get("speaker_id"),
            })
    return out_words
