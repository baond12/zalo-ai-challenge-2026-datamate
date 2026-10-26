# DataMate 2026 — Bản cô đọng để ra quyết định

Ngày đọc tài liệu: 26/10/2026, múi giờ Việt Nam. Đây là bản tóm tắt từ tài liệu local người dùng cung cấp, không phải thông báo mới được xác minh trên cổng BTC. Khi BTC cập nhật, phải cập nhật bản này và ghi lịch sử thay đổi.

## 1. Mục tiêu và phạm vi

Xây dựng agent trả lời câu hỏi tiếng Việt trên CSV, Excel, SQLite của một doanh nghiệp. Input còn có README, `as_of_date`, rulebook và lịch âm dương của split. Output là giá trị có kiểu chính xác, `unanswerable`, hoặc `abstain`.

Mục tiêu dự án là tối đa hóa khả năng đạt PA cao trên doanh nghiệp/ngành mới, trong giới hạn tính toán và thể lệ. Chưa có mô hình hay thực nghiệm được triển khai trong bộ tài liệu này. Không thể hứa chiến thắng hoặc bảo đảm điểm private từ điểm public.

Nguồn gốc yêu cầu:

| Nguồn tại thư mục gốc | Nội dung dùng làm căn cứ |
|---|---|
| `Description.txt` | Bài toán, input/output |
| `Evaluation.docx` | Matching từng kiểu, PA, tie-break |
| `Data.docx` | Cấu trúc split, ngành mới, rulebook theo split, Docker và log |
| `Rule.txt`, mục 1–8 | Điều kiện mô hình, dữ liệu, offline, tài nguyên, tái lập |
| `Submission Guidance.txt` | Mốc thời gian, quota, hình thức nộp |
| `train/rulebook.md`, `public_test/rulebook.md` | Ngữ nghĩa nghiệp vụ và khác biệt đã đọc |
| `train/questions.jsonl`, `train/answers.jsonl` | Thống kê quan sát trực tiếp dưới đây |

## 2. Các ràng buộc không được bỏ sót

| Ràng buộc từ tài liệu | Hệ quả thiết kế |
|---|---|
| PA = (correct − wrong) / N; abstain = 0 | Tối ưu quyết định trả lời, không chỉ accuracy trên số câu đã trả lời |
| Sai type hoặc sai giá trị: −1, không partial credit | Serializer, rounding, thứ tự list là thành phần của giải pháp |
| Tổng tham số mọi model inference ≤15 tỷ, kể cả model không nạp cùng lúc và toàn bộ tham số MoE | Lập inventory LLM, embedding, reranker, classifier; lượng tử hóa không giảm số tham số |
| Weights công khai **trước 01/10/2026**, license cho phép; được fine-tune | Xác minh ngày, revision và license từng model; không chọn chỉ theo tên hoặc kích thước |
| Inference hoàn toàn offline, không download, không external service | Đóng gói weights/tokenizer/dependencies; smoke test tắt mạng |
| Không hard-code đáp án hoặc logic theo question/business ID | ID chỉ để liên kết, chia nhóm, log; mapping nghiệp vụ phải suy ra từ input |
| Không dùng public/private test để training hoặc thu thập đáp án | Không fine-tune, distill, tạo few-shot hoặc nhãn pseudo từ test; không dò đáp án qua leaderboard |
| Private có ngành chưa xuất hiện ở train/public | Cần validation theo ngành và schema mới, không chỉ doanh nghiệp mới |
| 2×RTX 5090, mỗi GPU 32 GB; RAM 512 GB; cả private ≤6 giờ, gồm load model | VRAM hai GPU không mặc nhiên là một vùng liên tục; đo phân bổ model, preprocessing, inference và logging |
| Blackwell cần CUDA ≥12.8, PyTorch/vLLM phù hợp | Dùng base image BTC chỉ định khi nhận được Docker guideline |
| `predict.sh`: đọc `/data`, ghi `/result/submission.jsonl` và log từng câu ở `/result/logs/` | Data read-only; temp/cache ghi nơi khác; lưu kết quả tăng dần để chịu timeout |
| Chênh PA uploaded/re-run ≤0,03 | Khóa code/config/weights/image, seed; đo sai khác từng câu qua nhiều lần chạy |
| Điểm cuối từ BTC re-run; quá giờ/termination: chỉ chấm output đã ghi | Không phụ thuộc cache ngoài image; cần checkpoint output hợp lệ |

