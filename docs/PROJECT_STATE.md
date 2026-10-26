# Project state — DataMate 2026

Ngày cập nhật: **26/10/2026, GMT+7**. Stage A **completed** trong phạm vi người dùng giao. Chưa bắt đầu stage B. Đọc file này trước khi tiếp tục; không chạy lại audit/split từ đầu nếu input chưa thay đổi.

**Cập nhật tài nguyên:** người dùng chốt phát triển trên **1× P100 16 GB của server hiện có**. Đã chuẩn bị repo Git portable, setup/preflight/smoke scripts và hướng dẫn `docs/P100_SERVER.md`; chưa có SSH host/path nên chưa deploy hoặc chạy GPU. Profile P100 chỉ là cấu hình khởi điểm, chưa là benchmark PA.

## Trạng thái cốt lõi

- **Champion: chưa có. Baseline/model PA: chưa đo.** Không có training hoặc model inference nào đã chạy.
- Audit train hiện hành: `runs/stage_a_audit_v3`; 30 business, 3.000 câu, 339 bảng/sheet, 3.997.042 dòng vật lý. Không lỗi đọc. SHA-256 của 162 file train được kiểm tra không đổi.
- Current validation lock: `splits/LOCK.json` → **splits/business_v2.json**. Development=24 business/2.289 câu; holdout=6/711. 4-fold Group CV giữ chung exact sale-schema family; 5 protocol LOSO, chưa chạy mô hình.
- **Holdout score openings=0**. Input/metadata/aggregate type audit đã diễn ra; không gọi đây là pristine blind holdout. `holdout_exposure.jsonl` đang rỗng.
- Local scorer v1 là mô phỏng tài liệu, chưa có official scorer BTC. Xem VALIDATION_PROTOCOL §7 trước diễn giải PA.
- Bộ CPU verification: **45/45 tests PASS**, không skipped; CLI fixture C=8/W=2/A=2, expected PA=0,5; holdout guard PASS. PA fixture không phải PA giải pháp.

## Artifact để đọc

1. `docs/competition/01_COMPETITION_BRIEF.md`: compact yêu cầu ban đầu.
2. `docs/requirements.json`, `docs/RULE_REGISTER.json`, `docs/TRAIN_README_REGISTER.json`, `docs/source_extracts/`: BA có nguồn/hashes và trạng thái implementation.
3. `docs/AUDIT_REPORT.md`, `docs/BUSINESS_TAXONOMY.json`, `runs/stage_a_audit_v3/`: audit và metadata. Roles/date profiles/joins là quan sát hoặc candidate, chưa là semantic mapping đúng hoàn toàn.
4. `docs/VALIDATION_PROTOCOL.md`, `splits/`: ranh giới dữ liệu, fold, holdout/LOSO, scorer assumptions.
5. `docs/DATA_CONTRACTS.md`, `src/datamate/`, `scripts/`, `tests/`, `README.md`: scaffold và cách chạy.
6. `docs/DECISIONS.md`, `docs/BACKLOG.md`, `docs/OPEN_QUESTIONS.md`, `docs/QA_STAGE_A.md`: quyết định, việc tiếp theo và giới hạn.
7. `runs/stage_a_verification_v1/`: logs, metrics synthetic, integrity và code/config hashes.

## Công việc đã thực hiện

Đọc nguồn; trích source có line/paragraph index; tạo 30 requirement và 190 rulebook records (23 record có ví dụ), 31 table-rule differences. Quét raw train toàn bộ, giữ nguyên source; thống kê dates/units/status/key/null/duplicate; phân biệt candidate joins với foreign keys đã chứng minh. Đóng taxonomy và split trước model development.

Scaffold stdlib gồm strict JSONL contracts, Decimal scorer, raw CSV/XLSX/SQLite readers, split context không đọc answers và Planner/Executor interfaces. Chưa có semantic answer engine hoặc `predict.sh`/Docker chạy được, không có file giả được gọi là solution.

## Lệnh đã chạy và evidence

```bash
python3 scripts/build_register.py
python3 scripts/audit_train.py --output runs/stage_a_audit_v3
python3 scripts/build_splits.py --audit runs/stage_a_audit_v3 --version business_v2 --supersedes business_v1
python3 scripts/render_audit_report.py --audit runs/stage_a_audit_v3
python3 scripts/verify_stage_a.py --audit runs/stage_a_audit_v3 --output runs/stage_a_verification_v1
python3 -m compileall -q src scripts tests
```

Các command tạo run/split mới bảo vệ không overwrite; đây là lịch sử, không chạy lại nguyên văn vào output đã tồn tại. Để kiểm thử nhanh: `PYTHONPATH=src python3 -m unittest discover -s tests -v`.

Audit v1/v2 và split v1 giữ làm lịch sử. V3 sửa đầy đủ recognized date formats; split v2 sửa annotation nhầm thuốc lá/pharmacy và loại unknown sector khỏi LOSO. Revision không đổi business/fold membership, không dùng score. Xem DECISIONS D003/D005.

## Tài nguyên và ngân sách

Local: Python 3.14.4, 16 logical CPUs, RAM tổng khoảng 14,5 GiB; không có nvidia-smi/docker trên PATH. Server phát triển được người dùng chỉ định: **1× P100 16 GB**; chưa xác minh driver/Python/CUDA thực tế, SSH target và thư mục chưa được cung cấp. Ba full audit CPU mất tổng khoảng 571 giây wall-clock; GPU-hours=0, model downloads=0, paid compute=0. Chưa chốt wall-time cho training/GPU dài; không thuê GPU khác. Không đọc credentials hoặc kết nối server khác.

Repo chuẩn bị P100: CPU suite hiện **50/50 PASS** (45 stage A + 5 deployment policy/export tests), Bash syntax và Python compile pass. Local preflight trả `NOT_VERIFIED` vì chưa có torch/GPU local; không báo PASS giả. Evidence: `runs/p100_repo_verification_v1/` và `runs/p100_local_preflight_v1.json`. Gói chuyển server: `artifacts/p100_v1/`; `.git` workspace được quản lý read-only nên gói chứa repo Git riêng và bundle, không sửa `.git` gốc.

## Bước tiếp theo cụ thể

Thực hiện giai đoạn B, ưu tiên **B01–B04 trong BACKLOG**: semantic readers + provenance, schema capabilities, time/status theo runtime rules, baseline CPU end-to-end có abstain hợp lệ. Chạy development theo split v2; lưu predictions/log/PA/error slices thật. **Chưa mở holdout** và chưa training/GPU dài khi chưa có ngân sách.

Cần tiếp theo: chuyển repo lên server sau khi có SSH target/path, setup venv và bounded GPU preflight; chốt wall-time trước training/GPU dài. Cần bổ sung trước model/release: model license/release-date evidence, general regulations và Docker guideline. Chúng không chặn các việc baseline CPU nêu trên. Không có cam kết chiến thắng hoặc bảo đảm private từ public.
