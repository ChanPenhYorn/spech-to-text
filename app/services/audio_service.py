import subprocess
from pathlib import Path

from app.utils.file_utils import create_temp_file
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


def convert_to_wav(input_path: str) -> str:
    output_path = create_temp_file(suffix=".wav")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        "-sample_fmt", "s16",
        output_path,
    ]

    logger.info("Converting %s to 16kHz mono WAV", input_path)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        logger.error("FFmpeg conversion failed: %s", result.stderr)
        raise RuntimeError(f"FFmpeg conversion failed: {result.stderr}")

    logger.info("Conversion complete: %s", output_path)
    return output_path
