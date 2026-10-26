# Validation protocol — stage A, 26/10/2026

Trạng thái: giao thức được thiết lập trước model development. Chưa đo chất lượng giải pháp. Manifest đang có hiệu lực lấy từ `splits/LOCK.json`; bản hiện hành là `business_v2.json`. Không đổi split sau khi thấy score để làm kết quả đẹp hơn.

## 1. Mục tiêu đánh giá

Metric chính: PA=(C−W)/N, mẫu số gồm cả abstain và missing. Báo kèm coverage, accuracy trên câu đã trả lời, wrong/N, PA theo business/type/ngành và runtime. PA macro theo business là chỉ báo phụ, không thay metric BTC.

Business là đơn vị tách dữ liệu tối thiểu. Các doanh nghiệp có cùng schema bán hàng chính đã được nhận diện bằng header chuẩn hóa được giữ cùng nhóm. Cách này giảm khả năng tận dụng export template đã thấy; không chứng minh mọi tương đồng về dữ liệu sinh/template đã được loại bỏ.

## 2. Manifest cố định

- Seed: **20261026**; tạo từ schema/README và số câu, trước khi có model hoặc score. Nhãn ngành là annotation BA, không phải nhãn chính thức BTC và không được import vào inference để chọn thuật toán.
- **Development: 24 business, 2.289 câu.** Group CV 4 fold, lần lượt 590, 592, 554, 553 câu validation. Báo PA gộp OOF theo câu, không lấy trung bình PA các fold như metric chính khi kích thước khác nhau.
- **Holdout: 6 business, 711 câu:** biz_102, biz_103, biz_104, biz_121, biz_122, biz_129. Năm business đầu dùng chung schema sale-fact; giữ cả family ngoài development. Thêm một restaurant có format khác.
- Holdout bao gồm grocery/cafe/pharmacy/restaurant, **không có building materials**. Không gọi nó là mẫu đại diện hoàn hảo của private. CV theo nhóm và leave-one-sector-out bổ sung phần thiếu.
- Các type hiếm không xuất hiện ở mọi fold. Fold 0 không có boolean/unanswerable, fold 3 không có table. Không phá group để cân bằng cho đẹp; báo số mẫu và kết quả gộp, bổ sung fixture độc lập cho edge case.
- `splits/question_assignments_v2.jsonl` chỉ có ID, business, partition và fold; không chứa đáp án. `LOCK.json` lưu checksum và số lần mở holdout ban đầu=0.

`business_v1.json` được giữ làm lịch sử và đã bị thay thế: rule gán nhãn ngành ban đầu bắt nhầm từ “Thuốc” trong “Thuốc lá”. Bản v2 sửa annotation và LOSO, không đổi membership development/holdout/CV hoặc xem score nào. Xem `splits/REVISIONS.jsonl` và `docs/DECISIONS.md`.

## 3. Ranh giới dữ liệu

| Artifact/công việc | Dữ liệu được dùng |
|---|---|
| Audit input schema, README, dates, quality | Toàn bộ train, không sửa dữ liệu |
| Aggregate type statistics, integrity validation | Toàn bộ train references; không chấm candidate holdout |
| Training, prompt/few-shot/template selection, synthetic, learned mappings | Chỉ business thuộc training partition của fold |
| Inference trên fold validation | Đọc input package, README/rulebook/calendar của chính nó; không dùng nhãn vào pipeline |
| Confidence calibration/model selection | Inner validation hoặc cross-fitting trong outer training; không dùng nhãn outer validation để vừa fit vừa chấm |
| Holdout inference/evaluation | Chỉ tại checkpoint đã định, sau khi khóa candidate và threshold bằng development |
| Public/private | Input inference theo thể lệ; không training, pseudo-label, few-shot, lookup answer, giải tay hoặc dò đáp án |

Mọi synthetic/paraphrase sinh từ một business đi cùng group của business đó; không tạo từ holdout/test. Dữ liệu ngoài/synthetic độc lập phải có provenance và chống trùng với evaluation. Preprocessor hoặc rule/template học từ dữ liệu cũng được fit trong training fold. Runtime discovery từ input mới được phép vì nó thuộc bài toán; nhãn/feedback evaluation không được trở thành runtime knowledge.

Không dùng `train/answers.jsonl` trong predictor. File này chỉ thuộc audit/evaluation/training tools được phép. `load_split` không đọc answers, không có fallback sang rulebook train. Register tài liệu có luật public chỉ phục vụ đối chiếu nguồn; inference phải đọc rulebook runtime, không import register làm defaults của private.

## 4. Holdout exposure

Holdout **không phải blind pristine**: raw input, README, aggregate answer types đã được audit toàn train trước freeze; một số ví dụ train đã được hiển thị trong phiên soạn prompt trước đó. Các business được chọn tránh các ví dụ nhãn cá biệt đã hiển thị được xác định, nhưng không tuyên bố có quy trình giấu nhãn vật lý.

Các references nằm chung một file và công cụ có thể parse file để lọc; khóa hiện tại là giao thức + guard CLI, không phải hệ thống bảo mật ngăn người phát triển đọc nhãn. Chưa có score hay error analysis candidate nào trên holdout.

