from app.models.schemas import Segment
from app.services.subtitle_service import (
    segments_to_text,
    segments_to_srt,
    segments_to_vtt,
    _format_timestamp,
)


def test_format_timestamp():
    assert _format_timestamp(0.0) == "00:00:00,000"
    assert _format_timestamp(1.5) == "00:00:01,500"
    assert _format_timestamp(3661.789) == "01:01:01,789"


def test_segments_to_text():
    segs = [Segment(0.0, 1.0, "Hello"), Segment(1.0, 2.0, "World")]
    assert segments_to_text(segs) == "Hello World"


def test_segments_to_srt():
    segs = [Segment(0.0, 1.0, "Hello"), Segment(1.0, 2.0, "World")]
    result = segments_to_srt(segs)
    assert "1" in result
    assert "00:00:00,000 --> 00:00:01,000" in result
    assert "Hello" in result
    assert "2" in result
    assert "World" in result


def test_segments_to_srt_empty():
    assert segments_to_srt([]) == ""


def test_segments_to_vtt():
    segs = [Segment(0.0, 1.0, "Hello")]
    result = segments_to_vtt(segs)
    assert result.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:01.000" in result
    assert "Hello" in result
