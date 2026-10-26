#!/usr/bin/env python3
"""Generate a few tokens with a local model on P100; NOT a competition predictor."""
import argparse
import importlib.metadata
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from datamate.hardware import load_profile, preflight
from datamate.io import sha256, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True, help="Existing local HF safetensors directory, never a model hub ID")
    parser.add_argument("--profile", type=Path, default=Path("configs/hardware/p100_16gb.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must be a fresh directory")
    if not args.model.is_dir() or not (args.model / "config.json").is_file():
        parser.error("--model must be an existing local model directory")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    profile = load_profile(args.profile)
    report = {"kind": "model_smoke_only", "training": False, "competition_quality_measured": False,
              "profile_sha256": sha256(args.profile), "model_path": str(args.model.resolve()), "status": "FAIL"}
    start = time.monotonic()
    try:
        import torch
        from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
        report["preflight"] = preflight(profile, torch)
        if report["preflight"]["status"] != "PASS":
            raise RuntimeError("GPU preflight failed; inspect report")
        torch.manual_seed(profile["seed"])
        torch.cuda.manual_seed_all(profile["seed"])
        torch.use_deterministic_algorithms(True)
        local = str(args.model.resolve())
        config = AutoConfig.from_pretrained(local, local_files_only=True, trust_remote_code=False)
        # Count before allocating real weights on the GPU.
        from accelerate import init_empty_weights
        with init_empty_weights():
            skeleton = AutoModelForCausalLM.from_config(config, trust_remote_code=False)
            skeleton.tie_weights()
            count = sum(p.numel() for p in skeleton.parameters())
        del skeleton
        report["inference_parameters"] = count
        if count > profile["initial_parameter_cap"]:
            raise RuntimeError("Model exceeds initial P100 parameter budget")
        tokenizer = AutoTokenizer.from_pretrained(local, local_files_only=True, trust_remote_code=False)
        torch.cuda.set_per_process_memory_fraction(profile["max_model_memory_gib"] * 2**30 / torch.cuda.get_device_properties(0).total_memory, 0)
        torch.cuda.reset_peak_memory_stats()
        model = AutoModelForCausalLM.from_pretrained(local, torch_dtype=torch.float16, attn_implementation="eager",
                                                    local_files_only=True, trust_remote_code=False, use_safetensors=True,
                                                    low_cpu_mem_usage=True, device_map={"": 0})
        model.eval()
        # This is intentionally a tiny hardware smoke prompt, not a QA training/example record.
        prompt = "Tính 2 + 3 và chỉ ghi kết quả."
        if tokenizer.chat_template:
            prompt = tokenizer.apply_chat_template([{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=profile["max_input_tokens"]).to("cuda:0")
        torch.cuda.synchronize()
        generation_start = time.monotonic()
        with torch.inference_mode():
            output = model.generate(**inputs, max_new_tokens=min(32, profile["max_new_tokens"]), do_sample=False,
                                    pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id)
        torch.cuda.synchronize()
        generated = output[0, inputs["input_ids"].shape[1]:]
        report.update({"status": "PASS", "output_text": tokenizer.decode(generated, skip_special_tokens=True),
                       "generated_tokens": int(generated.numel()), "generation_seconds": time.monotonic() - generation_start,
                       "peak_allocated_gib": torch.cuda.max_memory_allocated() / 2**30,
                       "peak_reserved_gib": torch.cuda.max_memory_reserved() / 2**30,
                       "versions": {m: importlib.metadata.version(m) for m in ("torch", "transformers", "accelerate", "safetensors")}})
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    report["wall_seconds"] = time.monotonic() - start
    write_json(args.output / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
