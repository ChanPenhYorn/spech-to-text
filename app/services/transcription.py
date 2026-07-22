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
CHUNK_DURATION = 15
CHUNK_OVERLAP = 2


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


def _split_audio(audio_path: str, chunk_duration: int) -> list[tuple[float, float, str]]:
    duration = _get_duration(audio_path)
    chunks: list[tuple[float, float, str]] = []
    official_start = 0

    while official_start < duration:
        actual_start = max(0, official_start - CHUNK_OVERLAP)
        chunk_end = min(duration, official_start + chunk_duration + CHUNK_OVERLAP)
        chunk_len = chunk_end - actual_start
        output_path = create_temp_file(suffix=".wav")
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", audio_path,
                "-ss", str(actual_start),
                "-t", str(chunk_len),
                "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
                output_path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        chunks.append((official_start, actual_start, output_path))
        official_start += chunk_duration

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
            "model": "latest_short",
            "speechContexts": [{
                "phrases": [
                    "ទូរស័ព្ទ", "ទិន្នន័យ", "គណនី", "លុប",
                    "App", "server", "delete account",
                    "ព័ត៌មាន", "សេវាកម្ម", "ក្រុមហ៊ុន",
                    "ចែករំលែក", "មុខងារ", "តាមរយៈ",
                    "ទាំងស្រុង", "មួយចំនួន", "រក្សាទុក",
                    "លុបចោល", "លុបចេញ", "ធ្លាប់",
                    "ទូរសព្ទ", "ធម្មតា", "ប្រើ",
                    "សន្យា", "បណ្ដាញ", "សង្គម", "បណ្ដាញសង្គម",
                    "សង្ស័យ", "គួរឲ្យ", "ប្រាក់ខែ",
                    "អញ្ចឹង", "ការពិត", "និង",
                    "ChatGPT", "Canva AI", "Google Gemini",
                    "Perplexity AI", "CapCut", "Subtitle",
                    "Effect", "content creator", "designer",
                    "Bye bye", "Follow",
                ],
                "boost": 10,
            }],
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
        if "languageCode" in entry:
            detected_lang = entry["languageCode"]

        raw_words = alternative.get("words", [])
        if raw_words:
            raw_tokens: list[tuple[str, float, float]] = []
            for w in raw_words:
                text = w.get("word", "").strip()
                if not text:
                    continue
                start = _duration_to_seconds(w["startTime"]) + time_offset
                end = _duration_to_seconds(w["endTime"]) + time_offset
                if end <= start:
                    end = start + 0.060
                raw_tokens.append((text, start, end))
                if end > chunk_duration:
                    chunk_duration = end

            merged = _merge_subword_tokens(raw_tokens)
            for text, start, end in merged:
                segments.append(Segment(start=start, end=end, text=text))
        else:
            seg_text = alternative.get("transcript", "").strip()
            if seg_text:
                segments.append(Segment(start=time_offset, end=time_offset, text=seg_text))

    return segments, detected_lang, chunk_duration


def _transcribe_tail(audio_path: str, from_time: float, duration: float, token: str) -> list[Segment]:
    tail_path = create_temp_file(suffix=".wav")
    try:
        tail_len = duration - from_time
        subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path, "-ss", str(from_time), "-t", str(tail_len),
             "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", tail_path],
            capture_output=True, text=True, timeout=60,
        )
        segs, _, _ = _transcribe_chunk(tail_path, from_time, token)
        return segs
    finally:
        cleanup_temp(tail_path)


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
            temp_chunks = [(0.0, 0.0, audio_path)]

        token = _get_bearer_token()
        all_segments: list[Segment] = []
        detected_lang = "km"
        total_duration = 0.0

        prev_last_end = 0.0
        for i, (chunk_start, actual_start, chunk_path) in enumerate(temp_chunks):
            segs, lang, chunk_dur = _transcribe_chunk(chunk_path, actual_start, token)
            if i > 0:
                segs = [s for s in segs if s.start >= prev_last_end]
            all_segments.extend(segs)
            if lang != "km":
                detected_lang = lang
            if segs:
                last_end = segs[-1].end
                prev_last_end = max(prev_last_end, last_end)
                if last_end > total_duration:
                    total_duration = last_end
            logger.info("Chunk %d/%d done: %d segments", i + 1, len(temp_chunks), len(segs))

        if total_duration < duration - 2:
            tail_start = total_duration - CHUNK_OVERLAP
            logger.info("Audio tail missing (%.1fs of %.1fs). Retranscribing tail from %.1fs...",
                        total_duration, duration, tail_start)
            tail_segs = _transcribe_tail(audio_path, max(0, tail_start), duration, token)
            tail_segs = [s for s in tail_segs if s.start >= total_duration]
            if tail_segs:
                all_segments.extend(tail_segs)
                total_duration = max(total_duration, tail_segs[-1].end)
                logger.info("Tail transcription added %d segments, new duration %.1fs",
                            len(tail_segs), total_duration)

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
        for entry in temp_chunks:
            chunk_path = entry[2] if len(entry) == 3 else entry[1]
            if chunk_path != audio_path:
                cleanup_temp(chunk_path)
