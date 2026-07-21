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
