# Models và cấu hình NLP

- `grammar/syntax.fcfg`: start symbol và entry rules.
- `grammar/rules/*.fcfg`: luật cấu trúc theo miền.
- `lexicon/*.yaml`: mục từ, alias và ID thực thể phục vụ parser.

Đây là cấu hình NLP viết tay, chưa phải model học máy được huấn luyện. Model thống kê và cấu hình đi kèm có thể bổ sung tại đây sau. Không lưu dữ liệu gốc hoặc kết quả chạy trong models.

Sửa các file nguồn ở đây, sau đó chạy `python -m src.main grammar` để xuất grammar đầy đủ ra `output/grammar.txt`.
