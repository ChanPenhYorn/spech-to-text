import base64
import subprocess
import time
from typing import Optional

import requests
from google.auth import default
from google.auth.transport.requests import Request as AuthRequest

from app.models.schemas import Segment, TranscriptionResult
from app.utils.file_utils import create_temp_file, cleanup_temp
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

_token: Optional[str] = None
_token_expiry: float = 0
CHUNK_DURATION = 59
RECOGNIZER_NAME = "projects/967729414303/locations/global/recognizers/khmer-test-latestlong"


def _get_bearer_token() -> str:
    global _token, _token_expiry
    if time.time() >= _token_expiry:
        credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        credentials.refresh(AuthRequest())
        _token = credentials.token
        _token_expiry = time.time() + 3000
    return _token


def _get_duration(audio_path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            audio_path,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return float(result.stdout.strip())


def _split_audio(audio_path: str, chunk_duration: int) -> list[tuple[float, str]]:
    duration = _get_duration(audio_path)
    chunks: list[tuple[float, str]] = []
    start = 0
    while start < duration:
        chunk_dur = min(chunk_duration, duration - start)
        output_path = create_temp_file(suffix=".wav")
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", audio_path,
                "-ss", str(start),
                "-t", str(chunk_dur),
                "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
                output_path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        chunks.append((start, output_path))
        start += chunk_duration
    return chunks


def _merge_subword_tokens(tokens: list[tuple[str, float, float]]) -> list[tuple[str, float, float]]:
    words: list[tuple[str, float, float]] = []
    current_word = ""
    current_start = 0.0
    current_end = 0.0

    for txt, st, et in tokens:
        if txt.startswith("▁"):
            if current_word:
                words.append((current_word, current_start, current_end))
            current_word = txt[1:]
            current_start = st
            current_end = et
        else:
            current_word += txt
            current_end = et

    if current_word:
        words.append((current_word, current_start, current_end))

    return words


def _transcribe_chunk(audio_path: str, time_offset: float, token: str) -> tuple[list[Segment], str, float]:
    logger.info("Reading audio chunk for V2: %s", audio_path)

    with open(audio_path, "rb") as f:
        content = f.read()

    encoded = base64.b64encode(content).decode("utf-8")

    body = {
        "config": {
            "explicit_decoding_config": {
                "encoding": "LINEAR16",
                "sample_rate_hertz": 16000,
                "audio_channel_count": 1,
            },
            "features": {"enable_word_time_offsets": True},
        },
        "content": encoded,
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }

    resp = requests.post(
        f"https://speech.googleapis.com/v2/{RECOGNIZER_NAME}:recognize",
        headers=headers,
        json=body,
        timeout=120,
    )

    resp.raise_for_status()
    response_data = resp.json()

    segments: list[Segment] = []
    detected_lang = "km"
    chunk_duration = 0.0

    for entry in response_data.get("results", []):
        alternative = entry["alternatives"][0]
        raw_words = alternative.get("words", [])

        if "languageCode" in entry:
            detected_lang = entry["languageCode"]

        if raw_words:
            tokens: list[tuple[str, float, float]] = []
            for w in raw_words:
                text = w.get("word", "").strip()
                if not text:
                    continue
                st = float(w.get("startOffset", "0s").rstrip("s"))
                et = float(w.get("endOffset", "0s").rstrip("s"))
                tokens.append((text, st, et))

            merged = _merge_subword_tokens(tokens)

            for word_text, word_start, word_end in merged:
                if not word_text.strip():
                    continue
                start = word_start + time_offset
                end = word_end + time_offset
                if end <= start:
                    end = start + 0.060
                segments.append(Segment(start=start, end=end, text=word_text))
                if end > chunk_duration:
                    chunk_duration = end
        else:
            seg_text = alternative.get("transcript", "").strip()
            if seg_text:
                segments.append(Segment(start=time_offset, end=time_offset, text=seg_text))

    return segments, detected_lang, chunk_duration


def transcribe(audio_path: str) -> TranscriptionResult:
    duration = _get_duration(audio_path)

    try:
        if duration > CHUNK_DURATION:
            logger.warning(
                "Audio duration %.2fs exceeds %ds. Splitting into chunks...",
                duration, CHUNK_DURATION,
            )
            temp_chunks = _split_audio(audio_path, CHUNK_DURATION)
        else:
            temp_chunks = [(0.0, audio_path)]

        token = _get_bearer_token()
        all_segments: list[Segment] = []
        detected_lang = "km"
        total_duration = 0.0

        for i, (chunk_start, chunk_path) in enumerate(temp_chunks):
            segs, lang, chunk_dur = _transcribe_chunk(chunk_path, chunk_start, token)
            all_segments.extend(segs)
            if lang != "km":
                detected_lang = lang
            if segs:
                last_end = segs[-1].end
                if last_end > total_duration:
                    total_duration = last_end
            logger.info("V2 Chunk %d/%d done: %d segments", i + 1, len(temp_chunks), len(segs))

        result = TranscriptionResult(
            language=detected_lang,
            segments=all_segments,
            duration=total_duration,
        )

        logger.info(
            "V2 Transcription complete: %d segments, language %s, duration %.2fs",
            len(all_segments), detected_lang, total_duration,
        )

        return result

    finally:
        for _, chunk_path in temp_chunks:
            if chunk_path != audio_path:
                cleanup_temp(chunk_path)
