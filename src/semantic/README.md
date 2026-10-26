# Semantic module

Luồng phụ thuộc:

```text
Parse tree → interpreter → features + rules → SemanticFrame
                                           → intent_entity.extract
```

- `models.py`: hợp đồng dữ liệu `SemanticFrame`, `SemanticRule` và kiểu nguồn slot.
- `exceptions.py`: `UnsupportedSemanticError` (thiếu schema), `InvalidSemanticError` (feature thiếu/chưa hợp nhất/mơ hồ).
- `features.py`: đọc feature ở gốc hoặc `CATEGORY.FEATURE` trong subtree; không truy cập KB.
- `rules.py`: registry schema, nhóm QTYPE có cùng vai trò slot; phát hiện khai báo trùng key.
- `interpreter.py`: class điều phối việc áp dụng schema, copy cấu hình theo instance; chỉ sử dụng API class, không tạo interpreter mới cho mỗi cây.
- `intent_entity.py`: chiếu semantic frame sang kết quả intent/entity cho output.
- `__init__.py`: API công khai cho các module bên ngoài.

Dùng từ pipeline:

```python
from src.semantic import SemanticInterpreter

interpreter = SemanticInterpreter()
frame = interpreter.interpret(tree)
```

Các bước normalize, parse, đọc/ghi file, query KB, trả lời và xử lý context nằm ngoài module này. `context_ref` chỉ là tham chiếu chưa được giải quyết.

Thêm QTYPE dùng feature sẵn có: bổ sung nhóm/mapping ở `rules.py`, không sửa vòng lặp interpreter. Nếu thêm cách lấy dữ liệu từ cây mới, phát triển `features.py` và test tương ứng. `SemanticRule` là frozen dataclass nhưng dict bên trong vẫn mutable; interpreter deep-copy cấu hình để tránh chia sẻ thay đổi giữa các instance.

Chạy test từ root project:

```bash
python -m unittest discover -s tests -p 'test_semantics.py' -v
```

## Intent và entity (Phần II)

`intent_entity.extract(frame)` lấy `predicate`, `qtype`, `arguments` của SemanticFrame và tạo `intent`, `qtype`, `entities`. Việc nhận diện dựa trên FCFG/unification và semantic schema; không phân loại lại bằng keyword. Các slot danh sách được deep-copy để kết quả không làm thay đổi semantic frame.

Pipeline gọi bước này với stage `intent_entity`, trước query, nên câu có semantic nhưng chưa có query handler vẫn có kết quả intent/entity. Parse thất bại, semantic chưa hỗ trợ hoặc nhiều cách hiểu khác nhau cho kết quả null; các ứng viên mơ hồ được giữ trong trace. Context chưa giải quyết vẫn giữ `context_ref`, không thay bằng ID đoán.

`python -m src.main batch` xuất `output/intent-entity.txt`, một dòng JSON hoặc null cho mỗi câu đầu vào không rỗng theo thứ tự. Đối chiếu cùng dòng với semantic.txt và traces.jsonl. Nếu cần kiểm tra riêng:

```bash
python -m unittest discover -s tests -p 'test_intent_entity.py' -v
```
