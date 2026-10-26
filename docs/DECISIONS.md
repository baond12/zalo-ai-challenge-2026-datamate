# Decision log

## D001 — Scope stage A và giới hạn tài nguyên

26/10/2026: hoàn thành BA, audit, split, evaluator và scaffold CPU. Không training, tải model, inference mô hình, thuê compute hoặc submit. Chưa có GPU budget; không cản các công việc CPU. Bằng chứng môi trường: `runs/stage_a_audit_v3/environment.json`.

## D002 — Dùng thư viện chuẩn cho công việc hiện tại

Python đang có 3.14.4; openpyxl/pandas/numpy/pytest/torch không có sẵn. Chọn CSV/SQLite/ZIP/XML/Decimal/unittest từ stdlib để tránh cài nặng chỉ cho audit/eval. Reader này không phải Excel calculation engine; baseline có thể dùng dependency khác sau khi kiểm chứng nhu cầu. Không cần pip install để chạy các lệnh hiện có.

## D003 — Audit đầy đủ, không chỉnh nguồn

Quét 162 file train, 30 business, 339 bảng/sheet và 3.997.042 dòng vật lý; lưu hash, null/duplicate/key/date/category profiles. Không auto forward-fill/dedup hoặc ép missing thành 0. Full scan cuối: `runs/stage_a_audit_v3`. Audit v1/v2 giữ làm lịch sử vì đã phát hiện và sửa nhận diện unit/quantity/duration/date; không sửa dữ liệu gốc. Verification cuối so SHA-256 mọi file.

## D004 — Freeze theo business và schema family

Giữ cùng group các sale-fact headers giống nhau, thay vì random-split câu. Development=24 business/2.289 câu, holdout=6/711; 4-fold group CV. Holdout giữ cả family biz_102/103/104/121/122 và restaurant biz_129. Không có building-materials trong holdout; supplement bằng CV/LOSO và báo hạn chế thay vì tuyên bố đại diện private.

## D005 — Sửa annotation ngành trước model development

Rule metadata ban đầu dùng từ “Thuốc”, bắt nhầm “Thuốc lá” của grocery. Thay bằng bằng chứng quy tắc thuốc/hoạt chất và product-only observations. `business_v1` bị supersede bởi `business_v2`, không đổi development/holdout/CV membership. LOSO loại cả unknown-sector business khỏi training để claim unseen industry không bị nhiễm. Không có score/candidate trước revision. Bằng chứng: `splits/REVISIONS.jsonl` và regression `test_grocery_tobacco_not_misclassified_as_pharmacy`.

## D006 — Holdout khóa theo giao thức, ghi rõ exposure

Đã audit input và aggregate type train trước split; không gọi holdout pristine blind. Chưa chấm model hoặc phân tích lỗi candidate trên holdout. CLI chặn holdout mặc định; lúc mở phải có checkpoint và append exposure. Source answers chung file có thể được parse để lọc, nên guard không phải tường bảo mật. Không thay holdout vì score thấp.

## D007 — Local evaluator là bản mô phỏng có giả định

Theo Evaluation + rulebook; strict validator, number absolute epsilon 1e−9, percent HALF_UP, string normalization giữ dấu, alias list/table theo shape train, table bipartite row matching. Các chi tiết chưa đặc tả được ghi riêng, không quảng bá là code BTC. Invalid submission báo lỗi thay vì tự chọn chế tài. Tách evaluator khỏi predictor; không sửa scorer để tăng điểm.

## D008 — Không có model champion hoặc PA giải pháp ở stage A

45 tests và fixture 12 câu chứng minh các hành vi hạ tầng đã kiểm tra. Fixture PA=0,5 (8 đúng, 2 sai, 2 abstain) là expected score tính tay để kiểm chứng evaluator, không phải chất lượng agent. Không dùng reference-as-prediction để tạo điểm baseline giả. Stage B mới tạo baseline trả lời raw data.

## D009 — Nội dung public chỉ dùng đối chiếu yêu cầu

Đọc public rulebook theo stage A để ghi sự khác biệt, không đọc public business data/questions trong lượt này, không giải hay sinh nhãn/few-shot từ test. Register có luật public là documentary evidence; runtime phải đọc split rulebook, không import register làm hidden defaults.

## D010 — Bước tiếp theo

Thực hiện B01–B04 trong BACKLOG: semantic ingestion/schema/time/status và baseline CPU. Model shortlist và training đợi compute budget, nguồn weights/license/date hợp lệ. Giữ nguyên manifests/checksums, lưu tất cả OOF/error/run evidence và không mở holdout cho mỗi trial.

## D011 — Chốt giới hạn phát triển 1× P100 16 GB

Người dùng xác nhận chỉ có P100 16 GB trên server của mình. Thiết kế workflow trong giới hạn này, không thuê compute khác. Bắt đầu FP16/eager/batch1, context 2048, output 256, model ≤4B làm mức thử đầu và allocator budget 13 GiB; đây là starting policy, không phải bảo đảm mọi model vừa VRAM. Không mặc định BF16/FlashAttention/vLLM/QLoRA. Chưa có wall-time cho training dài, chưa tải/chọn model cuối.

Ghim environment candidate Python3.11/torch2.6.0 cu118 (cu124 tùy driver), Transformers4.51.3; official PyTorch v2.6 build source bao gồm sm60. Bắt buộc check arch và real FP16 GEMM trên server. Profile P100 phục vụ phát triển; release BTC Blackwell cần environment riêng. Nguồn và cách chạy ở P100_SERVER.md.

## D012 — Portable Git repo thay `.git` bị quản lý

Root `.git` là thư mục read-only do môi trường quản lý, `git rev-parse` báo không phải Git repository. Tạo Git repo độc lập dưới artifacts và local bundle/source tar bằng allowlist; data/evidence archives tách riêng, không models/credentials/runs trong source Git. Không tạo remote, push hoặc publish. Kiểm thử clone/unpack/test từ package trước chuyển server; chưa có SSH host/path nên chưa kết nối.
