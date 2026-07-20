from dataclasses import dataclass


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    language: str
    segments: list[Segment]
    duration: float


@dataclass
class UsageRecord:
    user_id: int
    count: int
