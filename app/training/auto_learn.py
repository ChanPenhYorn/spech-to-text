# -*- coding: utf-8 -*-
"""
Fully automated learning system:
1. Auto-extract rules from (STT, correct) pairs
2. Auto-update subtitle_service.py
3. Auto-restart bot
4. Background scraper for YouTube Khmer content
"""
import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

logger = logging.getLogger(__name__)

BOT_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "main.py")
SERVICE_PATH = os.path.join(os.path.dirname(__file__), "..", "services", "subtitle_service.py")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "pairs.jsonl")


def _read_pairs() -> list[dict]:
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def _exists_in_file(content: str, entry: str) -> bool:
    """Check if an entry already exists in the file content."""
    return entry in content


def _inject_into_content(content: str, marker: str, open_char: str, close_char: str, new_entries: list[str]) -> str:
    """Inject new entries into a dict or list before its closing bracket."""
    start = content.find(marker)
    if start < 0:
        return content
    
    # Find '=' after marker, then find the first open_char after '='
    eq_pos = content.find("=", start)
    if eq_pos < 0:
        return content
    
    literal_start = content.find(open_char, eq_pos)
    if literal_start < 0:
        return content
    
    # Find the matching closing bracket from literal_start
    depth = 0
    close_pos = None
    for i in range(literal_start, len(content)):
        c = content[i]
        if c == open_char:
            depth += 1
        elif c == close_char:
            depth -= 1
            if depth == 0:
                close_pos = i
                break
    
    if close_pos is None:
        return content
    
    # Find the last newline before close_pos (insert before close)
    insert_pos = content.rfind("\n", literal_start, close_pos)
    if insert_pos < 0:
        insert_pos = close_pos
    
    entries_text = "\n".join(f"    {e}" for e in new_entries)
    if entries_text:
        entries_text = "\n" + entries_text + "\n"
    
    return content[:insert_pos] + entries_text + content[insert_pos:]


def apply_rules(new_replacements: dict, new_compounds: list[tuple]) -> bool:
    """Update subtitle_service.py with new rules."""
    try:
        with open(SERVICE_PATH, encoding="utf-8") as f:
            content = f.read()
        
        repl_entries = []
        for k, v in new_replacements.items():
            entry = f'"{k}": "{v}"'
            if not _exists_in_file(content, entry):
                repl_entries.append(f'"{k}": "{v}",')
        
        comp_entries = []
        for c in new_compounds:
            if len(c) == 3:
                entry = f'("{c[0]}", "{c[1]}", "{c[2]}")'
                if not _exists_in_file(content, entry):
                    comp_entries.append(f'("{c[0]}", "{c[1]}", "{c[2]}"),')
        
        if repl_entries:
            content = _inject_into_content(content, "WORD_REPLACEMENTS", "{", "}", repl_entries)
        
        if comp_entries:
            content = _inject_into_content(content, "KHMER_COMPOUNDS", "[", "]", comp_entries)
        
        if repl_entries or comp_entries:
            with open(SERVICE_PATH, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("Injected %d replacements, %d compounds", len(repl_entries), len(comp_entries))
        
        return True
    except Exception as e:
        logger.error("Failed to apply rules: %s", e)
        return False


def restart_bot() -> None:
    """Restart the bot process."""
    logger.info("Restarting bot...")
    os.chdir(os.path.dirname(BOT_SCRIPT))
    os.execvp("python", ["python", "-m", "app.main"])


async def auto_learn_from_pairs() -> tuple[int, int]:
    """Auto-extract and apply rules from all accumulated pairs."""
    from app.training.rule_extractor import auto_extract_rules
    pairs = _read_pairs()
    if not pairs:
        return 0, 0
    
    all_repl = {}
    all_comp = set()
    for p in pairs:
        repl, comp = auto_extract_rules(p["input"], p["output"])
        all_repl.update(repl)
        all_comp.update(comp)
    
    if all_repl or all_comp:
        if apply_rules(all_repl, list(all_comp)):
            return len(all_repl), len(all_comp)
    return 0, 0


async def auto_train_model() -> bool:
    """Auto-train the Qwen model if enough pairs exist."""
    pairs = _read_pairs()
    if len(pairs) < 5:
        logger.info("Not enough pairs for training (%d < 5)", len(pairs))
        return False
    
    try:
        from app.training.train_model import train
        train()
        return True
    except Exception as e:
        logger.error("Auto-train failed: %s", e)
        return False


async def scrape_youtube_channel(channel_url: str, max_videos: int = 3) -> int:
    """Auto-scrape a YouTube channel for Khmer videos with captions."""
    import yt_dlp
    
    learned = 0
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            entries = info.get("entries", [])[:max_videos]
        
        for entry in entries:
            video_url = f"https://youtube.com/watch?v={entry['id']}"
            logger.info("Processing: %s", entry.get("title", video_url))
            
            result = await _process_youtube_video(video_url)
            if result:
                learned += 1
    
    except Exception as e:
        logger.error("Scrape failed: %s", e)
    
    return learned


async def _process_youtube_video(url: str) -> bool:
    """Process a single YouTube video: download audio + captions, compare, learn."""
    import yt_dlp
    import webvtt
    from app.services.audio_service import convert_to_wav
    from app.services import transcription as transcription_v1
    from app.services.word_timestamp_processor import process_segments
    from app.services.subtitle_service import segments_to_text
    from app.training.learn_from_audio import find_diffs
    from app.training.rule_extractor import add_pair, auto_extract_rules
    
    temp_dir = os.path.join(os.path.dirname(__file__), "..", "..", "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    out_template = os.path.join(temp_dir, "%(id)s.%(ext)s")
    
    with yt_dlp.YoutubeDL({
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}],
        "writesubtitles": True,
        "subtitleslangs": ["km"],
        "writeautomaticsub": False,
        "quiet": True,
    }) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info["id"]
    
    audio_path = os.path.join(temp_dir, f"{video_id}.m4a")
    subs_path = os.path.join(temp_dir, f"{video_id}.km.vtt")
    
    if not os.path.exists(audio_path) or not os.path.exists(subs_path):
        return False
    
    captions = webvtt.read(subs_path)
    correct_text = " ".join(c.text.replace("\n", " ").strip() for c in captions)
    
    wav_path = convert_to_wav(audio_path)
    result = transcription_v1.transcribe(wav_path)
    segments = process_segments(result.segments, wav_path)
    our_text = segments_to_text(segments)
    
    add_pair(our_text, correct_text)
    
    repl, comp = auto_extract_rules(our_text, correct_text)
    if repl or comp:
        return apply_rules(repl, comp)
    
    return True
