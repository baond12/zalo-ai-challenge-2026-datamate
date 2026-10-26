"""P100 policy and a bounded CUDA check; import torch only when explicitly run."""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path


def load_profile(path: Path) -> dict:
    profile = json.loads(path.read_text())
    if profile["dtype"] != "float16" or profile["attention_implementation"] != "eager":
        raise ValueError("P100 initial profile requires float16 and eager attention")
    if profile["batch_size"] != 1 or profile["gpu_count_per_process"] != 1:
        raise ValueError("Initial P100 profile is one GPU, batch size 1")
    if not 0 < profile["initial_parameter_cap"] <= profile["competition_total_parameter_cap"]:
        raise ValueError("Invalid parameter budget")
    if not 0 < profile["max_model_memory_gib"] < profile["minimum_device_memory_gib"]:
        raise ValueError("Reserve GPU memory outside the model budget")
    if profile["max_input_tokens"] < 1 or profile["max_new_tokens"] < 1:
        raise ValueError("Token limits must be positive")
    if profile["quantization"] != "none" or profile["training_enabled"]:
        raise ValueError("This starting profile does not enable quantization or training")
    if not profile["local_files_only"] or profile["trust_remote_code"] or not profile["use_safetensors"]:
        raise ValueError("Require local safetensors with built-in model code")
    return profile


def preflight(profile: dict, torch_module=None) -> dict:
    report = {"profile": profile["profile"], "python": sys.version, "platform": platform.platform(),
              "status": "NOT_VERIFIED", "checks": [], "model_loaded": False}
    if shutil.which("nvidia-smi"):
        try:
            p = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                               capture_output=True, text=True, timeout=15)
            report["nvidia_smi"] = {"returncode": p.returncode, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}
        except (OSError, subprocess.TimeoutExpired) as exc:
            report["nvidia_smi_error"] = str(exc)
    try:
        if torch_module is None:
            import torch as torch_module
        torch = torch_module
        report["torch"] = torch.__version__
        report["torch_cuda"] = torch.version.cuda
        if not torch.cuda.is_available():
            report["reason"] = "CUDA unavailable; verify driver, device visibility and installed torch wheel"
            return report
        capability = tuple(torch.cuda.get_device_capability(0))
        props = torch.cuda.get_device_properties(0)
        arches = torch.cuda.get_arch_list()
        report.update({"device_name": props.name, "capability": list(capability),
                       "device_memory_gib": props.total_memory / 2**30, "compiled_arches": arches})
        report["checks"] = [
            {"name": "expected_compute_capability", "passed": capability == tuple(profile["expected_compute_capability"])},
            {"name": "native_sm60_in_wheel", "passed": "sm_60" in arches},
            {"name": "device_memory", "passed": props.total_memory >= profile["minimum_device_memory_gib"] * 2**30}]
        if not all(c["passed"] for c in report["checks"]):
            report["status"] = "FAIL"
            report["reason"] = "Hardware/wheel does not match the P100 profile"
            return report
        start = time.monotonic()
        # Real FP16 GEMM exercises the installed kernel without occupying meaningful VRAM.
        a = torch.ones((64, 64), device="cuda:0", dtype=torch.float16)
        result = a @ a
        torch.cuda.synchronize()
        ok = bool(torch.all(result == 64).item())
        report["checks"].append({"name": "fp16_cuda_gemm", "passed": ok})
        report["probe_seconds"] = time.monotonic() - start
        report["status"] = "PASS" if ok else "FAIL"
    except ImportError as exc:
        report["reason"] = f"GPU dependencies not installed: {exc}"
    except Exception as exc:
        report["status"] = "FAIL"
        report["reason"] = f"{type(exc).__name__}: {exc}"
    return report
