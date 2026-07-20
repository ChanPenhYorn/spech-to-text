import sys
from faster_whisper import WhisperModel

if __name__ == "__main__":
    model_size = sys.argv[1] if len(sys.argv) > 1 else "base"
    print(f"Downloading Whisper model '{model_size}'...")
    WhisperModel(model_size, device="cpu", compute_type="int8")
    print("Model downloaded successfully")
