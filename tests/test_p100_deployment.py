import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from datamate.hardware import load_profile, preflight

ROOT = Path(__file__).resolve().parents[1]


class P100Tests(unittest.TestCase):
    def test_initial_profile_is_bounded(self):
        profile = load_profile(ROOT / "configs/hardware/p100_16gb.json")
        self.assertLessEqual(profile["initial_parameter_cap"], 4_000_000_000)
        self.assertFalse(profile["training_enabled"])
        self.assertIsNone(profile["long_run_wall_hours"])

    def test_incompatible_precision_and_attention_rejected(self):
        original = json.loads((ROOT / "configs/hardware/p100_16gb.json").read_text())
        for key, value in [("dtype", "bfloat16"), ("attention_implementation", "flash_attention_2"),
                           ("batch_size", 4), ("trust_remote_code", True), ("local_files_only", False),
                           ("max_model_memory_gib", 16), ("training_enabled", True)]:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "profile.json"
                path.write_text(json.dumps({**original, key: value}))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    load_profile(path)

    def test_missing_cuda_reports_unverified_not_pass(self):
        fake = SimpleNamespace(__version__="fake", version=SimpleNamespace(cuda=None),
                               cuda=SimpleNamespace(is_available=lambda: False))
        report = preflight(load_profile(ROOT / "configs/hardware/p100_16gb.json"), fake)
        self.assertEqual(report["status"], "NOT_VERIFIED")
        self.assertFalse(report["model_loaded"])

    def test_wrong_wheel_architecture_rejected_before_allocation(self):
        fake = SimpleNamespace(__version__="fake", version=SimpleNamespace(cuda="13.0"),
                               cuda=SimpleNamespace(is_available=lambda: True, get_device_capability=lambda i: (6, 0),
                                                    get_device_properties=lambda i: SimpleNamespace(name="Tesla P100", total_memory=16 * 2**30),
                                                    get_arch_list=lambda: ["sm_80", "sm_90"]))
        report = preflight(load_profile(ROOT / "configs/hardware/p100_16gb.json"), fake)
        self.assertEqual(report["status"], "FAIL")

    def test_source_export_excludes_data_credentials_and_runtime(self):
        spec = importlib.util.spec_from_file_location("package_repo", ROOT / "scripts/package_repo.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = ["README.md", "src/datamate/__init__.py", "scripts/run.py", "train/answers.jsonl",
                     "public_test/questions.jsonl", "train/data/b/file.csv", ".aws/credentials", ".env",
                     "runs/debug/secrets.txt", "models/model.safetensors", "src/__pycache__/x.pyc",
                     "train/rulebook.md", "public_test/rulebook.md"]
            for name in names:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture")
            link = root / "src/credentials_link"
            link.symlink_to(root / ".aws/credentials")
            exported = {str(p.relative_to(root)) for p in module.source_files(root)}
            self.assertEqual(exported, {"README.md", "src/datamate/__init__.py", "scripts/run.py", "train/rulebook.md", "public_test/rulebook.md"})


if __name__ == "__main__":
    unittest.main()
