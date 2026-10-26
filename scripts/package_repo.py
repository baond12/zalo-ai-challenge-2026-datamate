#!/usr/bin/env python3
"""Build a standalone private Git snapshot and transfer archives using an allowlist."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from datamate.io import sha256, write_json

CODE_DIRECTORIES = ("src", "scripts", "tests", "configs", "requirements", "splits", "docs")
ROOT_FILES = ("README.md", "pyproject.toml", ".gitignore", "Description.txt", "Evaluation.docx", "Data.docx", "Rule.txt", "Submission Guidance.txt")


def source_files(root: Path) -> list[Path]:
    result = []
    for name in ROOT_FILES:
        path = root / name
        if path.is_file() and not path.is_symlink():
            result.append(path)
    for directory in CODE_DIRECTORIES:
        for path in sorted((root / directory).rglob("*")):
            relative = path.relative_to(root)
            if path.is_file() and not path.is_symlink() and "__pycache__" not in relative.parts and ".git" not in relative.parts and path.suffix != ".pyc":
                result.append(path)
    # Documentary source metadata needed by register tests, not test questions/business data.
    for name in ("train/rulebook.md", "public_test/rulebook.md"):
        path = root / name
        if path.is_file() and not path.is_symlink():
            result.append(path)
    return sorted(result)


def make_archive(destination: Path, root: Path, files: list[Path]):
    with tarfile.open(destination, "w:gz") as archive:
        for path in files:
            relative = path.relative_to(root)
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError(f"Symlink or outside root: {relative}")
            archive.add(path, arcname=str(relative), recursive=False)


def package(root: Path, output: Path, include_train=False, include_evidence=False):
    if output.exists():
        raise FileExistsError("Use a fresh output directory")
    output.mkdir(parents=True)
    repo = output / "repo"
    repo.mkdir()
    files = source_files(root)
    for path in files:
        destination = repo / path.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    write_json(repo / "SOURCE_MANIFEST.json", {"scope": "private code/documentary snapshot; no raw business data, model weights or credentials",
                                              "files": [{"path": str(p.relative_to(root)), "sha256": sha256(p)} for p in files]})
    git_prefix = ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                  "-c", "user.name=DataMate Snapshot", "-c", "user.email=snapshot@localhost", "-C", str(repo)]
    def git(*args):
        return subprocess.run(git_prefix + list(args), check=True, capture_output=True, text=True, timeout=60).stdout.strip()
    git("init", "-b", "main")
    git("add", "--force", "--", *[str(p.relative_to(root)) for p in files], "SOURCE_MANIFEST.json")
    git("commit", "-m", "Prepare DataMate CPU scaffold and P100 16GB server workflow")
    commit = git("rev-parse", "HEAD")
    git("bundle", "create", str((output / "datamate.bundle").resolve()), "--all")
    git("bundle", "verify", str((output / "datamate.bundle").resolve()))
    repo_files = [repo / p.relative_to(root) for p in files] + [repo / "SOURCE_MANIFEST.json"]
    make_archive(output / "source.tar.gz", repo, repo_files)
    if include_train:
        train_files = sorted(p for p in (root / "train").rglob("*") if p.is_file())
        make_archive(output / "train.tar.gz", root, train_files)
    if include_evidence:
        evidence = []
        for folder in ("stage_a_audit_v3", "stage_a_verification_v1", "p100_repo_verification_v1"):
            evidence.extend(p for p in (root / "runs" / folder).rglob("*") if p.is_file())
        preflight = root / "runs/p100_local_preflight_v1.json"
        if preflight.is_file():
            evidence.append(preflight)
        make_archive(output / "evidence.tar.gz", root, sorted(evidence))
    artifacts = [{"name": p.name, "bytes": p.stat().st_size, "sha256": sha256(p)} for p in sorted(output.iterdir()) if p.is_file()]
    report = {"git_commit": commit, "code_files": len(files), "artifacts": artifacts,
              "train_separate_from_git": True, "published": False, "pushed": False,
              "hardware_execution": "NOT VERIFIED: local package only"}
    write_json(output / "PACKAGE_MANIFEST.json", report)
    (output / "SHA256SUMS").write_text("".join(f"{r['sha256']}  {r['name']}\n" for r in artifacts) + f"{sha256(output / 'PACKAGE_MANIFEST.json')}  PACKAGE_MANIFEST.json\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-train", action="store_true")
    parser.add_argument("--include-evidence", action="store_true")
    args = parser.parse_args()
    package(ROOT, args.output.resolve(), args.include_train, args.include_evidence)
