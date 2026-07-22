from typing import Any, Optional

from app.models.schemas import Segment
from app.services.subtitle_service import merge_khmer_compounds, replace_words

MIN_DURATION = 0.060


def _to_word_dicts(segments: list[Segment]) -> list[dict[str, Any]]:
    return [{"word": s.text, "start": s.start, "end": s.end} for s in segments]


def _from_word_dicts(words: list[dict[str, Any]]) -> list[Segment]:
    return [Segment(start=w["start"], end=w["end"], text=w["word"]) for w in words]


def _normalize_word_timestamps(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not words:
        return []

    result = []
    prev_end = 0.0

    for w in words:
        start = max(float(w["start"]), prev_end)
        end = float(w["end"])

        if end < start:
            end = start

        if end - start < MIN_DURATION:
            end = start + MIN_DURATION

        prev_end = end

        out = dict(w)
        out["start"] = start
        out["end"] = end
        result.append(out)

    return result


def process_segments(
    segments: list[Segment],
    audio_path: Optional[str] = None,
) -> list[Segment]:
    if not segments:
        return []

    words = _to_word_dicts(segments)

    words = _normalize_word_timestamps(words)

    words = replace_words(words)

    words = merge_khmer_compounds(words)

    words = replace_words(words)

    return _from_word_dicts(words)
