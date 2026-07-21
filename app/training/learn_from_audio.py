# -*- coding: utf-8 -*-
"""
Usage: python -m app.training.learn_from_audio audio.m4a correct_text.txt [--update-rules]
"""
import json
import os
import re
import sys
from difflib import SequenceMatcher
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.services import transcription as transcription_v1
from app.services.word_timestamp_processor import process_segments
from app.services.subtitle_service import segments_to_text, WORD_REPLACEMENTS, KHMER_COMPOUNDS
from app.services.audio_service import convert_to_wav
from app.training.rule_extractor import add_pair

TEMP_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "temp")
os.makedirs(TEMP_DIR, exist_ok=True)


def run_stt(audio_path: str) -> str:
    wav_path = convert_to_wav(audio_path)
    result = transcription_v1.transcribe(wav_path)
    segments = process_segments(result.segments, wav_path)
    text = segments_to_text(segments)
    return text


def _norm(s: str) -> str:
    return re.sub(r'\s+', '', s)


def find_diffs(our_text: str, correct_text: str) -> list[dict]:
    """Compare our STT output with correct text, find meaningful errors."""
    our_stripped = _norm(our_text)
    correct_stripped = _norm(correct_text)
    our_words = our_text.split()

    matcher = SequenceMatcher(None, our_stripped, correct_stripped)
    diffs = []

    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op != "replace":
            continue
        bad_seq = our_stripped[i1:i2]
        good_seq = correct_stripped[j1:j2]
        if not bad_seq or not good_seq:
            continue
        if len(bad_seq) <= 1 and len(good_seq) <= 1:
            continue  # skip single-char noise

        # Find which STT words correspond to bad_seq
        bad_pos = our_text.find(bad_seq)
        if bad_pos < 0:
            continue

        # Find the word(s) containing bad_seq
        char_count = 0
        start_word_idx = None
        end_word_idx = None
        for idx, w in enumerate(our_words):
            word_start = char_count
            word_end = char_count + len(w)
            if bad_pos >= word_start and bad_pos < word_end:
                start_word_idx = idx
            if bad_pos + len(bad_seq) >= word_start and bad_pos + len(bad_seq) <= word_end:
                end_word_idx = idx
                break
            char_count += len(w)

        if start_word_idx is None:
            continue

        affected_words = our_words[start_word_idx:end_word_idx + 1] if end_word_idx else [our_words[start_word_idx]]
        affected_text = " ".join(affected_words)
        full_bad = "".join(affected_words)

        # Skip if bad_seq doesn't substantially appear in affected words
        if bad_seq not in full_bad and full_bad not in bad_seq:
            continue

        # Determine rule type
        if len(affected_words) == 1:
            rule_type = "WORD_REPLACEMENT"
            key = affected_words[0]
            value = good_seq
        else:
            rule_type = "COMPOUND"
            key = tuple(affected_words)
            value = good_seq

        # Check if already handled
        already_have = False
        if rule_type == "WORD_REPLACEMENT" and key in WORD_REPLACEMENTS:
            already_have = True
        elif rule_type == "COMPOUND":
            for a, b, c in KHMER_COMPOUNDS:
                if len(key) >= 2 and a == key[0] and b == key[1] and c == value:
                    already_have = True
                    break

        diffs.append({
            "bad_seq": bad_seq,
            "good_seq": good_seq,
            "affected_words": affected_words,
            "affected_text": affected_text,
            "rule_type": rule_type,
            "key": key,
            "value": value,
            "already_have": already_have,
        })

    return diffs


def generate_rule_text(diff: dict) -> str:
    if diff["already_have"]:
        return f'  # Already exists: {diff["affected_text"]} → {diff["value"]}'
    if diff["rule_type"] == "WORD_REPLACEMENT":
        return f'    "{diff["key"]}": "{diff["value"]}",'
    else:
        words = diff["key"]
        return f'    ("{words[0]}", "{words[1]}", "{diff["value"]}"),'


