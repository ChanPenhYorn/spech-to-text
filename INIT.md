# Speech-to-Text Khmer Bot — Project Init

## Overview
Telegram bot that transcribes Khmer audio using Google STT V1 (`latest_short` model) with rule-based post-processing and auto-learning pipeline.

## Architecture

### Pipeline
```
Audio (.m4a/.mp3/.wav/.ogg)
  → Google STT latest_short (15s chunks, 2s overlap, subword token merging)
  → replace_words() — 35+ WORD_REPLACEMENTS (single-word error fixes)
  → merge_khmer_compounds() — 90+ KHMER_COMPOUNDS (multi-pass until stable)
  → SRT + plain text output
```

### Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | Bot entry point, command registration |
| `app/bot/handlers.py` | Telegram handlers: /start, /v1, /v2, /v3, /learn, /learn_yt |
| `app/services/transcription.py` | V1 engine: Google STT latest_short, chunking, overlap dedup |
| `app/services/subtitle_service.py` | WORD_REPLACEMENTS (dict) + KHMER_COMPOUNDS (list) + merge logic |
| `app/services/word_timestamp_processor.py` | Orchestrates replace_words → merge_khmer_compounds |
| `app/services/llm_correction.py` | LLM correction (OpenRouter/DeepSeek/Gemini/Ollama) — currently disabled |
| `app/services/learner.py` | Loads fine-tuned Qwen2.5-0.5B model for correction |
| `app/training/rule_extractor.py` | Auto-extracts WORD_REPLACEMENTS + COMPOUNDS from (STT, correct) pairs |
| `app/training/learn_from_audio.py` | CLI tool: compare audio STT vs correct text, show/report diffs |
| `app/training/auto_learn.py` | Auto-apply rules to subtitle_service.py + auto-restart |
| `app/training/train_model.py` | LoRA fine-tune Qwen2.5-0.5B on collected pairs |
| `app/training/seed_data.py` | Seed initial training pairs |
| `app/training/auto_scheduler.py` | Periodic YouTube scraper + auto-learn |
| `app/run.py` | Combined launcher (bot + background scheduler) |

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome + engine info |
| `/v1` | Google STT standard (default — best quality) |
| `/v2` | Google STT latest_long |
| `/v3` | Whisper Khmer (experimental, broken) |
| `/learn <correct text>` | After sending audio, provide correct text → auto-extracts rules + restarts |
| `/learn_yt <YouTube URL>` | Download audio + Khmer captions → compare → auto-learn + restart |

## STT Engine Details

### V1 (Default)
- `model: latest_short` — significantly more accurate than default
- `CHUNK_DURATION=15` seconds, `CHUNK_OVERLAP=2` seconds
- `_merge_subword_tokens()` — merges SentencePiece `▁` prefixed tokens
- Overlap dedup: skip words with `start < prev_last_end`
- Audio: ffmpeg conversion to 16kHz mono WAV (no loudnorm — caused regressions)

## Rule-Based Post-Processing

### WORD_REPLACEMENTS (~35 entries)
Single word fixes: `"ប្រេងសារ" → "ប្រេងសាំង", "រុយ" → "Reuters"`, etc.

### KHMER_COMPOUNDS (~90 entries)
Adjacent word pair mergers: `("មិន", "ដែល", "មិនដែល")`, `("មិនដែល", "សង្គម", "បណ្ដាញសង្គម")`

### merge_khmer_compounds
Multi-pass loop (while changed) — enables cascading merges:
- Pass 1: `មិន` + `ដែល` → `មិនដែល`
- Pass 2: `មិនដែល` + `សង្គម` → `បណ្ដាញសង្គម`

## Auto-Learning

### Data Format
`app/training/data/pairs.jsonl` — JSONL with `{"input": "STT output", "output": "correct text"}`

### Auto-Extract Rules
`rule_extractor.py` — character-level diff between stripped texts, maps differences back to STT words, extracts WORD_REPLACEMENTS + COMPOUNDS candidates

### Auto-Apply
`auto_learn.py:apply_rules()` — reads current subtitle_service.py, finds `WORD_REPLACEMENTS` dict and `KHMER_COMPOUNDS` list via marker + `=` sign + bracket matching, injects new entries before closing bracket, deduplicates by string check

### Bot Restart
After rule injection, bot calls `os.execvp()` to restart itself (hot reload)

## Training (Fine-Tuning)

### Qwen2.5-0.5B-Instruct + LoRA
- Requires 5+ pairs minimum
- Runs on MPS (Apple Silicon GPU) ~60s for 20 epochs
- Peft LoRA: r=4, target q_proj+v_proj
- Chat template with system/user/assistant roles
- Saved to `app/training/adapters/khmer_corrector/`

Commands:
```bash
python -m app.training.train_model
```

## Known Limitations
- Severe STT hallucinations (e.g., `ជើងបានចូលវីដេអូនៅទឹក` → should be `Comment`) cannot be fixed by rules or LLM
- Auto-extraction from <10 pairs produces noisy results; needs 50+ pairs to be reliable
- YouTube learning requires manually uploaded Khmer subtitles (auto-captions insufficient)
- Fine-tuned model needs 50+ pairs to be useful; with only 2 pairs it overfits

## Setup on New PC

```bash
# Clone + install
git clone <repo> && cd spech-to-text
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Environment
cp .env.example .env
# Edit .env: BOT_TOKEN, GOOGLE_APPLICATION_CREDENTIALS

# Run
python -m app.main           # Bot only
python -m app.run            # Bot + auto-scheduler
```
