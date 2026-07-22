from typing import Any

from app.models.schemas import Segment

MIN_DURATION = 0.060
ADJUSTMENT_MS = 5

WORD_REPLACEMENTS: dict[str, str] = {
    "ហ្វេសប៊ុក": "Facebook",
    "ហ្វេសប៊ុក្ក": "Facebook",
    "តុក្កតា": "TikTok",
    "សុខស្រីនាង": "សួស្ដី",
    "live": "like",
    "ឡាយ": "like",
    "ម៉ូត": "ប្រមូល",
    "អា": "",
    "អី": "",
    "apple": "App",
    "អែប": "App",
    "app": "App",
    "video": "វីដេអូ",
    "server": "Server",
    "អាំងស្តា": "Instagram",
    "យូធូប": "YouTube",
    "វ៉ាត់សាប": "WhatsApp",
    "តេឡេក្រាម": "Telegram",
    "ទូរសព្ទ": "ទូរស័ព្ទ",
    "កម្ដៅ": "ក៏",
    "ប្ដឹង": "ប្រែ",
    "ប៉ា": "តើ",
    "វីឌីអូ": "វីដេអូ",
    "តាណឹង": "ទេហ្នឹង",
    "ស្នេហ៍": "ស្នើ",
    "ប្រែ": "ប្រើ",
    "delet": "delete",
    "លោត": "លុប",
    "គណនេរ": "គណនី",
    "គណនេ": "គណនី",
    "សុវិល": "សេវា",
    "អ": "App",
    "លីត": "",
    "អាខោន": "account",
    "ស្នា": "ស្នើ",
    "ប្រេងសារ": "ប្រេងសាំង",
    "រុយ": "Reuters",
    "បង្អែក": "ពឹងផ្អែក",
    "អ្នកនាង": "អ្នកទាំងអស់គ្នា",
    "ណាសា": "NASA",
    "អូត្រា": "អ៊ុលត្រា",
    "សោម": "សោន",
    "follo": "Follow",
    "flo": "Follow",
    "ករុណា": "កក្កដា",
    "ជំរាបលា": "ជម្រាបលា",
    "ឱកាសញ្ញាណិក": "អវកាសយានិក",
    "ញ្ញាណិក": "យានិក",
    "ដីកា": "លិកា",
    "ឆ្អិន": "ឆ្អឹង",
    "google": "Google",
    "ais": "AI",
    "a.i": "AI",
    "eu": "EU",
    "android": "Android",
    "ai": "AI",

    "មេរៀន": "ែន",

}

