from app.services.file_service import is_supported, get_extension


def test_get_extension():
    assert get_extension("audio.m4a") == ".m4a"
    assert get_extension("audio.mp3") == ".mp3"
    assert get_extension("audio.wav") == ".wav"
    assert get_extension("audio.ogg") == ".ogg"


def test_is_supported():
    assert is_supported("test.m4a") is True
    assert is_supported("test.mp3") is True
    assert is_supported("test.wav") is True
    assert is_supported("test.ogg") is True
    assert is_supported("test.pdf") is False
    assert is_supported("test.txt") is False


def test_is_supported_no_extension():
    assert is_supported("test") is False
