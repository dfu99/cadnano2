#!/usr/bin/env python3
"""
finetune_unsloth.py

Fine-tune a local model (Qwen 2.5 or similar) on cadnano agent trajectories
using Unsloth + LoRA. Run this OUTSIDE cadnano on a machine with a GPU.

Prerequisites:
    pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
    pip install trl datasets

Usage:
    # 1. Export training data from expert JSON examples:
    python tools/export_training_data.py agent-6hb-scaffoldonly.json \
        --task "Create a 6-helix bundle with 105bp scaffold routing through all helices" \
        --output ~/.cadnano2/training_data.jsonl

    # 2. Also export any trajectories recorded by the agent:
    #    (trajectorylogger saves to ~/.cadnano2/trajectories/success/)
    #    python tools/export_trajectories.py  ← TODO: implement this converter

    # 3. Fine-tune:
    python tools/finetune_unsloth.py \
        --data ~/.cadnano2/training_data.jsonl \
        --model Qwen/Qwen2.5-1.5B-Instruct \
        --output ~/.cadnano2/finetuned_model \
        --epochs 3

    # 4. Deploy in Ollama:
    ollama create cadnano-agent -f ~/.cadnano2/finetuned_model/Modelfile

Notes:
    - Use Qwen2.5-1.5B-Instruct for fast iteration (fits on 8GB VRAM)
    - Use Qwen2.5-7B-Instruct for better performance (needs 16GB+ VRAM)
    - The TOOL_SCHEMAS from agenttools.py define the available functions
    - After fine-tuning, the model should be much better at:
        1. Knowing WHICH method to call (createHelicesWithStrands vs addCrossoversForPair)
        2. Knowing the CORRECT parameters (num_helices=6, length=84, etc.)
        3. Understanding when the task is done
"""

import argparse
import json
import os
import sys


def load_jsonl(path: str) -> list:
    examples = []
    with open(os.path.expanduser(path)) as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def messages_to_text(messages: list, tokenizer) -> str:
    """Convert messages list to text using the model's chat template."""
    # Filter out tool_call_id from tool messages (not always supported)
    cleaned = []
    for msg in messages:
        m = {k: v for k, v in msg.items() if k != "tool_call_id"}
        # Flatten tool_calls to text for models that don't natively support them
        if m.get("role") == "assistant" and m.get("tool_calls"):
            tc = m["tool_calls"][0]
            fn = tc["function"]
            m = {
                "role": "assistant",
                "content": f'<tool_call>{{"name": "{fn["name"]}", "arguments": {fn["arguments"]}}}</tool_call>'
            }
        elif m.get("role") == "tool":
            m = {"role": "user", "content": f"<tool_result>{m['content']}</tool_result>"}
        cleaned.append(m)

    return tokenizer.apply_chat_template(
        cleaned,
        tokenize=False,
        add_generation_prompt=False
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="JSONL training data file")
    parser.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct",
                        help="Base model (HuggingFace ID)")
    parser.add_argument("--output", default="~/.cadnano2/finetuned_model",
                        help="Output directory for fine-tuned model")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--max-seq-len", type=int, default=4096)
    parser.add_argument("--lora-r", type=int, default=16,
                        help="LoRA rank (higher = more capacity, more VRAM)")
    args = parser.parse_args()

    try:
        from unsloth import FastLanguageModel
        from trl import SFTTrainer
        from transformers import TrainingArguments
        from datasets import Dataset
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install: pip install 'unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git' trl datasets")
        sys.exit(1)

    print(f"Loading model: {args.model}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model,
        max_seq_length=args.max_seq_len,
        dtype=None,       # Auto-detect
        load_in_4bit=True # QLoRA: quantize base, train LoRA adapters
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=args.lora_r * 2,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth"
    )

    print(f"Loading training data: {args.data}")
    raw_examples = load_jsonl(args.data)
    print(f"  {len(raw_examples)} examples")

    texts = []
    for ex in raw_examples:
        msgs = ex.get("messages", ex)  # Handle both formats
        text = messages_to_text(msgs, tokenizer)
        texts.append({"text": text})

    dataset = Dataset.from_list(texts)

    output_dir = os.path.expanduser(args.output)
    os.makedirs(output_dir, exist_ok=True)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=args.max_seq_len,
        dataset_num_proc=2,
        args=TrainingArguments(
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            warmup_steps=10,
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            fp16=True,
            logging_steps=10,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=42,
            output_dir=output_dir,
            save_strategy="epoch",
            report_to="none"
        )
    )

    print("Starting fine-tuning...")
    trainer.train()

    print(f"Saving to {output_dir}")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    # Write a simple Ollama Modelfile
    modelfile_path = os.path.join(output_dir, "Modelfile")
    with open(modelfile_path, "w") as f:
        f.write(f'FROM {output_dir}\nPARAMETER temperature 0.1\n')
    print(f"Modelfile written to {modelfile_path}")
    print()
    print("Deploy in Ollama:")
    print(f"  ollama create cadnano-agent -f {modelfile_path}")
    print()
    print("Then in cadnano: switch backend to Ollama, model = cadnano-agent")


if __name__ == "__main__":
    main()
