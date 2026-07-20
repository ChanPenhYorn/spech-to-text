from pathlib import Path

from telegram import File

from app.utils.file_utils import create_temp_file
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

SUPPORTED_EXTENSIONS = {".m4a", ".mp3", ".wav", ".ogg"}


def get_extension(file_name: str) -> str:
    return Path(file_name).suffix.lower()


def is_supported(file_name: str) -> bool:
    ext = get_extension(file_name)
    supported = ext in SUPPORTED_EXTENSIONS
    if not supported:
        logger.warning("Unsupported file extension: %s", ext)
    return supported


async def download_audio(file: File, file_name: str) -> str:
    ext = get_extension(file_name)
    if not ext:
        ext = ".m4a"

    temp_path = create_temp_file(suffix=ext)
    await file.download_to_drive(custom_path=temp_path)
    logger.info("Downloaded audio to %s", temp_path)
    return temp_path
