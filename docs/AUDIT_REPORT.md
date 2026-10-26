# Train audit — stage A, 26/10/2026

Bằng chứng chính: `runs/stage_a_audit_v3/summary.json`, `tables.json`, `businesses.json`, `relationships.json`, `input_manifest.json` và `derived_findings.json`. Báo cáo được sinh bằng `scripts/render_audit_report.py` từ full physical scan, không dựa trên sampling để đếm dòng/null/duplicate.

## Phạm vi và tình trạng

Đã đọc 30 README, 3,000 questions và kiểm tra contract/ID của 3,000 train references; quét tất cả CSV/XLSX/SQLite trong train. Có 339 bảng/sheet, 3,997,042 dòng vật lý sau header/preamble được nhận diện. Đây là tổng trên mọi bảng, **không phải số giao dịch độc lập**. Audit hoàn tất trong 194.762 giây ở lượt cuối, không có lỗi đọc file.

Đã đọc năm tài liệu cuộc thi và đối chiếu rulebook train/public. Không giải public questions, không đọc business data public/private trong stage A. Reference values chỉ phục vụ contract và thống kê shape/type; không có candidate được chấm trên holdout.

## Phát hiện đã đo

- Header row distribution: {1: 224, 2: 34, 3: 42, 4: 39}. 115 sheet/table có header sau dòng 1; parser không thể mặc định hàng đầu là header.
- 103,108 dòng có cùng decoded values với dòng trước đó trong cùng bảng/sheet. Đây là count quan sát, không phải số lỗi cần xóa. Không fill/dedup dữ liệu gốc; merged/blank order fields có thể khiến dòng trông giống nhau trước khi khôi phục nhóm.
- 216 column occurrences hoàn toàn trống, 597 có null một phần. Đếm theo bảng/sheet nên cột lặp qua các tháng được đếm nhiều lần. Không tự biến missing thành zero.
- 33 column occurrences có giá trị số âm. Chưa kết luận toàn bộ là trả hàng; cần role và README/status để diễn giải.
- 2,447,983 ô trong các cột date-candidate được nhận diện ngày; 0 ô không trống còn unparsed theo heuristic hiện tại. Không có nghĩa mọi mapping/ngữ nghĩa ngày đã được xác minh.
- Date parse modes: {'text_date': 1789600, 'numeric_excel_serial_styled': 438343, 'numeric_excel_serial_inferred': 195009, 'text_excel_serial_inferred': 25031}. Có text tiếng Việt `thg`, serial dạng numeric và serial lưu trong string; serial không style được đánh dấu inferred.
- Calendar có 1461 ngày duy nhất, liên tục 2024-01-01..2027-12-31. Chưa kiểm chứng tính đúng của từng quy đổi âm dương bằng nguồn ngoài; runtime dùng lịch BTC cung cấp.
- 408 candidate joins từ role/unique-key/overlap; 190 không có distinct child key ngoài parent. Các candidate còn lại có thể do partition theo tháng, phạm vi khác hoặc mapping sai; chưa gọi là referential-integrity violations.
- README không có section dictionary cột: biz_106, biz_109, biz_123, biz_124. Các README này vẫn có conventions hữu ích; cần schema discovery thay vì đòi đủ dictionary.
- Không có formula cell được reader phát hiện. Không thực hiện tính lại công thức Excel.

Ví dụ quan hệ có bằng chứng: biz_111 `don_hang.csv` có 66.469 distinct order IDs; `chi_tiet_don.csv` có 106.585 dòng gắn đủ 66.469 IDs, không có distinct orphan; tối đa 3 dòng hàng/đơn. `thanh_toan.csv` có thể có tới 4 dòng/đơn. Join trực tiếp cả hai detail tables vào header có nguy cơ nhân chéo tiền/số lượng: cần aggregate theo grain trước join.

## Taxonomy

Nhãn ngành là annotation BA dựa README và product-only observations. Có 6 grocery, 5 cafe, 6 building_materials, 6 pharmacy, 6 restaurant và 1 unknown. biz_110 chỉ có invoice-level data, chưa có đủ bằng chứng ngành nên giữ unknown. Không dùng các nhãn/ID này như routing rules trong solution.

Question tags dưới đây là regex không loại trừ nhau, có thể false positive/negative; không phải intent labels chính thức hoặc độ khó đã xác nhận:

| Tag | Câu match |
|---|---:|
| units | 1795 |
| revenue | 1035 |
| relative_time | 756 |
| ranking | 431 |
| comparison | 327 |
| debt | 116 |
| purchase | 114 |
| profit_cost | 46 |
| inventory | 40 |
| lunar | 5 |

Answer type: number=1884; percent=578; string=88; list=193; unanswerable=70; date=145; table=19; boolean=23. Number+percent=2.462/3.000 (82,07%); đây là cơ sở ưu tiên deterministic execution, không phải cam kết private có cùng phân bố.

