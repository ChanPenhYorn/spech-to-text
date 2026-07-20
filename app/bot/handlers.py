import asyncio
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
    mode = context.user_data.get("use_v2", False)
    engine = "V2 (latest_long)" if mode else "V1 (standard)"
    await update.message.reply_text(f"{WELCOME_MESSAGE}\n\nEngine: {engine}\n/v2 — Toggle V2 engine (/v1 to switch back)")


async def v2_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["use_v2"] = True
    logger.info("User %s switched to V2 engine", update.effective_user.id)
    await update.message.reply_text("Switched to Google STT V2 (latest_long). /v1 to switch back.")


async def v1_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["use_v2"] = False
    logger.info("User %s switched to V1 engine", update.effective_user.id)
    await update.message.reply_text("Switched to Google STT V1 (standard). /v2 for V2 engine.")


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

        use_v2 = context.user_data.get("use_v2", False)
        transcribe_fn = transcription_v2.transcribe if use_v2 else transcription_v1.transcribe
        engine_label = "V2 latest_long" if use_v2 else "V1 standard"

        result = await loop.run_in_executor(None, transcribe_fn, temp_wav)

        processed = await loop.run_in_executor(
            None, process_segments, result.segments, temp_wav
        )

        plain_text = segments_to_text(processed)
        lang_display = get_language_display(result.language)

        await message.reply_text(
            f"{TRANSCRIPTION_HEADER}\n"
            f"{LANGUAGE_LABEL} {lang_display}\n"
            f"{plain_text}\n\n"
            f"{USAGE_LABEL} 0/0 ដង\n"
            f"Engine: {engine_label}"
        )

        await message.reply_text(PROCESSING_MESSAGE)

        srt_content = segments_to_srt(processed)

        elapsed = int(time.time() - start_time)

        srt_file_name = f"{audio.file_id}.srt"
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