Tài liệu hiện có chưa gồm quy định chung đầy đủ và Docker guideline riêng. Chưa rõ chi tiết cách tính các adapter/model dùng chung trọng số, yêu cầu packaging cụ thể và các tình huống chấm không được mô tả. Ghi thành câu hỏi cần xác minh, không tự suy diễn thành luật.

## 3. Scoring và chiến lược abstain

- `number`: khớp giá trị reference; reference nguyên hoặc làm tròn 2 số lẻ. Rulebook quy định chi tiết: tiền làm tròn đồng, trung bình tiền cũng vậy; trung bình khác và % thường 2 số lẻ. Dùng số thập phân có chính sách rounding rõ ràng, tránh áp `round()` mặc định máy móc.
- `percent`: đơn vị phần trăm, ví dụ `12.4` thay vì `0.124`; giữ dấu tăng/giảm.
- `string`: NFC, lowercase, bỏ dấu câu bằng khoảng trắng, gộp khoảng trắng; **không bỏ dấu tiếng Việt**. Alias hợp lệ từ dữ liệu và mã đối tượng.
- `date`: ISO ngày hoặc tháng theo câu hỏi.
- `boolean`: JSON boolean.
- `list`: luôn có thứ tự; tie-break theo mã tăng dần, không có mã thì theo tên theo rulebook. Ít hơn k thì trả tất cả.
- `table`: các dòng so như một tập, cột so tên chuẩn hóa rồi fallback vị trí; giá trị ô theo quy tắc tương ứng.
- `unanswerable`: kết luận dữ liệu không đủ; đúng +1 chỉ khi reference cũng như vậy. Thiếu cột cần thiết hoặc kỳ hoàn toàn ngoài phạm vi khác với giá trị 0.
- `abstain`: hệ thống chưa đủ chắc; luôn 0, kể cả reference là unanswerable.

Nếu xác suất **toàn bộ đáp án, gồm type**, đúng là p đã được hiệu chỉnh, kỳ vọng trả lời là `2p−1`; abstain là 0. Ngưỡng lý tưởng >0,5 chỉ là kết quả toán học khi p đáng tin cậy, không phải mặc định sử dụng một con số LLM tự báo. Chọn và hiệu chỉnh chính sách bằng dự đoán ngoài mẫu trong train. `unanswerable` cũng là một ứng viên trả lời chịu ngưỡng tin cậy.

Local evaluator chỉ xấp xỉ scorer BTC ở phần chưa có code chính thức: epsilon số thực, rounding tại điểm giữa, alias trong list/table và đối sánh cột còn có thể cần xác minh. Cần test fixture và ghi rõ giả định, không sửa scorer chỉ để làm điểm đẹp.

## 4. Kiểm kê đã thực hiện, chưa phải EDA đầy đủ

| Nội dung | Train | Public test |
|---|---:|---:|
| Doanh nghiệp trong questions | 30 | 14 |
| Câu hỏi | 3.000 | 1.000 |
| CSV dữ liệu doanh nghiệp | 20 | 10 |
| XLSX dữ liệu doanh nghiệp | 107 | 69 |
| SQLite dữ liệu doanh nghiệp | 1 | 1 |
| README doanh nghiệp | 30 | 14 |

Đếm định dạng trong `data/`, không tính calendar và các file ở gốc split. Tổng dung lượng file trong `data/` khoảng 193,5 MB train và 109,1 MB public theo byte thập phân. Train có ID questions/answers duy nhất và hai tập ID khớp nhau.

