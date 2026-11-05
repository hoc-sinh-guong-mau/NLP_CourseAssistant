# Models và cấu hình NLP

- `grammar/syntax.fcfg`: start symbol, entry rules và khung hỏi dùng chung.
- `grammar/rules/*.fcfg`: luật cấu trúc theo miền.
- `lexicon/*.yaml`: mục từ, biến thể từ để hỏi, alias và ID thực thể phục vụ parser.

Grammar và lexicon là cấu hình NLP viết tay; mô hình qtype thống kê được huấn luyện riêng từ dữ liệu tổng hợp. Không lưu dữ liệu gốc hoặc kết quả chạy trong thư mục models, ngoại trừ model và báo cáo đánh giá.

Sửa các file nguồn ở đây, sau đó chạy `python -m src.main grammar` để xuất grammar đầy đủ ra `output/grammar.txt`.

Pipeline dùng FCFG trước; mô hình qtype chỉ chạy làm dự phòng khi câu không parse được. Cài `pip install .[statistical]`, sau đó chạy `python -m src.statistical_processing.train_intent_model` để tạo dữ liệu, chia tập, huấn luyện và lưu mô hình tại `models/statistical/qtype.joblib`. Có thể ghi đè vị trí bằng `COURSE_QTYPE_MODEL`. Báo cáo đánh giá được lưu tại `models/statistical/metrics.json`.
