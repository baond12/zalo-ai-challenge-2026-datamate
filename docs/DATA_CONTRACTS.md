# Data contracts và ranh giới module

## Input

Một split cung cấp `data/<business_id>/*.{csv,xlsx,sqlite}`, `data/<business_id>/README.md`, `questions.jsonl`, `rulebook.md`, `calendar.csv`. Input runtime không cần và không được đọc answers. Source: Description/Input, Data/Package structure, Rule/5.

Question: `id`, `business_id`, `question`, `as_of_date` đều là chuỗi không rỗng. `as_of_date` được kiểm tra là ngày; mọi resolver tương lai phải lấy ngày này thay ngày hệ thống. ID dùng liên kết/log và tìm input directory, không quyết định thuật toán/đáp án. Directory traversal bị từ chối.

`SplitContext`: nội dung rulebook và calendar của root input, hash hai file, questions. `BusinessContext`: thư mục read-only, README và danh sách raw files. Không fallback sang train. API hiện tại giữ nội dung luật, **chưa diễn giải hoặc thực thi luật**.

## Raw readers hiện tại

- CSV: UTF-8/BOM, sniff delimiter trong `,;tab|`; giữ nguyên chuỗi, quote/newline. Chưa hỗ trợ fallback encoding và chưa tự diễn giải format tiền.
- XLSX: shared/inline strings, sparse cells, bool/numeric, formula cached values, styles, sheet visibility/date epoch và merged range metadata. Streaming XML. Không tính lại công thức, không fill merged cells. Chưa phải reader semantic Excel tổng quát.
- SQLite: mở `mode=ro`, `query_only=ON`; ghi lỗi bị từ chối. Audit giữ DDL/foreign-key metadata, không giả định cột có tên mã là PK/FK chính thức.
- Profile header: heuristic chọn trong 12 dòng đầu; ghi header row và preamble. Chưa chứng minh đúng cho workbook ngoài train hoặc header sâu hơn.
- Date profiling: ISO, ngày/tháng/năm, năm từ sheet khi thiếu, `thg`, Excel serial styled hoặc plausible unstyled. Cơ chế inferred được ghi riêng. Không dùng numeric serial heuristic cho mọi cột số; chỉ cột date candidate. Việc diễn giải ngày hiện tại phục vụ audit, cần semantic fixtures trước inference.

## Kế hoạch tương lai

`Planner.plan(question, split, business) -> QueryPlan`: output type, operation, parameters, supporting rule locations, required fields. `Executor.execute(plan, business) -> result`. Hai interface mới được khai báo, chưa có implementation sinh answer.

Ingestion tương lai cần giữ provenance file/sheet/row/cell, grain và mapping evidence; forward-fill/dedup phải theo nhóm và rulebook. Phần chung canonical schema có extensions/raw view cho ngành mới. Kiểm tra cardinality trước join; mask hợp lệ theo nghiệp vụ revenue/debt/stock riêng.

## Output và evaluation

Supported answer types: number, percent, string, date, boolean, list, table, unanswerable, abstain. JSON strict; bool không phải number; số không NaN/Infinity; date ISO; list chỉ tên/số; table có columns và rows cùng width. `reason` nếu có phải string. `unanswerable`/`abstain` không mang answer khác null.

Validator hiện tại báo lỗi trước khi chấm malformed submission. Nó không phải mô phỏng chính thức cách BTC xử lý dòng lỗi. Câu thiếu hoàn toàn trong predictions vẫn abstain=0. Eval tools được phép đọc references, inference context không đọc.

Submission runtime cuối cùng phải ghi `/result/submission.jsonl` tăng dần và `/result/logs/` có ID/final answer/elapsed time. Writer chịu crash, predict.sh và Docker sẽ được thực hiện ở giai đoạn sau; không có placeholder được quảng bá là giải pháp chạy được.
