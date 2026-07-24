import time
import subprocess
from typing import Optional

from faster_whisper import WhisperModel

from app.models.schemas import Segment, TranscriptionResult
from app.utils.file_utils import create_temp_file, cleanup_temp
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

CHUNK_DURATION = 600

_model: Optional[WhisperModel] = None


def _get_model():
    global _model
    if _model is None:
        logger.info("Loading Whisper Khmer model (faster-whisper)...")
        t0 = time.time()
        _model = WhisperModel(
            "PhanithLIM/whisper-small-khmer-ct2",
            device="cpu",
            compute_type="int8",
        )
        logger.info("Whisper Khmer model loaded in %.1fs", time.time() - t0)
    return _model


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


def transcribe(audio_path: str) -> TranscriptionResult:
    model = _get_model()
    duration = _get_duration(audio_path)

    logger.info("Transcribing with Whisper Khmer (duration=%.1fs)...", duration)
    t0 = time.time()

    segments_generator, info = model.transcribe(
        audio_path,
        language="km",
        task="transcribe",
        beam_size=1,
        vad_filter=False,
    )

    all_segments: list[Segment] = []
    for seg in segments_generator:
        text = seg.text.strip()
        if not text:
            continue
        all_segments.append(Segment(start=seg.start, end=seg.end, text=text))

    elapsed = time.time() - t0

    result = TranscriptionResult(
        language=info.language if info else "km",
        segments=all_segments,
        duration=duration,
    )
    logger.info(
        "Transcription complete: %d segments, language %s, %.1fs audio in %.1fs",
        len(all_segments), result.language, duration, elapsed,
    )
    return result
