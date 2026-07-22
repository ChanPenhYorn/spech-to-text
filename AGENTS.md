# spech-to-text

Telegram bot that transcribes Khmer audio using Google Cloud STT with rule-based post-processing and auto-learning pipeline.

## Commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill BOT_TOKEN + GOOGLE_APPLICATION_CREDENTIALS

python -m app.main              # bot only
python -m app.run               # bot + background auto-learn scheduler
python -m app.run --bot-only    # bot only
python -m app.run --learn-only  # scheduler only
python -m app.training.train_model               # LoRA fine-tune Qwen2.5-0.5B
python -m app.training.learn_from_audio <audio> <correct.txt> [--update-rules]
python -m app.training.auto_scheduler --once      # one-shot auto-learn cycle
python scripts/download_model.py <size>           # pre-download Whisper model
pytest                          # run tests (no special flags needed)
pytest tests/test_file_service.py  # single test file
```

`ffmpeg` must be installed on the host (used for audio conversion and duration probing).

## Architecture

| Path | Role |
|------|------|
| `app/main.py` | Bot entrypoint, registers handlers |
| `app/run.py` | Combined launcher (bot + background scheduler) |
| `app/bot/handlers.py` | Telegram command/audio handlers |
| `app/services/transcription.py` | **V1 (default, best)**: Google STT `latest_short`, 15s chunks |
| `app/services/transcription_v2.py` | V2: Google STV2 `latest_long` |
| `app/services/transcription_whisper.py` | V3: Whisper Khmer via faster-whisper (experimental, broken) |
| `app/services/subtitle_service.py` | `WORD_REPLACEMENTS` dict + `KHMER_COMPOUNDS` list + merge logic |
| `app/services/word_timestamp_processor.py` | Processing pipeline: normalize → replace_words → merge_khmer_compounds |
| `app/services/usage_service.py` | **Stubbed** — always returns unlimited (all fn return 0/True) |
| `app/services/llm_correction.py` | LLM correctors: OpenRouter, DeepSeek, Gemini, Ollama, Transformers — **all disabled by default** (no API keys shipped) |
| `app/services/learner.py` | Loads fine-tuned Qwen2.5-0.5B via PEFT adapters from `app/training/adapters/khrem_corrector/` |
| `app/training/auto_learn.py` | Auto-extract rules from pairs JSONL and inject into `subtitle_service.py` |
| `app/training/rule_extractor.py` | Diff-based rule extraction from (STT, correct) pairs |
| `app/training/learn_from_audio.py` | CLI tool to compare STT vs correct text |
| `app/training/data/pairs.jsonl` | Accumulated training pairs |
| `app/config/settings.py` | Env-driven frozen dataclass (dotenv) |
| `app/models/schemas.py` | `Segment`, `TranscriptionResult`, `UsageRecord` dataclasses |

## Key patterns

- **Post-processing pipeline**: `replace_words()` → `merge_khmer_compounds()` (multi-pass while-changed loop)
- **Auto-learn**: `/learn <correct text>` or `/learn_yt <URL>` → extracts rules from diff → injects into `subtitle_service.py` → `os.execvp()` restart
- **Bot restart** via `os.execvp("python", ["python", "-m", "app.main"])` in handlers; no graceful shutdown
- **FFmpeg conversion**: 16kHz mono WAV, no loudnorm filter (caused regressions per INIT.md)
- **V1 chunking**: 15s chunks, 2s overlap, overlap-dedup by `start < prev_last_end`
- **Subword merging**: SentencePiece `▁`-prefixed tokens are merged in `_merge_subword_tokens()`
- **V2 uses a hardcoded recognizer name** (`projects/967729414303/locations/global/recognizers/khmer-test-latestlong`)

## Testing quirks

- `pytest-asyncio` is installed but no `pytest.ini` with `asyncio_mode` — tests use sync functions only (no async tests yet)
- Tests are lightweight unit tests in `tests/` — no fixtures, no mocking, no integration tests
- Google STT credentials not needed for tests (no service import in tests)
- `test_usage_service.py` explicitly verifies the stubbed unlimited behavior

## Important constraints

- **No README** — use `INIT.md` as primary project doc
- **No CI, no lint, no format, no typecheck** config found
- Only **2 seed pairs** in `app/training/seed_data.py` — both in `pairs.jsonl` already
- YouTube auto-learning requires manually uploaded Khmer subtitles (auto-captions insufficient)
- `usage_service.py` is completely stubbed (always returns 0/True) — usage tracking needs implementation
- Fine-tuned Qwen2.5-0.5B model in `app/training/adapters/` is gitignored
- `app/training/auto_scheduler.py` has empty `DEFAULT_SOURCES` — YouTube sources must be configured externally