Phân bố type train: number 1.884 (62,80%); percent 578 (19,27%); list 193; date 145; string 88; unanswerable 70; boolean 23; table 19. Number + percent chiếm 82,07%: ưu tiên tính toán đúng có tiềm năng lớn, nhưng chưa biết phân bố private. Mỗi doanh nghiệp có 40–119 câu, vì vậy báo cáo cả PA theo câu và PA macro theo doanh nghiệp; chỉ PA theo câu là metric chính thức.

## 5. Rủi ro nghiệp vụ đã xác nhận

1. **Rulebook khác giữa split**: public bổ sung khách trung thành theo số ngày mua, khách sộp theo AOV với ≥3 đơn, mặt hàng ưa chuộng theo số đơn, nhà cung cấp chính theo số phiếu. Không dùng nhầm mặc định “nhiều tiền/số lượng”. Một số quy định train không còn có trong public; không mang luật vắng mặt sang bằng code fallback ẩn.
2. **Thời gian**: lấy `as_of_date`, không lấy ngày máy; tháng này tới hết hôm nay; so tháng trước theo cùng số ngày. Tết dùng calendar của split.
3. **Ngoại lệ dữ liệu tương lai**: dữ liệu phát sinh sau hôm nay thường không được tính trong câu hỏi hiện tại, nhưng trạng thái hủy/trả của đơn lấy theo trạng thái ghi nhận, kể cả trả sau hôm nay. Không dùng bộ lọc ngày toàn cục làm mất ngoại lệ này.
4. **Hủy/trả một phần**: bỏ cả đơn khỏi doanh thu; đơn trả vẫn có thể vào công nợ. Không dùng chung một mask “đơn hợp lệ” cho mọi nghiệp vụ.
5. **Hạt dữ liệu**: một dòng có thể là dòng hàng hoặc một phiếu độc lập; thông tin đầu nhóm có thể để trống ở các dòng sau. Forward-fill phải trong nhóm hợp lệ; dedup đúng phạm vi, không xóa mọi dòng giống nhau.
6. **Tiền/đơn vị**: doanh thu, tổng khách phải trả, tiền đã thu, giá vốn và tồn kho có định nghĩa khác nhau; số lượng theo đơn vị bán khác số lượng cơ bản.
7. **Ngành mới**: public có luật sửa xe, điện thoại, mẹ và bé; schema chuẩn hóa cần giữ cả phần mở rộng và dữ liệu gốc.

Hướng kiến trúc để thử nghiệm: đọc và mô tả schema → suy ra mapping có bằng chứng → diễn giải câu hỏi và rulebook → lập kế hoạch có cấu trúc → thực thi SQL/Python → kiểm tra kết quả → quyết định answer/unanswerable/abstain → serialize và log. Đây là giả thuyết thiết kế, chưa phải kết luận về phương án tốt nhất.

## 6. Lịch từ Submission Guidance

Tất cả mốc GMT+7, năm 2026 theo tài liệu:

- Public: 26/10–16/11; tối đa 5 lần/ngày, reset cuối ngày.
- Giải pháp Docker: hạn **16/11, 23:59**; tối đa 2 bản, BTC chỉ đánh giá bản cuối. Nộp qua form với checksum và link Google Drive công khai.
- Private: phát hành **20/11, 09:00**, hạn kết quả **23/11, 23:59**; chạy giải pháp đã freeze.
- Công bố top 2: 02/12.

## 7. Những gì cần bổ sung khi bắt đầu triển khai

- Compute thực tế, quyền dùng server/GPU, thời lượng chạy và dung lượng đĩa.
- Quy định chung và Docker guideline chính thức; nguồn cập nhật từ BTC.
- Baseline, local scorer đã kiểm tra, split cố định, ngân sách thực nghiệm.
- Không coi việc chưa có GPU là lý do dừng BA, audit, scorer, parser và kiểm thử CPU.