## Inventory theo business

| Business | Ngành (annotation) | Bảng/sheet | Dòng vật lý | Raw duplicate | Câu hỏi | Cutoff README |
|---|---|---:|---:|---:|---:|---|
| biz_101 | grocery | 1 | 56,501 | 0 | 40 | 2026-08-24 |
| biz_102 | grocery | 19 | 86,106 | 0 | 119 | 2026-06-16 |
| biz_103 | grocery | 17 | 45,611 | 11,728 | 119 | 2026-07-09 |
| biz_104 | cafe | 2 | 62,896 | 0 | 119 | 2026-06-02 |
| biz_105 | cafe | 21 | 141,748 | 2,222 | 119 | 2026-06-24 |
| biz_106 | cafe | 10 | 289,353 | 3,230 | 119 | 2026-09-14 |
| biz_107 | grocery | 1 | 43,605 | 5,756 | 40 | 2026-07-22 |
| biz_108 | grocery | 7 | 113,696 | 0 | 119 | 2026-05-29 |
| biz_109 | grocery | 9 | 156,626 | 0 | 118 | 2026-08-05 |
| biz_110 | unknown | 1 | 29,317 | 0 | 40 | 2026-07-03 |
| biz_111 | cafe | 5 | 239,499 | 0 | 118 | 2026-08-19 |
| biz_112 | cafe | 17 | 113,375 | 0 | 118 | 2026-07-31 |
| biz_113 | building_materials | 1 | 32,994 | 5,285 | 40 | 2026-08-09 |
| biz_114 | building_materials | 1 | 26,119 | 0 | 40 | 2026-06-21 |
| biz_115 | building_materials | 19 | 55,962 | 0 | 118 | 2026-05-16 |
| biz_116 | building_materials | 4 | 79,117 | 0 | 118 | 2026-09-03 |
| biz_117 | building_materials | 23 | 66,286 | 473 | 118 | 2026-05-20 |
| biz_118 | building_materials | 23 | 92,169 | 0 | 118 | 2026-09-10 |
| biz_119 | pharmacy | 28 | 172,569 | 1,908 | 118 | 2026-07-13 |
| biz_120 | pharmacy | 27 | 240,702 | 0 | 118 | 2026-06-12 |
| biz_121 | pharmacy | 7 | 172,139 | 35,380 | 118 | 2026-09-20 |
| biz_122 | pharmacy | 26 | 214,306 | 24,975 | 118 | 2026-07-17 |
| biz_123 | pharmacy | 17 | 268,911 | 1,208 | 118 | 2026-06-28 |
| biz_124 | pharmacy | 13 | 305,973 | 1,188 | 118 | 2026-05-25 |
| biz_125 | restaurant | 1 | 79,052 | 0 | 40 | 2026-05-11 |
| biz_126 | restaurant | 1 | 66,429 | 5,713 | 40 | 2026-06-06 |
| biz_127 | restaurant | 5 | 198,800 | 2,899 | 118 | 2026-07-28 |
| biz_128 | restaurant | 25 | 152,259 | 1,143 | 118 | 2026-09-07 |
| biz_129 | restaurant | 5 | 222,331 | 0 | 118 | 2026-08-14 |
| biz_130 | restaurant | 3 | 172,591 | 0 | 118 | 2026-08-29 |

## Chưa xác minh / giả định

- Header và role detection là heuristic. Stage B phải dùng README + raw provenance, kiểm tra grouping, metadata rows, status và cardinality trước tính đáp án; không coi profile là semantic adapter hoàn chỉnh.
- Số có dấu phân cách tiền chưa được ép thành numeric trong audit; các thống kê numeric chỉ chắc cho plain numbers. Không tự đoán dấu chấm/phẩy là thập phân hay hàng nghìn ở inference.
- Date ranges theo column có thể là order date, payment date, expiry, registration…; không dùng min/max của mọi cột làm coverage của doanh nghiệp.
- Chưa aggregate các file/sheet cùng một logical table, chưa xác minh toàn bộ composite keys, cross-file duplicate và entity aliases. Các profile là vật lý, joins là candidate.
- Chưa chạy SQL trả lời câu train, chưa xác minh reference từng câu, chưa có accuracy/PA của mô hình, chưa có confidence calibration.
- Chưa có GPU/Docker reference benchmark; chỉ xác nhận công cụ nvidia-smi và docker không có trên PATH hiện tại.

## Lịch sử audit

v1 là full scan đầu tiên; v2 sửa phân biệt quantity/unit/duration, format `thg` và numeric serial; v3 bổ sung serial-as-text và duration label, là bản hiện hành. Ba bản giữ nguyên count physical rows/duplicate. Giữ các bản cũ để truy nguyên; không chỉnh source data. Verification cuối kiểm tra lại SHA-256 toàn bộ 162 file train.
