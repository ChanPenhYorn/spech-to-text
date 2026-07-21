import json
import os
import sys

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorForSeq2Seq,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.training.rule_extractor import load_pairs

MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
ADAPTER_PATH = os.path.join(os.path.dirname(__file__), "adapters", "khmer_corrector")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "pairs.jsonl")
os.makedirs(os.path.dirname(ADAPTER_PATH), exist_ok=True)
os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)

PROMPT_TEMPLATE = """Fix Khmer STT transcription errors.

Input: {input}
Corrected: {output}"""


def build_dataset() -> Dataset:
    pairs = load_pairs()
    if not pairs:
        raise ValueError("No training data found")

    texts = []
    for p in pairs:
        texts.append(PROMPT_TEMPLATE.format(input=p["input"].strip(), output=p["output"].strip()))
    return Dataset.from_dict({"text": texts})


def tokenize(examples, tokenizer, max_length=512):
    tokenized = tokenizer(
        examples["text"],
        truncation=True,
        padding="max_length",
        max_length=max_length,
    )
    tokenized["labels"] = tokenized["input_ids"].copy()
    return tokenized


def train() -> None:
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Using device: {device}")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float32,
        device_map=None,
    ).to(device)

    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=8,
        lora_alpha=32,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        lora_dropout=0.1,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    dataset = build_dataset()
    tokenized = dataset.map(lambda x: tokenize(x, tokenizer), remove_columns=["text"], batched=False)

    args = TrainingArguments(
        output_dir=ADAPTER_PATH,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        num_train_epochs=20,
        logging_steps=1,
        save_strategy="epoch",
        learning_rate=2e-4,
        fp16=False,
        report_to="none",
        save_total_limit=2,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=tokenized,
        data_collator=DataCollatorForSeq2Seq(tokenizer, pad_to_multiple_of=8),
    )

    trainer.train()
    trainer.save_model(ADAPTER_PATH)
    tokenizer.save_pretrained(ADAPTER_PATH)
    print(f"Adapter saved to {ADAPTER_PATH}")


if __name__ == "__main__":
    train()