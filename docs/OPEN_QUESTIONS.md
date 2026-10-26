# Thông tin cần bổ sung và giả định còn mở

Không có mục nào dưới đây ngăn hoàn tất stage A trên CPU. Các câu hỏi chưa được gửi ra ngoài hoặc tự suy diễn thành yêu cầu BTC.

## Cần từ BTC/tài liệu chính thức trước release

1. **General regulations đầy đủ** và thay đổi/clarification mới, vì Rule/1 dẫn chiếu nhưng workspace chưa có bản này.
2. **Docker guideline**: exact base image/digest, CUDA/framework, invocation, memory/CPU limits, output flushing, packaging training data và giải pháp khi image lớn.
3. **Official evaluator** nếu được công bố: numeric epsilon, rounding ties cho percent, alias list/table, partial column-name matching, duplicate row semantics và malformed-line handling. Local assumptions nằm trong VALIDATION_PROTOCOL §7.
4. Cách tính parameters nếu dùng model chung weights/adapters, hoặc models chỉ dùng train. Trước khi có clarification, khai báo toàn bộ model inference và đếm bảo thủ; hiện chưa dùng model.
5. Cách xử lý README mâu thuẫn rulebook hoặc thông tin thiếu/công thức không định nghĩa (ví dụ tỷ lệ có mẫu số 0). Không tự lấy nhãn test để suy luật.
6. Private release có thay đổi nào được phép với packaging/runtime hay bắt buộc frozen image tuyệt đối? Hiện áp chính sách giữ nguyên artifact theo Rule/rounds.

## Tài nguyên đã xác định và phần còn thiếu trước training/GPU dài

Người dùng đã chốt: **1× P100 16 GB trên server của mình**; không coi GPU khác là tài nguyên phát triển có sẵn. Đã có profile/setup/preflight tại `docs/P100_SERVER.md`.

- SSH alias/host, thư mục repo server, CPU/RAM/disk và driver/Python thực tế; GPU đã biết là P100 16 GB.
- Giới hạn GPU-hours/wall time và chi phí; số experiment tối đa mỗi batch.
- Quyền tải weights/datasets hợp lệ và dung lượng cho image/artifacts. Chưa tải hoặc thuê tài nguyên.

Khảo sát hiện tại: Python 3.14.4, 16 logical CPUs, MemTotal 15.194.360 kB; nvidia-smi/docker không có trên PATH. Điều này không khẳng định máy không có GPU; chỉ có nghĩa chưa xác minh GPU và không có công cụ Docker ở môi trường đang dùng. Không đọc credentials hoặc thử kết nối server khác.

## Giả định đã ghi, cần thử thêm

- Ngành từ README/product metadata là annotation BA, không official label; biz_110 vẫn unknown.
- Header trong 12 dòng đầu, UTF-8 CSV, date locale và plausible Excel serial phù hợp audit train đã chạy, chưa kiểm chứng mọi input private.
- Raw duplicate counts không đồng nghĩa lỗi, raw null không đồng nghĩa thiếu nghiệp vụ.
- Giao thức holdout hiện tại có input/aggregate metadata exposure, chưa phải môi trường giấu nhãn vật lý.
