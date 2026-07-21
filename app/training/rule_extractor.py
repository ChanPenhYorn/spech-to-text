import json
import os
import re
from difflib import SequenceMatcher

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "pairs.jsonl")
os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)


def add_pair(stt_text: str, correct_text: str) -> None:
    with open(DATA_PATH, "a") as f:
        f.write(json.dumps({"input": stt_text, "output": correct_text}, ensure_ascii=False) + "\n")


def load_pairs() -> list[dict[str, str]]:
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def _norm(s: str) -> str:
    return re.sub(r'\s+', '', s)


def _extract_diffs(input_stripped: str, output_stripped: str) -> list[tuple[int, int, int, int]]:
    matcher = SequenceMatcher(None, input_stripped, output_stripped)
    return [op for op in matcher.get_opcodes() if op[0] == 'replace']


def auto_extract_rules(stt_text: str, correct_text: str) -> tuple[dict[str, str], list[tuple[str, str, str]]]:
    raw = _norm(stt_text)
    corr = _norm(correct_text)
    word_replacements = {}
    compounds = []

    diffs = _extract_diffs(raw, corr)
    for op, i1, i2, j1, j2 in diffs:
        bad_seq = raw[i1:i2]
        good_seq = corr[j1:j2]
        if not bad_seq or not good_seq or len(bad_seq) > 15 or len(good_seq) > 15:
            continue
        if bad_seq not in stt_text or good_seq not in corr:
            continue

        # Match bad_seq to STT words
        stt_words = stt_text.split()
        matched_words = [w for w in stt_words if bad_seq in w or re.match(re.escape(bad_seq), w)]
        for w in matched_words:
            if w != good_seq and len(w) > 1:
                word_replacements[w] = good_seq

        # Check if bad_seq spans multiple words
        if bad_seq:
            span = []
            remaining = bad_seq
            for w in stt_words:
                if w in remaining:
                    span.append(w)
                    remaining = remaining.replace(w, '', 1)
                elif remaining.startswith(w[:2]):
                    span.append(w)
                    remaining = remaining[len(w):]
                if not remaining:
                    break
            if len(span) >= 2 and ''.join(span) == bad_seq:
                for i in range(len(span) - 1):
                    compounds.append((span[i], span[i + 1], good_seq))

    return word_replacements, compounds


def show_stats() -> None:
    pairs = load_pairs()
    if not pairs:
        print("No training data yet.")
        return
    print(f"Collected {len(pairs)} pairs")
    all_replacements = {}
    all_compounds = set()
    for p in pairs:
        repl, comp = auto_extract_rules(p["input"], p["output"])
        all_replacements.update(repl)
        all_compounds.update(comp)
    print(f"Auto-extracted {len(all_replacements)} word replacements:")
    for k, v in sorted(all_replacements.items()):
        print(f'  "{k}" → "{v}"')
    print(f"Auto-extracted {len(all_compounds)} compounds:")
    for a, b, c in sorted(all_compounds):
        print(f'  "{a}" + "{b}" → "{c}"')