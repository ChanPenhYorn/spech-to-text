from app.services.usage_service import get_usage, increment_usage, get_remaining, can_transcribe


def test_usage_always_unlimited():
    assert get_usage(0) == 0
    assert can_transcribe(0) is True
    increment_usage(0)
    assert get_usage(0) == 0
    assert get_remaining(0) == 0
