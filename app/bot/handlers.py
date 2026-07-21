import asyncio
import os
import time

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.responses import (
    WELCOME_MESSAGE,
    PROCESSING_MESSAGE,
    TRANSCRIPTION_DONE,
    TRANSCRIPTION_HEADER,
    LANGUAGE_LABEL,
    SRT_LANGUAGE_LABEL,
    get_language_display,
    SRT_FILE_LABEL,
    TIME_LABEL,
    TIME_SECONDS,
    USAGE_LABEL,
    BOT_TECH,
)
from app.services import transcription as transcription_v1
from app.services import transcription_v2
from app.services import transcription_whisper as transcription_v3
from app.services.file_service import is_supported, download_audio
from app.services.audio_service import convert_to_wav
from app.services.subtitle_service import segments_to_text, segments_to_srt
from app.services.word_timestamp_processor import process_segments
from app.training.rule_extractor import add_pair
from app.training.learn_from_audio import find_diffs
from app.utils.file_utils import cleanup_temp
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("User %s (%s) started the bot", user.id, user.full_name)
    engine = context.user_data.get("engine", "v1")
    engine_label = {"v1": "V1 (Google STT)", "v2": "V2 (Google STT latest)", "v3": "V3 (Whisper Khmer)"}.get(engine, engine)
    await update.message.reply_text(
        f"{WELCOME_MESSAGE}\n\n"
        f"Engine: {engine_label}\n"
        f"/v1 — Google STT standard\n"
        f"/v2 — Google STT latest_long\n"
        f"/v3 — Whisper Khmer (experimental)"
    )


async def v1_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["engine"] = "v1"
    logger.info("User %s switched to V1 engine", update.effective_user.id)
    await update.message.reply_text("Switched to Google STT V1 (standard). /v3 for Whisper Khmer.")


async def v2_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["engine"] = "v2"
    logger.info("User %s switched to V2 engine", update.effective_user.id)
    await update.message.reply_text("Switched to Google STT V2 (latest_long). /v3 for Whisper Khmer.")


async def v3_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["engine"] = "v3"
    logger.info("User %s switched to V3 Whisper Khmer engine", update.effective_user.id)
    await update.message.reply_text("Switched to Whisper Khmer (V3). May be slow on first use (model loading).")


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message

    audio = message.audio or message.voice or message.document
    if not audio:
        await message.reply_text("សូមផ្ញើឯកសារសំឡេង (.m4a, .mp3, .wav, .ogg)")
        return

    file_name = getattr(audio, "file_name", None) or f"{audio.file_id}.m4a"

    if not is_supported(file_name):
        await message.reply_text("ប្រភេទឯកសារមិនគាំទ្រ។ សូមផ្ញើ .m4a, .mp3, .wav, .ogg")
        return

    logger.info("User %s sent audio: %s", user.id, file_name)

    temp_audio = None
    temp_wav = None
    start_time = time.time()

    try:
        file = await audio.get_file()
        temp_audio = await download_audio(file, file_name)

        loop = asyncio.get_event_loop()
        temp_wav = await loop.run_in_executor(None, convert_to_wav, temp_audio)

        engine = context.user_data.get("engine", "v1")
        if engine == "v3":
            transcribe_fn = transcription_v3.transcribe
            engine_label = "V3 Whisper Khmer"
        elif engine == "v2":
            transcribe_fn = transcription_v2.transcribe
            engine_label = "V2 Google STT latest_long"
        else:
            transcribe_fn = transcription_v1.transcribe
            engine_label = "V1 Google STT standard"

        is_whisper = engine == "v3"

        processing_msg = await message.reply_text(PROCESSING_MESSAGE)

        result = await loop.run_in_executor(None, transcribe_fn, temp_wav)

        if is_whisper:
            processed = result.segments
            plain_text = segments_to_text(processed)
        else:
            processed = await loop.run_in_executor(
                None, process_segments, result.segments, temp_wav
            )
            plain_text = segments_to_text(processed)

        context.user_data["last_stt"] = plain_text

        lang_display = get_language_display(result.language)

        await processing_msg.edit_text(
            f"{TRANSCRIPTION_HEADER}\n"
            f"{LANGUAGE_LABEL} {lang_display}\n"
            f"{plain_text}\n\n"
            f"{USAGE_LABEL} 0/0 ដង\n"
            f"Engine: {engine_label}"
        )

        srt_content = segments_to_srt(processed)
        elapsed = int(time.time() - start_time)
        base_name = os.path.splitext(file_name)[0]
        srt_file_name = f"{base_name}.srt"
        await message.reply_document(
            document=srt_content.encode("utf-8"),
            filename=srt_file_name,
            caption=(
                f"{TRANSCRIPTION_DONE}\n"
                f"{SRT_FILE_LABEL} {srt_file_name}\n"
                f"{SRT_LANGUAGE_LABEL} {lang_display}\n"
                f"{TIME_LABEL} {elapsed} {TIME_SECONDS}\n"
                f"{USAGE_LABEL} 0/0 ដង\n"
                f"{BOT_TECH}"
            ),
        )

        logger.info(
            "Completed for user %s: %d segments, %ds elapsed",
            user.id, len(result.segments), elapsed,
        )

    except Exception as e:
        logger.error("Error processing audio for user %s: %s", user.id, str(e), exc_info=True)
        await message.reply_text(f"ដំណើរការបរាជ័យ: {str(e)}")

    finally:
        if temp_audio:
            cleanup_temp(temp_audio)
        if temp_wav:
            cleanup_temp(temp_wav)