FILLER_WORDS: set[str] = {"អា", "អី"}

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
    ("ការ", "ពិត", "ការពិត"),
    ("ការ", "លុប", "ការលុប"),
    ("ការ", "ប្រើ", "ការប្រើ"),
    ("ចែក", "រំលែក", "ចែករំលែក"),
    ("ជម្រាប", "លា", "ជម្រាបលា"),
    ("ស្វែង", "រក", "ស្វែងរក"),
    ("ទាំងអស់", "គ្នា", "ទាំងអស់គ្នា"),
    ("ខាង", "ក្រោម", "ខាងក្រោម"),
    ("មើល", "ទៅ", "មើលទៅ"),
    ("គេហ", "ទំព័រ", "គេហទំព័រ"),
    ("ព័ត៌", "មាន", "ព័ត៌មាន"),
    ("tik", "tok", "TikTok"),
    ("ជម្រាបលា", "បែក", "ជម្រាបលា Bye Bye"),
    ("សុខ", "ស្រីនាង", "សួស្ដី"),
    ("ពិត", "like", "like"),
    ("ពិត", "live", "like"),
    ("ពិត", "ឡាយ", "like"),
    ("នេះ", "ជាមួយ", "និយាយ ជាមួយ"),
    ("ទុក", "ទេ", "ទស្សន៍ទាយ"),
    ("ចាំ", "បន្តិច", "ចែករំលែក"),
    ("ចែករំលែក", "បន្តិច", "ចែករំលែកមតិយោបល់"),
    ("មួយ", "ចំនួន", "មួយចំនួន"),
    ("នៅ", "តែ", "នៅតែ"),
    ("បាន", "ជា", "បានជា"),
    ("ទោះ", "បី", "ទោះបី"),
    ("ចេញ", "ពី", "ចេញពី"),
    ("ទៅ", "ជា", "ទៅជា"),
    ("មុន", "ពេល", "មុនពេល"),
    ("លើក", "ក្រោយ", "លើកក្រោយ"),
    ("ទាំង", "ស្រុង", "ទាំងស្រុង"),
    ("ពិនិត្យ", "មើល", "ពិនិត្យមើល"),
    ("ប្រើ", "សេវាកម្ម", "ប្រើប្រាស់សេវាកម្ម"),
    ("ឈប់", "ប្រើ", "ឈប់ប្រើ"),
    ("រក្សា", "ទុក", "រក្សាទុក"),
    ("លុប", "ចេញ", "លុបចេញ"),
    ("លុប", "ចោល", "លុបចោល"),
    ("មាន", "ន័យ", "មានន័យ"),
    ("ណា", "មួយ", "ណាមួយ"),
    ("តាម", "រយៈ", "តាមរយៈ"),
    ("ធ្លាប់", "ដឹង", "ធ្លាប់ដឹង"),
    ("របស់", "អ្នក", "របស់អ្នក"),
    ("ចូល", "ទៅ", "ចូលទៅ"),
    ("សូម", "ពិនិត្យ", "សូមពិនិត្យ"),
    ("ស្នើ", "សុំ", "ស្នើសុំ"),
    ("គួរ", "តែ", "គួរតែ"),
    ("ទាំងអស់គ្នា", "ទាំងអស់គ្នា", "ទាំងអស់គ្នា"),
    ("មើល", "តិច", "បន្តិច"),
    ("ព័ត៌មាន", "ទាំងស្រុង", "ព័ត៌មានទាំងអស់"),
    ("ការ", "សន្យា", "ការសន្យា"),
    ("ការ", "ផ្សព្វផ្សាយ", "ការផ្សព្វផ្សាយ"),
    ("ប៉ុន្តែ", "ការ", "ប៉ុន្តែការ"),
    ("ធ្វើ", "ការងារ", "ធ្វើការងារ"),
    ("រក", "ប្រាក់", "រកប្រាក់"),
    ("ផ្តល់", "ប្រាក់", "ផ្តល់ប្រាក់"),
    ("បទ", "ពិសោធន៍", "បទពិសោធន៍"),
    ("សង្គម", "គ្រួសារ", "សង្គម"),
    ("ព័ត៌មាន", "ផ្ទាល់ខ្លួន", "ព័ត៌មានផ្ទាល់ខ្លួន"),
    ("ផ្សព្វផ្សាយ", "ការងារ", "ផ្សព្វផ្សាយការងារ"),
    ("ទទួល", "យក", "ទទួលយក"),
    ("ន", "ដែរ", "នោះដែរ"),
    ("ច", "លុប", "លុប"),
    ("ចង់", "លុប", "ចង់លុប"),
    ("អស់", "នេះ", "អស់គ្នា"),
    ("ដែល", "account", "delete account"),
    ("ថា", "តែ", "ថាតើ"),
    ("ទាំងអស់", "នេះ", "ទាំងអស់គ្នា"),
    ("មិនដែល", "សង្គម", "បណ្ដាញសង្គម"),
    ("មិន", "ដែល", "មិនដែល"),
    ("ជម្រាបលា", "បាយ", "ជម្រាបលា"),
    ("គួរតែ", "សង្ស័យ", "គួរឱ្យសង្ស័យ"),
    ("តែ", "អ្នក", "តើអ្នក"),
    ("ប៉", "ដល់", "ប៉ះពាល់ដល់"),
    ("ឡាន", "ថ្លៃ", "ឡើងថ្លៃ"),
    ("ជ្រាប", "លា", "ជម្រាបលា"),
    ("ទៅ", "ជួយ", "ភ្លេចជួយ"),
    ("ខំ", "មិន", "Comment"),
    ("ភ្លេចជួយ", "Comment", "ភ្លេចជួយComment"),
    ("រយ", "តើស", "Reuters"),
    ("ការ", "ភាគី", "ការភាគី"),
    ("អ៊ុលត្រា", "សោន", "Ultrasound"),
    ("ឆ្អឹង", "ខ្ចី", "ឆ្អឹងខ្ចី"),
    ("អវកាស", "យានិក", "អវកាសយានិក"),
    ("ជា", "លិកា", "ជាលិកា"),
    ("ពួក", "គេ", "ពួកគេ"),
    ("ម្សិល", "មិញ", "ម្សិលមិញ"),
    ("ថ្មី", "ៗ", "ថ្មីៗ"),
    ("ឆាប់", "ៗ", "ឆាប់ៗ"),
    ("ទទួល", "បាន", "ទទួលបាន"),
    ("6", "engine", "Search Engine"),

    ("ហ្នឹង", "ខ្ញុំ", "នេះ"),
    ("ប្រាំបាបសាយ", "ដើម្បី", "អឺ៥វេបសាយAI"),
    ("ទាំងអស់គ្នា", "ថ្ងៃ", "ជូនអ្នកទាំងអស់គ្នាអឺ"),

]


def replace_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not words:
        return []
    result = []
    for w in words:
        out = dict(w)
        replacement = WORD_REPLACEMENTS.get(out["word"])
        if replacement is not None:
            if replacement == "":
                continue
            out["word"] = replacement
        result.append(out)
    return result


def merge_khmer_compounds(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not words:
        return []

    result = list(words)
    changed = True
    while changed:
        changed = False
        merged: list[dict[str, Any]] = []
        i = 0
        while i < len(result):
            current = result[i]
            matched = False
            for first, second, compound in KHMER_COMPOUNDS:
                if current["word"] == first and i + 1 < len(result) and result[i + 1]["word"] == second:
                    merged.append({
                        "word": compound,
                        "start": current["start"],
                        "end": result[i + 1]["end"],
                    })
                    i += 2
                    matched = True
                    changed = True
                    break
            if not matched:
                merged.append(current)
                i += 1
        result = merged

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
