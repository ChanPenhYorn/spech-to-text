import json
import logging
import os
from typing import Optional

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from app.training.rule_extractor import add_pair, auto_extract_rules, load_pairs

logger = logging.getLogger(__name__)

ADAPTER_PATH = os.path.join(os.path.dirname(__file__), "adapters", "khmer_corrector")
MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"

_learner_model = None
_learner_tokenizer = None

PROMPT_TEMPLATE = "Fix Khmer STT transcription errors.\nInput: {input}\nCorrected:"


def _load_model():
    global _learner_model, _learner_tokenizer
    if _learner_model is not None:
        return True
    if not os.path.exists(ADAPTER_PATH) or not os.path.exists(os.path.join(ADAPTER_PATH, "adapter_config.json")):
        return False
    try:
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        tokenizer = AutoTokenizer.from_pretrained(ADAPTER_PATH)
        tokenizer.pad_token = tokenizer.eos_token
        base = AutoModelForCausalLM.from_pretrained(MODEL_NAME, torch_dtype=torch.float32).to(device)
        _learner_model = PeftModel.from_pretrained(base, ADAPTER_PATH).to(device)
        _learner_tokenizer = tokenizer
        logger.info("Learner model loaded from %s", ADAPTER_PATH)
        return True
    except Exception as e:
        logger.error("Failed to load learner model: %s", e)
        return False


def correct_with_learner(text: str) -> Optional[str]:
    if not _load_model():
        return None
    try:
        prompt = PROMPT_TEMPLATE.format(input=text)
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        inputs = _learner_tokenizer(prompt, return_tensors="pt").to(device)
        outputs = _learner_model.generate(
            **inputs,
            max_new_tokens=256,
            temperature=0.1,
            do_sample=False,
        )
        decoded = _learner_tokenizer.decode(outputs[0], skip_special_tokens=True)
        corrected = decoded.replace(prompt, "").strip()
        return corrected if corrected else None
    except Exception as e:
        logger.error("Learner inference failed: %s", e)
        return None


def learn_from_pair(raw_stt: str, correct_text: str) -> dict:
    add_pair(raw_stt, correct_text)
    replacements, compounds = auto_extract_rules(raw_stt, correct_text)
    return {"replacements": replacements, "compounds": compounds}


def stats() -> dict:
    pairs = load_pairs()
    return {
        "pairs": len(pairs),
        "model_loaded": _learner_model is not None,
        "model_exists": os.path.exists(os.path.join(ADAPTER_PATH, "adapter_config.json")),
    }