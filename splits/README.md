# Frozen validation manifests

`LOCK.json` chỉ định manifest đang có hiệu lực và SHA-256. Hiện dùng **business_v2.json** và **question_assignments_v2.jsonl**. Xem `docs/VALIDATION_PROTOCOL.md`.

`business_v1.json` và assignments v1 được giữ để truy nguyên, đã bị thay thế do annotation ngành bắt nhầm “Thuốc lá”. V2 sửa metadata/LOSO trước model experiments, không đổi business/fold membership. Không sử dụng sector summaries/LOSO từ v1.

Giữ nguyên manifest đã freeze. Thay đổi cần version mới và lý do, không overwrite để chọn score tốt hơn. `holdout_exposure.jsonl` ghi append-only các lần chấm/đọc lỗi candidate trên holdout; ban đầu rỗng, không có score opening. Audit metadata/input toàn train đã xảy ra trước freeze nên không gọi holdout là pristine blind.
