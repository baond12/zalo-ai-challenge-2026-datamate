# Backlog sau stage A

Ngày cập nhật 26/10/2026. Ưu tiên dựa trên yêu cầu và audit, chưa có error distribution từ mô hình. Các ước lượng tác động là giả thuyết; chưa có expected delta PA đo được. S/M/L là kích thước tương đối, không phải cam kết thời gian.

| ID | Ưu tiên | Việc và lý do | Đầu ra/acceptance | Effort | Phụ thuộc |
|---|---|---|---|---|---|
| B01 | P0 | Reader semantic: multirow headers, group-scoped fill, footer/metadata, partition union, dates, currencies | Provenance tới file/sheet/row; synthetic fixture tính tay và dev-only replay; không map theo ID | L | Audit/contract hiện có |
| B02 | P0 | Schema discovery + capabilities: field dictionary có/không, grain/keys/units, missing vs unsupported | Mapping có evidence và confidence; cardinality checks; giữ raw/extensions | L | B01 |
| B03 | P0 | Temporal/status engine với runtime rules | As-of, current/previous month/week, calendar Tết; late-return exception; mask revenue/debt riêng; đổi rulebook không sửa code | M/L | B01–B02 |
| B04 | P0 | Baseline end-to-end CPU theo operations tổng quát | Predict/evaluate một lệnh trên development; chưa hỗ trợ thì abstain; JSONL/log, PA/C/W/A và runtime thật; không đọc answers trong predictor | L | B01–B03 |
| B05 | P0 | Đánh giá lỗi baseline và lineage trong fold | OOF artifacts, slices, sai type/value/semantics; xác minh không fit examples/mapping bằng validation labels | M | B04 |
| B06 | P0 trước model | Chốt compute và model eligibility | GPU/server/quota/disk rõ; shortlist ít model có bằng chứng license/public-before-2026-10-01/parameters; model budget tổng ≤15B | M | Compute budget + nguồn model chính thức |
| B07 | P1 | Local model question planner/schema mapper so với CPU baseline | Benchmark cùng split; không đoán số thay execution; per-question plan/rules/SQL/results | L | B04–B06 |
| B08 | P1 | Mở rộng revenue/count/ratio/ranking trước | Number+percent chiếm 82,07% train; chỉ được nhận là cải thiện khi tăng PA CV, kiểm soát regression và runtime | M/L | B05 |
| B09 | P1 | Debt/stock/cost/profit/industry extensions | Tách total payable/revenue/cash; inventory snapshot; line cost authority; capability-based unanswerable | L | B02–B05 |
| B10 | P1 | Confidence/abstain calibration | Nested/cross-fit policy; risk–coverage; không fit và chấm policy trên cùng OOF labels; báo PA toàn N | M | OOF đủ dữ liệu |
| B11 | P1 | Unseen rule/schema/industry stress suite | Chạy manifests LOSO, synthetic rules đổi, format mới; annotation unknown không làm nhiễm claim ngành mới | M | B04/B07 |
| B12 | P2 | Bounded repair, retrieval, fine-tune hoặc ensemble | Một hypothesis/run, ablation/paired CV, time/memory/parameter budget; chỉ giữ nếu có bằng chứng | L | B05–B11 và budget |
| R01 | P0 trước release | Nhận general regulations, Docker guideline và scorer nếu BTC có | Nguồn/version được lưu; resolve các OPEN_QUESTIONS; không tự đoán base image | S/M | BTC/tài liệu bổ sung |
| R02 | P0 trước release | Docker offline, writer chịu interruption, logs, cold start | /data read-only, /result contract, no network/cache ngoài image; model inventory; <=6h trên máy tham chiếu | L | Candidate ổn + guideline + máy phù hợp |
| R03 | P0 trước release | Holdout checkpoint, reproducibility và freeze | Candidate/threshold khóa trước; ghi exposure; replay output/PA; manifest/checksum/README đầy đủ | M | QA dev pass, R01–R02 |

Bước có thể thực hiện tiếp ngay trong phạm vi CPU: B01–B04. Không cần trì hoãn chúng để chờ GPU. Chưa thực hiện B01–B04 trong stage A; raw readers hiện có phục vụ audit, chưa phải semantic baseline.

Tiêu chí dừng một batch tối ưu: hết ngân sách đã chốt, có bằng chứng không cải thiện, hoặc phát hiện vấn đề validation/leakage cần sửa trước. Không gọi một trial là “best” nếu chưa so với champion bằng cùng giao thức.
