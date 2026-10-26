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
- `interpreter.py`: class điều phối việc áp dụng schema, copy cấu hình theo instance; API hàm `interpret(tree)` vẫn được giữ.
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
