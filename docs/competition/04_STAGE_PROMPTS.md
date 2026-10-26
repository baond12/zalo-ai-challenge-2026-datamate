# Prompt theo từng giai đoạn và cho phiên tiếp theo

Dùng `02_MASTER_PROMPT.md` cho chỉ dẫn chung. Các prompt dưới đây giao một đầu ra cụ thể; không cần dán lại toàn bộ dữ liệu ở mỗi lần làm việc. Đây là yêu cầu để thực hiện trong tương lai, không phải danh sách việc đã hoàn thành.

## A. Khởi động: BA, audit và evaluation protocol

```text
Đọc và áp dụng docs/competition/02_MASTER_PROMPT.md.
Thực hiện giai đoạn A: BA + audit train + thiết kế evaluation.

Đọc đầy đủ năm tài liệu cuộc thi tại thư mục gốc, rulebook train,
calendar và README doanh nghiệp; đối chiếu brief hiện có. Chỉ dùng
public rulebook để xác nhận yêu cầu runtime/khác biệt được tài liệu nêu,
không giải public questions hoặc xây training examples từ public.

Tạo requirement/rule register có nguồn, data inventory và taxonomy ngành,
schema, loại câu hỏi, output type, mức đầy đủ dữ liệu. Kiểm tra grain,
keys, dates, units, duplicates, missingness, status và quan hệ bảng trên
train. Trình bày kết quả quan sát được và phần chưa audit rõ ràng.

Khảo sát compute read-only, không tiết lộ credentials. Tạo scaffold
modular tối thiểu, PROJECT_STATE, DECISIONS và VALIDATION_PROTOCOL.
Chốt manifest split theo business trước tuning, ghi holdout policy.
Xây local evaluator và fixture độc lập cho PA, matching, format và
rounding; ghi rõ chỗ chỉ mô phỏng vì chưa có scorer chính thức.
Chạy kiểm thử CPU phù hợp, báo command và kết quả thật.

Kết thúc bằng backlog ưu tiên theo khả năng cải thiện PA, effort và
rủi ro; ghi những câu hỏi cần BTC/compute budget. Chưa tải model lớn,
chưa training, chưa submit. Không dừng chỉ ở một bản kế hoạch.
```

## B. Baseline end-to-end

```text
Đọc master prompt, PROJECT_STATE và VALIDATION_PROTOCOL; tiếp tục repo
hiện có. Hoàn thành baseline chạy raw package + questions -> JSONL/logs
-> local evaluation trên train development theo split đã khóa.

Implement readers CSV/XLSX/SQLite có provenance, schema discovery,
runtime rulebook/calendar, entity/time resolution và operations tính toán
đúng. Dùng abstain cho câu chưa hỗ trợ thay vì bịa đáp án. Không hard-code
ID/business/answer; không dùng toàn bộ nhãn train làm inference lookup.

Có một lệnh predict và một lệnh evaluate. Chạy thật trên phạm vi đã định,
báo PA, C/W/A, coverage, slices và runtime. Nếu đủ compute budget, so một
số ít model eligible theo cùng giao thức; xác minh release date/license/
total parameters trước khi dùng. Nếu thiếu budget, hoàn thành baseline
CPU và phần không phụ thuộc model, ghi rõ giới hạn.

Lưu baseline bất biến, error taxonomy, experiment ledger và state.
Chưa mở holdout hoặc sinh public submission trừ khi được giao cụ thể.
```

## C. Một vòng tối ưu có bằng chứng

Điền ngân sách nếu đã có. Đừng gửi placeholder như một con số thật.

```text
Đọc master prompt, state, champion và error report. Chạy một batch tối ưu
trên development; tối đa [số run] và [GPU-hours/giờ chạy] đã được cấp.

Xác định nhóm lỗi gây mất PA lớn nhất, phân biệt lỗi ingestion, schema,
ngữ nghĩa luật, entity/time, execution, serialization và confidence.
Ưu tiên theo số câu có thể sửa và giá trị PA kỳ vọng trên validation,
effort, khả năng tổng quát hóa và runtime.

Đề xuất ít giả thuyết rõ ràng rồi thực hiện phương án ưu tiên trong
ngân sách. Một thay đổi chính mỗi experiment; so cùng split/config nền,
lưu dự đoán từng câu và thực hiện ablation cần thiết. Nếu có training,
few-shot, synthetic hoặc calibrator, đảm bảo fit riêng trong fold train.

Báo paired delta PA, uncertainty theo business, coverage, regressions,
worst slices và runtime. Chỉ cập nhật champion khi có bằng chứng phù hợp;
nếu chưa đủ thì giữ champion và ghi kết luận âm. Không mở holdout hoặc
tune theo public leaderboard. Kết thúc bằng state và ưu tiên batch sau.
```

## D. Mở rộng một năng lực mà không làm vỡ giải pháp

```text
Đọc master prompt và state. Mở rộng năng lực: [mô tả lỗi/năng lực cần thêm].
Xác định contract và module phù hợp; tái sử dụng kiến trúc hiện có.
Tạo fixture nhỏ có expected tính độc lập, phản ánh nguyên nhân lỗi trên
train-development hoặc synthetic hợp lệ. Không viết nhánh theo ID hoặc
tên business, không nhét luật public/private thành fallback trong code.

Implement, chạy regression liên quan rồi đánh giá trên cùng dev protocol.
So PA và runtime với champion; giải thích ảnh hưởng chéo tới nghiệp vụ
khác. Nếu rule/schema mới là input, chứng minh hệ thống tiếp nhận chúng
ở runtime mà không phải sửa tay theo từng business.

Lưu thay đổi, bằng chứng, quyết định giữ/bỏ và cập nhật docs/state.
```