def show_report(our_text: str, correct_text: str, diffs: list[dict]) -> None:
    print("=" * 60)
    print("LEARNING REPORT")
    print("=" * 60)
    print()
    print("OUR STT OUTPUT:")
    print(f"  {our_text}")
    print()
    print("CORRECT TEXT:")
    print(f"  {correct_text}")
    print()
    print("DETECTED DIFFERENCES:")
    print()

    new_rules = 0
    existing_rules = 0
    for d in diffs:
        status = "✓ ALREADY FIXED" if d["already_have"] else "✗ NEW ERROR"
        print(f"  {status}")
        print(f"    Heard:   {d['affected_text']}")
        print(f"    Correct: {d['value']}")
        print(f"    Rule:    {d['rule_type']}: {generate_rule_text(d)}")
        print()
        if d["already_have"]:
            existing_rules += 1
        else:
            new_rules += 1

    print(f"Summary: {new_rules} new errors found, {existing_rules} already covered by rules")
    print()


def update_rules_file(diffs: list[dict]) -> None:
    path = os.path.join(os.path.dirname(__file__), "..", "services", "subtitle_service.py")
    with open(path, encoding="utf-8") as f:
        content = f.read()

    new_replacements = []
    new_compounds = []
    for d in diffs:
        if d["already_have"]:
            continue
        if d["rule_type"] == "WORD_REPLACEMENT":
            new_replacements.append((d["key"], d["value"]))
        else:
            words = d["key"]
            new_compounds.append((words[0], words[1], d["value"]))

    if new_replacements:
        repl_text = "\n".join(f'    "{k}": "{v}",' for k, v in new_replacements)
        insert_before = "\n}"  # end of WORD_REPLACEMENTS dict
        idx = content.rfind(insert_before)
        if idx > 0:
            content = content[:idx] + "\n" + repl_text + content[idx:]
            print(f"Inserted {len(new_replacements)} WORD_REPLACEMENTS")

    if new_compounds:
        comp_text = "\n".join(f'    ("{a}", "{b}", "{c}"),' for a, b, c in new_compounds)
        insert_before = "]"  # end of KHMER_COMPOUNDS list
        idx = content.rfind(insert_before, 0, content.rfind(insert_before))
        if idx > 0:
            content = content[:idx] + "\n" + comp_text + content[idx:]
            print(f"Inserted {len(new_compounds)} KHMER_COMPOUNDS")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _download_from_url(url: str) -> Optional[str]:
    """Download audio from URL. Supports direct audio files and YouTube."""
    import requests
    from urllib.parse import urlparse

    parsed = urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower()
    supported_exts = {".mp3", ".m4a", ".wav", ".ogg", ".mp4", ".webm"}

    # Direct audio file URL
    if ext in supported_exts:
        out_path = os.path.join(TEMP_DIR, f"url_audio{ext}")
        print(f"Downloading audio from {url}...")
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Downloaded to {out_path}")
        return out_path

    # YouTube or other site — try yt-dlp
    try:
        import yt_dlp

        out_path = os.path.join(TEMP_DIR, "%(id)s.%(ext)s")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": out_path,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}],
            "quiet": True,
        }
        print(f"Extracting audio from {url} using yt-dlp...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            audio_path = os.path.join(TEMP_DIR, f"{info['id']}.m4a")
        print(f"Extracted to {audio_path}")
        return audio_path
    except ImportError:
        print("yt-dlp not installed. Install with: pip install yt-dlp")
        return None
    except Exception as e:
        print(f"Failed to download from {url}: {e}")
        return None


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    source = sys.argv[1]
    text_path_or_text = sys.argv[2]
    update = "--update-rules" in sys.argv

    # Determine correct text: from file or inline
    if os.path.exists(text_path_or_text):
        with open(text_path_or_text, encoding="utf-8") as f:
            correct_text = f.read().strip()
        print(f"Loaded correct text from file ({len(correct_text)} chars)")
    else:
        correct_text = text_path_or_text.strip()
        print(f"Using inline correct text ({len(correct_text)} chars)")

    # Determine audio source: file or URL
    if source.startswith(("http://", "https://")):
        audio_path = _download_from_url(source)
        if not audio_path:
            print("Failed to get audio from URL.")
            sys.exit(1)
    elif os.path.exists(source):
        audio_path = source
    else:
        print(f"Source not found: {source}")
        sys.exit(1)

    print("Running STT...")
    our_text = run_stt(audio_path)
    add_pair(our_text, correct_text)

    diffs = find_diffs(our_text, correct_text)
    show_report(our_text, correct_text, diffs)

    if update and diffs:
        confirm = input("Apply these new rules? (y/N): ")
        if confirm.lower() == "y":
            update_rules_file(diffs)
            print("Rules updated. Restart the bot to apply.")
        else:
            print("Skipping rule update.")


if __name__ == "__main__":
    main()
