import os
import shutil
import tempfile
from pathlib import Path

from app.config.settings import settings
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


def get_temp_dir() -> Path:
    path = Path(settings.temp_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_temp_file(suffix: str = "") -> str:
    temp_dir = get_temp_dir()
    fd, path = tempfile.mkstemp(suffix=suffix, dir=str(temp_dir))
    os.close(fd)
    return path


def cleanup_temp(path: str) -> None:
    try:
        if os.path.isfile(path):
            os.remove(path)
            logger.debug("Cleaned up temp file: %s", path)
    except OSError as e:
        logger.warning("Failed to clean up %s: %s", path, e)


def cleanup_temp_dir() -> None:
    temp_dir = get_temp_dir()
    try:
        shutil.rmtree(str(temp_dir))
        temp_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("Cleaned up temp directory")
    except OSError as e:
        logger.warning("Failed to clean up temp dir: %s", e)