async def learn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Compare last STT result with user-provided correct text. Usage: /learn <correct text>"""
    try:
        user = update.effective_user
        last_stt = context.user_data.get("last_stt")
        if not last_stt:
            await update.message.reply_text("No previous transcription found. Send an audio file first.")
            return

        args = context.args
        if not args:
            await update.message.reply_text("Usage: /learn <correct text>")
            return

        correct_text = " ".join(args)
        add_pair(last_stt, correct_text)
        diffs = find_diffs(last_stt, correct_text)

        if not diffs:
            await update.message.reply_text("No differences found — STT output matches!")
            return

        new_count = sum(1 for d in diffs if not d["already_have"])
        existing_count = sum(1 for d in diffs if d["already_have"])

        parts = []
        status_lines = [f"Found {len(diffs)} differences ({new_count} new, {existing_count} already fixed):"]
        for d in diffs[:20]:
            status = "✅" if d["already_have"] else "❌"
            status_lines.append(f"{status} {d['affected_text']} → {d['value']}")

        if len(diffs) > 20:
            status_lines.append(f"... and {len(diffs) - 20} more")

        msg = "\n".join(status_lines)
        if len(msg) > 4000:
            msg = msg[:3997] + "..."

        await update.message.reply_text(msg)

        # Auto-apply new rules
        new_rules = [d for d in diffs if not d["already_have"]]
        if new_rules:
            await update.message.reply_text(f"🔄 Auto-applying {len(new_rules)} new rules...")
            new_rep = {}
            for d in new_rules:
                if d["rule_type"] == "WORD_REPLACEMENT":
                    new_rep[d["key"]] = d["value"]
            new_comp = []
            for d in new_rules:
                if d["rule_type"] == "COMPOUND":
                    words = d["key"]
                    new_comp.append((words[0], words[1], d["value"]))

            from app.training.auto_learn import apply_rules
            if apply_rules(new_rep, new_comp):
                await update.message.reply_text(f"✅ Rules applied! Restarting bot to activate...")
                await asyncio.sleep(2)
                os.chdir(os.path.join(os.path.dirname(__file__), "..", ".."))
                os.execvp("python", ["python", "-m", "app.main"])
            else:
                await update.message.reply_text("❌ Failed to apply rules.")
        else:
            await update.message.reply_text("All differences already covered by existing rules ✅")
    except Exception as e:
        logger.error("learn_command failed: %s", e, exc_info=True)
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


async def learn_yt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Auto-learn from YouTube: download audio + captions, compare STT vs captions."""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /learn_yt <youtube_url>")
        return

    url = args[0]
    msg = await update.message.reply_text("⏳ Downloading audio and captions from YouTube...")

    try:
        import yt_dlp

        loop = asyncio.get_event_loop()
        temp_dir = os.path.join(os.path.dirname(__file__), "..", "..", "temp")
        os.makedirs(temp_dir, exist_ok=True)

        def _fetch():
            out_template = os.path.join(temp_dir, "%(id)s.%(ext)s")
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": out_template,
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}],
                "writesubtitles": True,
                "subtitleslangs": ["km"],
                "skip_download": False,
                "quiet": True,
                "writeautomaticsub": False,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_id = info["id"]
                audio_path = os.path.join(temp_dir, f"{video_id}.m4a")
                subs_path = os.path.join(temp_dir, f"{video_id}.km.vtt")
                subs_path2 = os.path.join(temp_dir, f"{video_id}.km.vtt")
                # Check alternative paths
                if not os.path.exists(subs_path):
                    subs_path = os.path.join(temp_dir, f"{video_id}.km.vtt")
                return audio_path, subs_path, info

        audio_path, subs_path, info = await loop.run_in_executor(None, _fetch)

        if not os.path.exists(audio_path):
            await msg.edit_text("❌ Failed to download audio.")
            return

        if not os.path.exists(subs_path):
            await msg.edit_text(
                "❌ No Khmer captions found for this video. "
                "The video needs manually uploaded Khmer subtitles."
            )
            return

        await msg.edit_text("⏳ Extracting captions...")
        def _read_subs():
            import webvtt
            captions = webvtt.read(subs_path)
            return " ".join(c.text.replace("\n", " ").strip() for c in captions)

        correct_text = await loop.run_in_executor(None, _read_subs)

        await msg.edit_text("⏳ Running STT on audio...")
        from app.services.audio_service import convert_to_wav
        wav_path = await loop.run_in_executor(None, convert_to_wav, audio_path)
        result = await loop.run_in_executor(None, transcription_v1.transcribe, wav_path)
        processed = await loop.run_in_executor(None, process_segments, result.segments, wav_path)
        our_text = segments_to_text(processed)

        add_pair(our_text, correct_text)
        diffs = find_diffs(our_text, correct_text)

        if not diffs:
            await msg.edit_text("✅ STT output matches YouTube captions perfectly!")
            return

        new_count = sum(1 for d in diffs if not d["already_have"])
        existing_count = sum(1 for d in diffs if d["already_have"])
        title = info.get("title", url)

        lines = [f"📖 {title}", f"Found {len(diffs)} differences ({new_count} new, {existing_count} already fixed):"]
        for d in diffs[:10]:
            status = "✅" if d["already_have"] else "❌"
            lines.append(f"{status} {d['affected_text']} → {d['value']}")

        if len(diffs) > 10:
            lines.append(f"... and {len(diffs) - 10} more")

        lines.append(f"\nPair saved. Auto-applying rules...")

        await msg.edit_text("\n".join(lines))

        new_rules = [d for d in diffs if not d["already_have"]]
        if new_rules:
            await msg.edit_text(f"🔄 Auto-applying {len(new_rules)} rules from YouTube...")
            new_rep = {}
            for d in new_rules:
                if d["rule_type"] == "WORD_REPLACEMENT":
                    new_rep[d["key"]] = d["value"]
            new_comp = []
            for d in new_rules:
                if d["rule_type"] == "COMPOUND":
                    words = d["key"]
                    new_comp.append((words[0], words[1], d["value"]))

            from app.training.auto_learn import apply_rules
            if apply_rules(new_rep, new_comp):
                await msg.edit_text(f"✅ {len(new_rules)} rules applied! Restarting bot...")
                await asyncio.sleep(1)
                os.chdir(os.path.join(os.path.dirname(__file__), "..", ".."))
                os.execvp("python", ["python", "-m", "app.main"])
            else:
                await msg.edit_text("❌ Failed to apply rules.")

    except ImportError:
        await msg.edit_text("❌ yt-dlp not installed. Run: pip install yt-dlp")
    except Exception as e:
        logger.error("learn_yt failed: %s", e, exc_info=True)
        await msg.edit_text(f"❌ Error: {str(e)[:200]}")