## E. QA phản biện trước release

```text
Đóng vai QA phản biện cho candidate [run/release ID], không mặc định
chấp nhận kết luận của lượt triển khai. Đọc master prompt, protocol,
requirements, lineage, code/config và evidence của candidate.

Trước tiên kiểm tra các lỗi có thể khiến PA đang báo không đáng tin:
label/test leakage, random split cùng business, template/synthetic leakage,
holdout đã được dùng tuning, model inventory thiếu và logic theo ID.

Tiếp theo kiểm tra semantics, temporal/status exceptions, grain/joins,
units/rounding, unanswerable/abstain, generalization và bounded runtime.
Chạy các checks đã có và bổ sung kiểm tra đúng rủi ro còn thiếu.
Chỉ mở holdout nếu đúng checkpoint protocol; không tự sửa candidate
dựa trên holdout rồi báo cùng kết quả đó là đánh giá mù.

Kiểm tra Docker offline/read-only/cold start, incremental output/logs,
VRAM/RAM, runtime và replay. Báo PASS/FAIL/NOT VERIFIED kèm evidence cho
từng mục trong workflow; phân loại blocker và sai lệch chưa giải thích.
Chưa có máy tham chiếu/guideline thì nêu chưa xác minh, không đánh dấu PASS.

Xuất QA report và verdict có điều kiện rõ ràng. Không tự submit hay
chỉnh đáp án test. Phân biệt lỗi cần quay lại development và việc có thể
khắc phục packaging mà không thay đổi behavior.
```

## F. Chuẩn bị public submission và freeze

```text
Đọc master prompt, state và QA report. Dùng champion đã chỉ định để
chạy public inference tự động bằng pipeline hiện có. Public là input
inference; không lấy kết quả/nhãn suy đoán để training hoặc điều chỉnh
đáp án thủ công. Không dò điểm từng câu bằng nhiều lần nộp có chủ đích.

Validate JSONL, coverage, logs và runtime. Ghi version của mọi artifact
và checksum output. Giữ lịch sử public score nếu người dùng cung cấp,
nhưng lựa chọn champion phải dựa chủ yếu trên giao thức train validation;
ghi rõ mọi quyết định chịu ảnh hưởng leaderboard.

Theo Docker guideline BTC, đóng gói source/weights/config/dependencies/
README/data cần thiết hợp lệ; chạy offline replay từ cold start.
Freeze release manifest và checksum. Báo ready chỉ khi đủ evidence,
liệt kê mục chưa xác minh nếu còn. Chuẩn bị file và chỉ dẫn nộp;
chưa upload/chia sẻ công khai/submit nếu chưa được yêu cầu rõ.
```

## G. Chạy private bằng giải pháp đã freeze

```text
Đọc release manifest, kiểm tra checksum và hướng dẫn BTC. Chạy đúng
frozen image [release ID] trên private input theo contract; không sửa
code, prompts, weights, thresholds hoặc đáp án bằng tay theo private.
Schema/README/rulebook mới được xử lý bởi thuật toán runtime đã freeze.

Theo dõi tài nguyên, thời gian, output/logs. Validate contract bằng công
cụ đã có; không đoán PA vì không có reference. Giữ output gốc và checksum,
báo tình trạng coverage/termination và vấn đề reproducibility nếu có.
Không tự sửa giải pháp khi phát hiện lỗi phụ thuộc private; ghi bằng chứng
và đối chiếu hướng dẫn BTC. Chuẩn bị artifact nộp và chờ lệnh nộp cụ thể.
```

## H. Tiếp tục ở phiên mới, giữ nguyên mục tiêu

```text
Tiếp tục dự án DataMate tại /home/baond12/Documents/ZL_AI_Challenge.
Đọc docs/competition/02_MASTER_PROMPT.md, docs/PROJECT_STATE.md,
docs/DECISIONS.md, validation protocol và evidence champion gần nhất.
Nếu file state chưa có, nói rõ và dựng trạng thái từ artifact thực tế.

Xác nhận ngắn: champion và PA đo bằng giao thức nào, việc đang dang dở,
ngân sách còn được cấp và bước tiếp theo. Hoàn thành bước tiếp theo có
giá trị nhất trong phạm vi đã được giao; không làm lại phần đã xong.
Không tự mở holdout, chạy GPU dài ngoài budget hoặc dùng test để học.
Cuối phiên cập nhật state/decisions/ledger, kèm commands và evidence.
```

## 5 câu hỏi đọc nhanh mỗi báo cáo

1. Con số này đã đo thật chưa, trên dữ liệu và split nào?
2. Bản mới tăng PA do sửa ngữ nghĩa tổng quát hay do học thuộc mẫu/business?
3. Có nhãn, synthetic, example hoặc threshold nào đi qua ranh giới validation/test?
4. Nếu schema, ngành hoặc rulebook thay đổi, thuật toán xử lý bằng cơ chế gì và đã kiểm tra ra sao?
5. Có thể chạy lại offline bằng đúng release, trong tài nguyên/thời gian BTC, và giải thích output bằng evidence không?