Checkpoint đề xuất: một lượt đánh giá candidate đã chọn trước release; một lượt replay cùng artifact để kiểm tra tái lập. Không mở holdout cho từng experiment. Mọi lần mở ghi append-only vào `splits/holdout_exposure.jsonl`: thời điểm, candidate hash, mục đích, người/phiên, hành động tiếp theo. `--allow-holdout` là guard kỹ thuật, không thay thế giao thức.

Nếu dùng lỗi/score holdout để sửa hoặc chọn model, ghi đã sử dụng thông tin đó và ngừng gọi kết quả tiếp theo là blind. Không reset exposure hoặc chọn holdout mới chỉ vì score thấp.

## 5. Leave-one-sector-out và stress test

Có manifest LOSO cho 5 ngành có bằng chứng input: grocery, cafe, building_materials, pharmacy, restaurant. Business chưa xác định ngành bị loại khỏi cả training và validation của bài kiểm tra khẳng định unseen industry. Các peer dùng chung schema với held industry cũng bị loại khỏi training để tránh đường tắt.

Đây là stress protocol, **chưa có kết quả mô hình**. Số business ít và một số ngành ít mẫu nên không dùng CI hay điểm LOSO để bảo đảm private. Tổng PA OOF, phân bố ngành và worst slices phải được xem cùng nhau.

Synthetic fixtures độc lập cần kiểm tra: luật thay đổi, thời gian và Tết, returned order sau as-of, null/0/out-of-range, grain/dedup/join, unit conversion, aliases, rounding, list order/table columns. Các kiểm thử semantic này phần lớn thuộc giai đoạn B; hiện mới có reader/context/scorer fixtures.

## 6. Confidence và chống chọn mô hình quá mức

Ngưỡng p>0,5 tối đa hóa kỳ vọng 2p−1 khi p là xác suất đúng của cả type+value đã được hiệu chỉnh. Không dùng confidence LLM tự báo như xác suất. Policy unanswerable cũng là một câu trả lời chịu −1 khi sai.

Không được fit calibrator/threshold trên toàn OOF rồi gọi PA policy trên chính OOF đó là đánh giá không thiên lệch. Dùng nested/cross-fit: với mỗi outer fold, fit policy bằng dữ liệu bên trong outer-training; áp một lần lên outer-validation. Sau selection có thể refit bằng development OOF cho final policy, nhưng không dùng score in-sample của policy làm bằng chứng cuối.

Mỗi batch có số run, thời gian và hypothesis định trước. So challenger/champion trên cùng subset, lưu C/W/A từng câu và paired delta. Bootstrap theo business; ghi số groups và hạn chế. Khi khác biệt không ổn định, giữ champion. Refit toàn train chỉ sau selection; provenance và final calibration policy phải được khóa, không biến train score thành generalization score.

## 7. Local scorer v1: các giả định rõ ràng

| Chi tiết | Quyết định local hiện tại | Trạng thái |
|---|---|---|
| Number | Decimal từ biểu diễn JSON, tolerance tuyệt đối 1e−9; không relative tolerance, không tự round number | Giả định epsilon, cần scorer BTC |
| Percent | ROUND_HALF_UP 2 chữ số, cả số âm | Tài liệu quy định 2 số lẻ; tie rounding chưa rõ hoàn toàn |
| String | NFC, lowercase, thay ký tự ngoài letter/digit/whitespace bằng khoảng trắng, gộp whitespace, giữ dấu | Theo mô tả Evaluation |
| List aliases | `alias[i]` là list alias cho phần tử i | Đã thấy cấu trúc này trong train, chưa có official code |
| Table aliases | `alias[row]` áp cho ô tên đầu tiên của reference row | Đã thấy cấu trúc train, giả định cách áp |
| Table columns | Nếu tập tên chuẩn hóa khớp duy nhất thì reorder toàn bộ; ngược lại fallback vị trí toàn bộ | Trường hợp match cột từng phần chưa được BTC đặc tả |
| Table rows | Exact raw duplicate rows collapse, sau đó so set qua bipartite matching | Tài liệu nói set; cách xử lý alias/normalized duplicates chưa rõ |
| Invalid/duplicate/unknown IDs, bad JSON/schema, reason không phải string | CLI báo lỗi, không tự gán điểm | Validator nghiêm hơn ingestion BTC; không mô phỏng chế tài malformed |
| Missing valid question ID | Abstain=0 | Theo tài liệu |

Các fixture riêng cho sai kiểu boolean/number, dấu tiếng Việt, thứ tự list, bảng đảo cột/dòng, alias chồng lấp và số rất lớn tránh scorer chấp nhận sai do relative tolerance. Scorer không làm rounding tiền thay cho solution; nhiệm vụ đó thuộc semantic execution/serialization theo rulebook.

## 8. Lệnh sử dụng

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/evaluate.py --splits splits/business_v2.json --subset development --predictions runs/CANDIDATE/predictions.jsonl --output runs/CANDIDATE_EVAL
```

Các tên CANDIDATE là placeholder cho artifact có thật ở giai đoạn B. Evaluator yêu cầu output directory mới, từ chối prediction ngoài subset, báo missing thành abstain. Chưa có lệnh prediction/champion stage A.
