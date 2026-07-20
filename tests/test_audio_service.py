import os
import tempfile
import wave

from app.services.audio_service import convert_to_wav


def create_test_audio(path: str, sample_rate: int = 44100, channels: int = 2):
    import struct
    import math

    with wave.open(path, "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(sample_rate):
            value = int(math.sin(2 * math.pi * 440 * i / sample_rate) * 32767 * 0.5)
            packed = struct.pack("<h", value)
            wf.writeframes(packed)
            if channels == 2:
                wf.writeframes(packed)


def test_convert_to_wav():
    input_path = tempfile.mktemp(suffix=".wav")
    create_test_audio(input_path, sample_rate=44100, channels=2)

    try:
        output_path = convert_to_wav(input_path)

        with wave.open(output_path, "r") as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 16000
            assert wf.getsampwidth() == 2
    finally:
        os.unlink(input_path)
