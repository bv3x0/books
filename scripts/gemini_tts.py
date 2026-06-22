#!/usr/bin/env python3
"""Render and synthesize Gemini TTS samples from audio scripts."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import re
import sys
import time
import wave
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback for bare Python.
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "gemini-3.1-flash-tts-preview"
DEFAULT_SAMPLE_RATE = 24000
DEFAULT_SAMPLE_WIDTH = 2
DEFAULT_CHANNELS = 1


DIRECTOR_NOTES = """Synthesize only the spoken transcript. Use these notes as performance guidance; do not read this instruction block aloud.

Style:
- Single-narrator audiobook lecture.
- Calm, literate, mildly warm, and authoritative.
- Clear, measured delivery with no casual podcast chatter, hype, or theatrical character acting.
- Slightly slower articulation through unfamiliar names, Hebrew and Latinized terms, sacred formulas, foreign-language titles, and dense typologies.
- Let section titles land as chapter-like transitions, with a clean pause before returning to the argument.

Pacing:
- Use a measured pace.
- Respect bracketed pause tags silently.
- Keep dense lists separated enough for a listener to follow without making the performance dramatic.

Pronunciation:
- Pronounce unfamiliar names and transliterations carefully and consistently.
- If a term is ambiguous, prefer a restrained scholarly reading over an exaggerated one.
"""


def load_environment() -> None:
    """Load repo env files without printing secrets."""
    env_files = [PROJECT_ROOT / ".env", PROJECT_ROOT / "app" / ".env"]
    if load_dotenv:
        for env_file in env_files:
            if env_file.exists():
                load_dotenv(env_file, override=False)
        return

    for env_file in env_files:
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_api_key() -> str:
    load_environment()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit("Missing GEMINI_API_KEY or GOOGLE_API_KEY in .env, app/.env, or shell environment.")
    return api_key


def slug_from_path(path: Path) -> str:
    slug = path.stem.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug.strip())
    return slug


def markdown_to_spoken_transcript(markdown: str) -> str:
    lines: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            lines.append("")
            continue

        if line.startswith("# "):
            title = line[2:].strip()
            lines.extend(["[medium pause]", title, "[medium pause]"])
            continue

        if line.startswith("## "):
            heading = line[3:].strip().strip('"')
            lines.extend(["", "[medium pause]", heading, "[medium pause]"])
            continue

        cleaned = line
        cleaned = re.sub(r"</?span[^>]*>", "", cleaned)
        cleaned = cleaned.replace("**", "")
        cleaned = cleaned.replace("__", "")
        cleaned = cleaned.replace("`", "")
        lines.append(cleaned)

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text + "\n"


def render_gemini(source: Path, output: Path, overwrite: bool) -> None:
    if output.exists() and not overwrite:
        raise SystemExit(f"Output exists; pass --overwrite to replace: {output}")

    markdown = source.read_text(encoding="utf-8")
    transcript = markdown_to_spoken_transcript(markdown)
    title = source.stem
    rendered = (
        f"# Gemini TTS Render: {title}\n\n"
        "### DIRECTOR'S NOTES\n\n"
        f"{DIRECTOR_NOTES.strip()}\n\n"
        "### TRANSCRIPT\n\n"
        f"{transcript}"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote Gemini render: {output}")


def parse_render(render_text: str) -> tuple[str, str]:
    marker = "### TRANSCRIPT"
    if marker not in render_text:
        return DIRECTOR_NOTES.strip(), render_text.strip()

    before, after = render_text.split(marker, 1)
    notes_marker = "### DIRECTOR'S NOTES"
    if notes_marker in before:
        notes = before.split(notes_marker, 1)[1].strip()
    else:
        notes = DIRECTOR_NOTES.strip()
    return notes, after.strip()


def words(text: str) -> list[str]:
    return re.findall(r"\S+", text)


def chunk_transcript(transcript: str, max_words: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", transcript) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for paragraph in paragraphs:
        count = len(words(paragraph))
        if current and current_words + count > max_words:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_words = count
        else:
            current.append(paragraph)
            current_words += count

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def build_prompt(notes: str, transcript_chunk: str) -> str:
    return (
        "Synthesize speech from the transcript below. "
        "Use DIRECTOR'S NOTES only as delivery guidance. "
        "Do not read labels, metadata, instructions, or Markdown syntax aloud. "
        "Read only the words in TRANSCRIPT, while treating bracketed pause tags as silent pacing cues.\n\n"
        "### DIRECTOR'S NOTES\n\n"
        f"{notes.strip()}\n\n"
        "### TRANSCRIPT\n\n"
        f"{transcript_chunk.strip()}\n"
    )


def call_gemini_tts(prompt: str, api_key: str, model: str, voice: str, timeout: int) -> bytes:
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice,
                    }
                }
            },
        },
        "model": model,
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini TTS HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Gemini TTS request failed: {exc}") from exc

    data = json.loads(body)
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])

    raise RuntimeError(f"Gemini TTS response did not include audio data: {json.dumps(data)[:1000]}")


def write_wav(path: Path, pcm: bytes) -> float:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(DEFAULT_CHANNELS)
        wav.setsampwidth(DEFAULT_SAMPLE_WIDTH)
        wav.setframerate(DEFAULT_SAMPLE_RATE)
        wav.writeframes(pcm)
        frames = len(pcm) // (DEFAULT_CHANNELS * DEFAULT_SAMPLE_WIDTH)
    return frames / DEFAULT_SAMPLE_RATE


def synthesize(
    input_path: Path,
    output_dir: Path,
    voice: str,
    model: str,
    chunk_words: int,
    start_chunk: int,
    max_chunks: int | None,
    overwrite: bool,
    retries: int,
    timeout: int,
) -> None:
    if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
        raise SystemExit(f"Output directory is not empty; pass --overwrite to replace files: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    render_text = input_path.read_text(encoding="utf-8")
    notes, transcript = parse_render(render_text)
    all_chunks = chunk_transcript(transcript, chunk_words)
    if start_chunk < 1:
        raise SystemExit("--start-chunk must be 1 or greater.")
    chunks = all_chunks[start_chunk - 1 :]
    if max_chunks is not None:
        chunks = chunks[:max_chunks]
    if not chunks:
        raise SystemExit("No transcript chunks found.")

    api_key = get_api_key()
    manifest = {
        "source": str(input_path),
        "model": model,
        "voice": voice,
        "chunk_words": chunk_words,
        "start_chunk": start_chunk,
        "total_available_chunks": len(all_chunks),
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "outputs": [],
    }

    for offset, chunk in enumerate(chunks):
        index = start_chunk + offset
        prompt = build_prompt(notes, chunk)
        chunk_name = f"chunk-{index:03d}.wav"
        chunk_path = output_dir / chunk_name
        last_error: Exception | None = None

        for attempt in range(1, retries + 2):
            try:
                print(f"Synthesizing {chunk_name} with {voice} ({len(words(chunk))} transcript words)...")
                pcm = call_gemini_tts(prompt, api_key, model, voice, timeout)
                duration = write_wav(chunk_path, pcm)
                manifest["outputs"].append(
                    {
                        "file": chunk_name,
                        "transcript_words": len(words(chunk)),
                        "prompt_chars": len(prompt),
                        "audio_bytes": len(pcm),
                        "duration_seconds": round(duration, 2),
                    }
                )
                break
            except Exception as exc:  # noqa: BLE001 - CLI should retry service failures.
                last_error = exc
                if attempt > retries:
                    raise
                wait = min(2**attempt, 10)
                print(f"Attempt {attempt} failed; retrying in {wait}s: {exc}", file=sys.stderr)
                time.sleep(wait)
        if last_error and not chunk_path.exists():
            raise last_error

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    total = sum(item["duration_seconds"] for item in manifest["outputs"])
    print(f"Wrote {len(manifest['outputs'])} audio chunk(s) to {output_dir}")
    print(f"Approximate generated duration: {total:.2f}s")
    print(f"Wrote manifest: {manifest_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    render_parser = subparsers.add_parser("render", help="Create a Gemini TTS render from a base audio script.")
    render_parser.add_argument("--script", required=True, type=Path, help="Base audio script markdown.")
    render_parser.add_argument("--output", type=Path, help="Gemini render output path.")
    render_parser.add_argument("--overwrite", action="store_true", help="Overwrite an existing render.")

    synth_parser = subparsers.add_parser("synthesize", help="Generate WAV chunks from a Gemini render.")
    synth_parser.add_argument("--input", required=True, type=Path, help="Gemini render markdown.")
    synth_parser.add_argument("--output-dir", type=Path, help="Directory for generated WAV files.")
    synth_parser.add_argument("--voice", default="Schedar", help="Gemini prebuilt voice name.")
    synth_parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini TTS model.")
    synth_parser.add_argument("--chunk-words", type=int, default=450, help="Approximate transcript words per chunk.")
    synth_parser.add_argument("--start-chunk", type=int, default=1, help="One-based chunk number to start from.")
    synth_parser.add_argument("--max-chunks", type=int, help="Limit generated chunks for samples.")
    synth_parser.add_argument("--overwrite", action="store_true", help="Allow writing into a non-empty output directory.")
    synth_parser.add_argument("--retries", type=int, default=2, help="Retries per chunk.")
    synth_parser.add_argument("--timeout", type=int, default=180, help="HTTP timeout in seconds.")

    args = parser.parse_args()
    if args.command == "render":
        source = args.script
        output = args.output
        if output is None:
            output = PROJECT_ROOT / "audio" / "tts" / "gemini" / f"{slug_from_path(source)}.md"
        render_gemini(source, output, args.overwrite)
    elif args.command == "synthesize":
        output_dir = args.output_dir
        if output_dir is None:
            output_dir = PROJECT_ROOT / "audio" / "output" / "gemini" / slug_from_path(args.input)
        synthesize(
            input_path=args.input,
            output_dir=output_dir,
            voice=args.voice,
            model=args.model,
            chunk_words=args.chunk_words,
            start_chunk=args.start_chunk,
            max_chunks=args.max_chunks,
            overwrite=args.overwrite,
            retries=args.retries,
            timeout=args.timeout,
        )


if __name__ == "__main__":
    main()
