from typing import Any

from app.models.schemas import Segment

MIN_DURATION = 0.060
ADJUSTMENT_MS = 5

KHMER_COMPOUNDS: list[tuple[str, str, str]] = [
    ("ពាណិជ្ជ", "កម្ម", "ពាណិជ្ជកម្ម"),
    ("នៅ", "លើ", "នៅលើ"),
    ("ទាំង", "អស់", "ទាំងអស់"),
    ("កំពុង", "តែ", "កំពុងតែ"),
    ("ជា", "ច្រើន", "ជាច្រើន"),
    ("ពី", "មុន", "ពីមុន"),
    ("កើត", "ឡើង", "កើតឡើង"),
    ("ដោយ", "សារ", "ដោយសារ"),
    ("ដូច", "ជា", "ដូចជា"),
    ("ចាប់", "អារម្មណ៍", "ចាប់អារម្មណ៍"),
    ("ជា", "ទូទៅ", "ជាទូទៅ"),
    ("ការ", "សន្ទនា", "ការសន្ទនា"),
    ("ការ", "បង្ហាញ", "ការបង្ហាញ"),
    ("ការ", "ស្វែងរក", "ការស្វែងរក"),
    ("ការ", "ចុច", "ការចុច"),
    ("ការ", "មើល", "ការមើល"),
    ("ចែក", "រំលែក", "ចែករំលែក"),
    ("ជម្រាប", "លា", "ជម្រាបលា"),
    ("ស្វែង", "រក", "ស្វែងរក"),
    ("ទាំងអស់", "គ្នា", "ទាំងអស់គ្នា"),
    ("ខាង", "ក្រោម", "ខាងក្រោម"),
    ("មើល", "ទៅ", "មើលទៅ"),
    ("គេហ", "ទំព័រ", "គេហទំព័រ"),
    ("ព័ត៌", "មាន", "ព័ត៌មាន"),
]


def merge_khmer_compounds(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not words:
        return []

    result: list[dict[str, Any]] = []
    i = 0
    while i < len(words):
        current = words[i]
        merged = False

        for first, second, compound in KHMER_COMPOUNDS:
            if current["word"] == first and i + 1 < len(words) and words[i + 1]["word"] == second:
                merged_word = {
                    "word": compound,
                    "start": current["start"],
                    "end": words[i + 1]["end"],
                }
                result.append(merged_word)
                i += 2
                merged = True
                break

        if not merged:
            result.append(current)
            i += 1

    return result


def format_timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


_format_timestamp = format_timestamp


def validate_word(word: dict[str, Any]) -> tuple[bool, str]:
    text = word.get("word", "").strip()
    if not text:
        return False, "empty"
    if not text.strip():
        return False, "whitespace"
    start = word.get("start")
    end = word.get("end")
    if start is None or end is None:
        return False, "missing_timestamp"
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        return False, "corrupted_timestamp"
    return True, ""


def normalize_timestamps(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
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

        if start < prev_end:
            start = prev_end
            if end <= start:
                end = start + ADJUSTMENT_MS / 1000

        prev_end = end

        out = dict(w)
        out["start"] = start
        out["end"] = end
        result.append(out)

    return result


def generate_word_srt(words: list[dict[str, Any]]) -> str:
    valid = []
    for w in words:
        ok, _ = validate_word(w)
        if ok:
            valid.append(w)

    if not valid:
        return ""

    valid = normalize_timestamps(valid)

    lines: list[str] = []
    for i, w in enumerate(valid, start=1):
        start_ts = format_timestamp(w["start"])
        end_ts = format_timestamp(w["end"])
        text = w.get("word", "").strip()
        lines.append(str(i))
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


def save_srt(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def segments_to_text(segments: list[Segment]) -> str:
    return " ".join(seg.text for seg in segments)


def segments_to_srt(segments: list[Segment]) -> str:
    raw = [{"word": s.text, "start": s.start, "end": s.end} for s in segments]
    raw = merge_khmer_compounds(raw)
    return generate_word_srt(raw)


def segments_to_vtt(segments: list[Segment]) -> str:
    lines = ["WEBVTT", ""]
    for seg in segments:
        start_ts = format_timestamp(seg.start).replace(",", ".")
        end_ts = format_timestamp(seg.end).replace(",", ".")
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)
