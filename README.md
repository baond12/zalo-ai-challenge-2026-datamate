# DataMate — Zalo AI Challenge 2026

Stage A đã hoàn thành: BA, full physical audit train, validation manifests, local evaluator và scaffold CPU. **Chưa có prediction agent, model champion hoặc PA giải pháp.**

Đọc [trạng thái dự án](docs/PROJECT_STATE.md), [audit](docs/AUDIT_REPORT.md), [validation protocol](docs/VALIDATION_PROTOCOL.md), [QA](docs/QA_STAGE_A.md) và [backlog](docs/BACKLOG.md) trước khi triển khai tiếp.

## Server GPU P100 16 GB

Tài nguyên phát triển hiện tại: **1× Tesla P100 16 GB**. Đã có profile, script setup Python 3.11/PyTorch 2.6.0, GPU preflight và local-model smoke test. Xem [hướng dẫn server](docs/P100_SERVER.md). Chưa deploy hoặc kiểm chứng GPU thực tế trên server.

```bash
PYTHON_BIN=python3.11 bash scripts/server/setup_p100.sh
CUDA_VISIBLE_DEVICES=0 .venv-p100/bin/python scripts/gpu_preflight.py --output runs/p100_preflight_001.json
```

Tạo gói chuyển server (output mới):

```bash
python3 scripts/package_repo.py --output artifacts/p100_v1 --include-train --include-evidence
```

Gói chứa repo Git độc lập và bundle để clone; data/evidence tách thành archive riêng. Không publish hoặc push lên dịch vụ nào. Sau khi unpack train, chạy `bash scripts/server/test_cpu.sh` trên server.

## Chạy hiện tại

Python >=3.11, chỉ thư viện chuẩn cho các command dưới; đã kiểm tra trên Python 3.14.4. Không cần cài package để dùng scripts tại repo root.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/audit_train.py --output runs/MY_NEW_AUDIT
python3 scripts/verify_stage_a.py --audit runs/stage_a_audit_v3 --output runs/MY_NEW_VERIFICATION
```

Các tên `MY_NEW_*` phải là output directory mới. Audit đã lưu ở `runs/stage_a_audit_v3`; không cần quét lại nếu input không đổi. Verification lưu stdout/test results, fixture tính tay, checksum và code/config manifest.

Local evaluation sau khi có prediction file:

```bash
python3 scripts/evaluate.py --splits splits/business_v2.json --subset development --predictions runs/CANDIDATE/predictions.jsonl --output runs/CANDIDATE_EVAL
```

`CANDIDATE` là placeholder; stage A chưa có predictions thực tế. Missing IDs được tính abstain; duplicate/unknown IDs và malformed answers bị validator từ chối. Holdout chặn mặc định; chỉ dùng tại checkpoint theo protocol.

## Nguồn và kiến trúc

- Tài liệu gốc: Description, Evaluation, Data, Rule, Submission Guidance tại thư mục gốc; rulebook/calendar theo split.
- [Requirement register](docs/requirements.json), [rule register](docs/RULE_REGISTER.json) và [source extracts](docs/source_extracts/) có nguồn/hashes và trạng thái implementation.
- [Contracts](docs/DATA_CONTRACTS.md): raw readers, split context và interface planner/executor. Semantic mappings, execution engine và inference packaging sẽ làm ở B trở đi.
- [Master prompt](docs/competition/02_MASTER_PROMPT.md), [workflow](docs/competition/03_WORKFLOW.md), [stage prompts](docs/competition/04_STAGE_PROMPTS.md) cho cách giao việc.

Dữ liệu gốc không được chỉnh, fill/dedup chỉ có thể tạo derived artifacts có provenance theo rulebook. Public/private không dùng cho training hoặc thu thập đáp án. Scorer local chưa được BTC xác nhận tương đương; các assumptions được liệt kê trong protocol.
