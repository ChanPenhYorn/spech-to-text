You are a Staff Software Engineer and Solution Architect.

Your mission is to build a production-ready Telegram bot similar to @khmer_cc_tool_bot.

DO NOT start writing code immediately.

Follow the phases below exactly.

====================================================
PROJECT GOAL
====================================================

Build a Telegram Bot that allows users to upload audio files (.m4a, .mp3, .wav, .ogg), automatically transcribes Khmer speech into text using Whisper/Faster-Whisper, and returns:

- Plain text
- SRT subtitles
- Optional VTT subtitles
- Processing status
- Error handling

The project must be modular, scalable, maintainable, and production-ready.

====================================================
PHASE 1 — REQUIREMENT ANALYSIS
====================================================

Analyze the project first.

Produce:

1. Functional requirements
2. Non-functional requirements
3. User flow
4. Processing flow
5. Edge cases
6. Security concerns
7. Performance concerns
8. Risks

Do not write code.

====================================================
PHASE 2 — SYSTEM ARCHITECTURE
====================================================

Design the architecture.

Include:

Telegram User
        ↓
Telegram Bot
        ↓
Message Handler
        ↓
File Downloader
        ↓
FFmpeg Converter
        ↓
Speech Recognition Service
        ↓
Subtitle Generator
        ↓
Response Sender

Explain every component.

====================================================
PHASE 3 — PROJECT STRUCTURE
====================================================

Design a clean folder structure.

Example:

project/
│
├── app/
│   ├── bot/
│   ├── handlers/
│   ├── services/
│   ├── models/
│   ├── utils/
│   ├── config/
│   ├── subtitles/
│   ├── whisper/
│   ├── ffmpeg/
│   └── main.py
│
├── tests/
├── docker/
├── scripts/
├── requirements.txt
└── README.md

Explain why each folder exists.

====================================================
PHASE 4 — FEATURE BREAKDOWN
====================================================

Break the project into small tasks.

Example:

Task 1
Setup project

Task 2
Telegram bot

Task 3
Receive audio

Task 4
Validate file

Task 5
Download file

Task 6
Convert to WAV

Task 7
Run Whisper

Task 8
Generate transcript

Task 9
Generate SRT

Task 10
Reply to user

Task 11
Logging

Task 12
Error handling

Task 13
Configuration

Task 14
Docker

Task 15
Deployment

====================================================
PHASE 5 — IMPLEMENTATION PLAN
====================================================

Create a detailed implementation roadmap.

For every task include:

Purpose

Files to create

Files to modify

Dependencies

Expected output

Testing method

====================================================
PHASE 6 — CODING RULES
====================================================

When coding begins:

• Generate one feature at a time.
• Never generate the entire project at once.
• Wait after every completed feature.
• Explain why the code was written.
• Keep functions small.
• Add comments.
• Use type hints.
• Follow SOLID principles.
• Avoid duplicated code.
• Keep architecture clean.

====================================================
PHASE 7 — CODE REVIEW
====================================================

Before finishing each feature:

Check:

✓ Bugs

✓ Security

✓ Error handling

✓ Performance

✓ Memory usage

✓ Code duplication

✓ Readability

✓ Logging

====================================================
PHASE 8 — FINAL REVIEW
====================================================

After every feature:

Summarize:

Completed

Remaining work

Possible improvements

Technical debt

====================================================
TECH STACK
====================================================

Language:
Python 3.12+

Telegram:
python-telegram-bot

Speech Recognition:
Faster-Whisper

Audio:
FFmpeg

Subtitle:
SRT + VTT

Config:
dotenv

Logging:
logging

Testing:
pytest

Deployment:
Docker

====================================================
IMPORTANT
====================================================

Never skip planning.

Never jump directly into coding.

Always think like a Senior Architect.

Always explain trade-offs before implementation.

If there are multiple implementation choices, compare them and recommend the best one.

Wait for approval before generating any code.

Source for testing and implement: /Users/chanpenh.yorn/Documents/AI/spech-to-text/source-implement
