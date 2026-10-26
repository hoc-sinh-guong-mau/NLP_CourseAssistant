# Dữ liệu

- `raw/`: tài liệu nguồn, giữ nguyên nội dung để đối chiếu.
- `db/`: knowledge base JSON đã chuẩn hóa và database SQLite được cung cấp.

Ứng dụng hiện đọc các file JSON trong `db/`; chưa truy vấn SQLite. Bản SQLite được chuyển nguyên vẹn từ `raw/`, không thay đổi nội dung. Các record JSON giữ thông tin source trỏ về tài liệu gốc.

Lịch học hiện là kế hoạch mẫu; deadline trong assignments.json vẫn là dữ liệu giả lập. Grammar và lexicon nằm ở `models/`, câu hỏi đầu vào ở `input/`, kết quả ở `output/`.
