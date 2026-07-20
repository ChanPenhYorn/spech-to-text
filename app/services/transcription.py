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


def _duration_to_seconds(t) -> float:
    if isinstance(t, dict):
        return t.get("seconds", 0) + t.get("nanos", 0) / 1e9
    s = str(t).rstrip("s")
    return float(s)


def _transcribe_chunk(audio_path: str, time_offset: float, token: str) -> tuple[list[Segment], str, float]:
    logger.info("Reading audio chunk: %s", audio_path)
    with open(audio_path, "rb") as f:
        content = f.read()

    encoded = base64.b64encode(content).decode("utf-8")

    # Try synchronous recognize first (faster for chunks)
    body = {
        "config": {
            "encoding": "LINEAR16",
            "sampleRateHertz": 16000,
            "languageCode": "km-KH",
            "alternativeLanguageCodes": ["en-US"],
            "enableWordTimeOffsets": True,
            "enableAutomaticPunctuation": True,
        },
        "audio": {"content": encoded},
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }

    resp = requests.post(
        "https://speech.googleapis.com/v1/speech:recognize",
        headers=headers,
        json=body,
        timeout=120,
    )

    if resp.status_code == 400 and "duration" in resp.text.lower():
        logger.warning("Chunk too long for sync API, using longrunning...")
        resp = requests.post(
            "https://speech.googleapis.com/v1/speech:longrunningrecognize",
            headers=headers,
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        operation = resp.json()
        operation_name = operation["name"]

        while True:
            time.sleep(2)
            status_resp = requests.get(
                f"https://speech.googleapis.com/v1/operations/{operation_name}",
                headers=headers,
                timeout=30,
            )
            status_resp.raise_for_status()
            status = status_resp.json()
            if status.get("done"):
                break

        if "error" in status:
            raise RuntimeError(f"Google STT error: {status['error']}")

        response_data = status.get("response", {})
    else:
        resp.raise_for_status()
        response_data = resp.json()

    segments: list[Segment] = []
    detected_lang = "km"
    chunk_duration = 0.0

    for entry in response_data.get("results", []):
        alternative = entry["alternatives"][0]
        words = alternative.get("words", [])

        if "languageCode" in entry:
            detected_lang = entry["languageCode"]

        if words:
            for w in words:
                text = w.get("word", "").strip()
                if not text:
                    continue
                start = _duration_to_seconds(w["startTime"]) + time_offset
                end = _duration_to_seconds(w["endTime"]) + time_offset
                if end <= start:
                    end = start + 0.060
                segments.append(Segment(start=start, end=end, text=text))
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
            logger.info("Chunk %d/%d done: %d segments", i + 1, len(temp_chunks), len(segs))

        result = TranscriptionResult(
            language=detected_lang,
            segments=all_segments,
            duration=total_duration,
        )

        logger.info(
            "Transcription complete: %d segments, language %s, duration %.2fs",
            len(all_segments), detected_lang, total_duration,
        )

        return result

    finally:
        for _, chunk_path in temp_chunks:
            if chunk_path != audio_path:
                cleanup_temp(chunk_path)
