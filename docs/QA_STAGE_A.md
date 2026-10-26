# QA stage A — 26/10/2026

Verdict: **PASS cho phạm vi stage A**, với giới hạn đã ghi. **Chưa submit-ready** và chưa có đánh giá chất lượng mô hình. Đây là self-review bằng test/tool và đối chiếu tài liệu; chưa có reviewer bên ngoài hoặc scorer BTC.

| Hạng mục | Trạng thái | Bằng chứng/giới hạn |
|---|---|---|
| Đọc nguồn và BA | PASS | 5 tài liệu gốc, 2 rulebook; source extracts và SHA-256 trong requirements.json |
| Requirement/rule register | PASS | 30 global requirements, 84 train + 106 public rulebook records, 31 khác biệt bảng; 23 record có ví dụ nhỏ do BA viết; implementation/fixture status phân biệt rõ |
| Train physical audit | PASS | 30 README, toàn bộ raw files, questions/reference contracts, 339 bảng; AUDIT_REPORT và raw profiles |
| Raw source integrity | PASS | Verification so 162 SHA-256, changed_files=[]; không fill/dedup source |
| Business/schema-group validation | PASS | Current LOCK + business_v2; 4 folds, holdout, LOSO; tests disjointness/group/source hash |
| Leakage boundaries | PASS cho thiết lập hiện tại | Chưa training/predictor/model feedback; no test business/questions read ở lượt này; public rulebook chỉ documentary. Future training lineage chưa có để kiểm định |
| Local evaluator | PASS local | 45 tests toàn bộ suite; matching type/value/alias/table, missing abstain, strict JSON; các giả định scorer rõ trong protocol |
| Hand-computed CLI integration | PASS | 12 synthetic câu, C=8 W=2 A=2, PA=0,5 đúng kỳ vọng; không phải PA agent |
| Holdout guard | PASS | Fixture CLI --subset holdout bị chặn exit 2 khi thiếu flag; chưa mở actual holdout score |
| Scaffold | PASS stage A | Read-only readers, runtime split context và Planner/Executor interfaces; chưa implementation predictor |
| Python syntax | PASS | `python3 -m compileall -q src scripts tests`, exit 0 |
| Semantic business correctness của agent | NOT VERIFIED | Chưa có agent, chưa chạy đáp án train |
| Generalization score/confidence | NOT VERIFIED | Chưa có CV/LOSO/holdout predictions của mô hình |
| Official evaluator equivalence | NOT VERIFIED | Chưa có official code; epsilon/rounding/table edge cases còn assumptions |
| GPU, <=6h, Docker offline/re-run | NOT VERIFIED | Không có công cụ GPU/Docker trên PATH; không chạy máy tham chiếu |
| Model license/date/<=15B | NOT APPLICABLE stage A | Không có model; phải kiểm tra trước đưa model vào pipeline |

Bằng chứng verification: `runs/stage_a_verification_v1/verification.json`, `unittest.log`, `fixture_cli.log`, `holdout_guard.log`, `code_and_config_manifest.json`. 45 tests chạy thành công, không skipped. Không mở rộng kết luận của unit test thành bảo đảm điểm private.

Rủi ro cần xử lý ở B: semantic parser và provenance, grouping/null/returns, unit/currency conversion, nhiều grain và join multiplication, dynamic rulebook interpretation, capability-based unanswerable, rare-type coverage và nested calibration. Xem BACKLOG và OPEN_QUESTIONS.
