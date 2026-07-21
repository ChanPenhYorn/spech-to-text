import logging
import os
from typing import Optional

import requests

from app.utils.logger import setup_logger

logger = setup_logger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:3b"

CORRECTION_PROMPT = """Fix STT (Speech-to-Text) errors in Khmer text mixed with English. Keep Khmer as Khmer.

Common errors to fix:
- "នេះ ជាមួយ" → "និយាយ ជាមួយ" (context: talking with friends)
- "អា" is a filler word — remove it
- "ពិត ឡាយ" or "ពិត live" → "like" (misheard "like")
- "កាល កម្មវិធី" → "កម្មវិធី" (remove "កាល")
- "ម៉ូត" → "ប្រមូល" (as in "ប្រមូលទិន្នន័យ")
- "ទុក ទេ" → "ទស្សន៍ទាយ" (as in "ដើម្បីទស្សន៍ទាយ")
- "ចាំ បន្តិច" → "ចែករំលែក មតិយោបល់" (context: comment section)
- "អាមើល" → "មើល"
- "apple" or "អែប" or lowercase "app" → "App" (brand name, capitalize)
- "server" (lowercase) → "Server" (capitalize)
- "លោក ពេទ្យ" → "App មួយ" (common STT error for "app មួយ")
- "ប៉ា" at start → "តែ" (context: "ប៉ុន្តែ" or "តែ")
- Remove random wrong words like "កម្ដៅ"
- Brand names: Facebook, TikTok, App (keep English, capitalize properly)
- Merge split compounds: "ការ ចុច" → "ការចុច", "នៅ លើ" → "នៅលើ"

Output ONLY the corrected text, no explanations.

Text:"""


def _check_ollama() -> bool:
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def _check_model_available() -> bool:
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code != 200:
            return False
        models = resp.json().get("models", [])
        return any(OLLAMA_MODEL in m.get("name", "") for m in models)
    except requests.RequestException:
        return False


def _correct_with_ollama(text: str) -> Optional[str]:
    if not _check_ollama():
        logger.warning("Ollama server not reachable at %s", OLLAMA_BASE_URL)
        return None

    if not _check_model_available():
        logger.warning("Ollama model %s not available", OLLAMA_MODEL)
        return None

    prompt = f"{CORRECTION_PROMPT}\n\nText: {text}\n\nCorrected:"
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 4096},
            },
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        corrected = data.get("response", "").strip()
        if corrected:
            return corrected
        logger.warning("Ollama returned empty response")
        return None
    except requests.RequestException as e:
        logger.error("Ollama request failed: %s", e)
        return None


def _correct_with_openrouter(text: str) -> Optional[str]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("OPENROUTER_API_KEY not set")
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        messages = [
            {"role": "system", "content": CORRECTION_PROMPT},
            {"role": "user", "content": text},
        ]
        resp = client.chat.completions.create(
            model="qwen/qwen-plus",
            messages=messages,
            temperature=0.1,
            max_tokens=4096,
            timeout=60,
        )
        corrected = resp.choices[0].message.content.strip()
        logger.info("OpenRouter correction succeeded (%d chars)", len(corrected))
        return corrected if corrected else None
    except Exception as e:
        logger.error("OpenRouter correction failed: %s", e)
        return None


def _correct_with_deepseek(text: str) -> Optional[str]:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        logger.warning("DEEPSEEK_API_KEY not set")
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        messages = [
            {"role": "system", "content": CORRECTION_PROMPT},
            {"role": "user", "content": text},
        ]
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.1,
            max_tokens=4096,
            timeout=60,
        )
        corrected = resp.choices[0].message.content.strip()
        return corrected if corrected else None
    except Exception as e:
        logger.error("DeepSeek correction failed")
        return None


def _correct_with_gemini(text: str) -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set")
        return None
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        prompt = f"{CORRECTION_PROMPT}\n\nText: {text}\n\nCorrected:"
        resp = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=prompt,
        )
        corrected = resp.text.strip()
        return corrected if corrected else None
    except Exception as e:
        logger.error("Gemini correction failed: %s", e)
        return None


def _correct_with_transformers(text: str) -> Optional[str]:
    try:
        from transformers import pipeline

        pipe = pipeline(
            "text2text-generation",
            model="Qwen/Qwen2.5-0.5B-Instruct",
            device=-1,
        )
        prompt = f"{CORRECTION_PROMPT}\n\nText: {text}\n\nCorrected:"
        result = pipe(prompt, max_new_tokens=256, temperature=0.1)
        corrected = result[0]["generated_text"].strip()
        return corrected if corrected else None
    except Exception as e:
        logger.error("Transformers correction failed: %s", e)
        return None


_corrector_fn = _correct_with_ollama


def set_corrector(fn_name: str) -> None:
    global _corrector_fn
    if fn_name == "transformers":
        _corrector_fn = _correct_with_transformers
    elif fn_name == "gemini":
        _corrector_fn = _correct_with_gemini
    elif fn_name == "ollama":
        _corrector_fn = _correct_with_ollama
    else:
        logger.warning("Unknown corrector '%s', keeping default", fn_name)


def correct_text(text: str) -> str:
    for fn in [_correct_with_openrouter, _correct_with_deepseek, _correct_with_gemini, _correct_with_ollama, _correct_with_transformers]:
        logger.info("Trying corrector: %s", fn.__name__)
        corrected = fn(text)
        if corrected:
            logger.info("Corrector %s succeeded", fn.__name__)
            return corrected
    logger.info("All LLM correction methods unavailable, returning original text")
    return text
