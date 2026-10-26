# Cấu trúc và quy trình mở rộng

## Phân chia trách nhiệm

```text
src/
  main.py                     CLI; không chứa logic NLP
  config.py                   Các đường dẫn mặc định theo project
  preprocessing/              Normalization và tokenization
  lexical/
    models.py                 Entry
    yaml_reader.py            YAML an toàn, phát hiện trùng khóa
    validation.py             Schema entry và chuẩn hóa alias
    lexicon_loader.py         Đọc/ghép entry, sinh lexical productions
    entity_resolver.py        Tra alias, giữ đủ các ứng viên
  parsing/
    grammar_loader.py         syntax + rules/*.fcfg + lexicon
    parser.py                 FeatureChartParser
    generator.py              Sinh câu và kiểm tra lại bằng FCFG
    runner.py                 Chạy parser theo file
  semantic/
    models.py                 Frame, rule và khóa semantic ổn định
    rules.py                  Schema theo INTENT/QTYPE
    features.py               Đọc feature ở gốc/subtree
    interpreter.py            Áp dụng schema
    intent_entity.py          Chiếu frame sang output intent/entity
    exceptions.py             Lỗi diễn giải
  retrieval/
    query_builder.py          QuerySpec registry + QueryBuilder
    knowledge_base.py         Collection JSON và thực thi lọc
  generation/
    answer.py                 Registry template + AnswerGenerator
  application/
    messages.py               Thông báo theo trạng thái
    pipeline.py               Điều phối; cho phép truyền component từ ngoài
  artifacts/                  Xuất các file kết quả
  evaluation/                 Đánh giá
```

Luồng phụ thuộc: CLI → application → các module xử lý. Semantic không gọi query/KB. Grammar và lexicon không chứa câu trả lời. Module giao tiếp bằng `SemanticFrame`, query dict và danh sách KB record. Pipeline vẫn trả trace dict để exporter/CLI dùng chung.

## Thêm một alias hoặc entity

1. Chọn YAML đúng miền trong `data/lexicon/`; loader tự khám phá các file `.yaml`/`.yml` theo thứ tự tên.
2. Alias mới của entity có sẵn: thêm vào entry đó. Không tạo hai entry trùng `(category, canonical_id)`.
3. Giữ đúng category mà syntax tham chiếu và ID khớp KB. Trong miền hiện tại `bài tập 1`, `assignment 1`, `bài tập lớn` cùng là BTL01.
4. Chạy test lexicon và xuất lại grammar. Alias trùng giữa các entity được giữ để parser/semantic xử lý; không tự chọn entity đầu tiên.

## Thêm cách hỏi có cùng ý nghĩa

Sửa file tương ứng trong `data/grammar/rules/`; dùng lại INTENT/QTYPE và truyền đủ ENTITY/TARGET. Không thêm `% start` vào fragment. Nếu cùng semantic schema, không cần sửa interpreter. `syntax.fcfg` chỉ giữ entry rules S và start symbol. `common.fcfg` chứa helper dùng chung; mỗi query có file theo miền để tránh một file lớn.

Tên file fragment mới được loader tự phát hiện theo thứ tự alphabet. Thứ tự cây và câu sinh có thể thay đổi sau khi di chuyển luật; thứ tự đó không phải xếp hạng xác suất. Lệnh parse vẫn xuất cây đại diện và lưu tất cả cây trong trace.

## Thêm một loại truy vấn mới

1. Grammar: thêm QTYPE và luật trong fragment đúng miền.
2. Semantic: thêm schema ở `semantic/rules.py` để ENTITY/TARGET hoặc subtree trở thành slot có tên rõ. Đừng ánh xạ tất cả về một `entity` chung.
3. Query: thêm `QuerySpec` trong `QUERY_SPECS`, chỉ rõ collection, cặp `(KB field, semantic slot)` và trường hỏi.
4. Answer: viết hàm nhận records, trả `(status, answer)`, rồi đăng ký trong `ANSWER_HANDLERS` cùng key `(INTENT, QTYPE)`.
5. Thêm test câu hỏi → semantic → query → thông tin trả lời; thêm trường hợp thiếu dữ liệu.

`QuerySpec` hiện hỗ trợ lọc bằng nhau. Các phép tìm topic trong danh sách, so sánh ngày hoặc join chưa được triển khai; muốn hỗ trợ chúng cần mở rộng giao thức query/KB có test, không nhồi logic vào pipeline. `select` đang mô tả trường được hỏi, KB vẫn trả record đầy đủ cho renderer và nguồn.

## Thêm collection KB

Thêm `data/KB/<collection>.json`, chứa danh sách record với `id` duy nhất. KnowledgeBase tự khám phá các file JSON; tên file trở thành tên collection. Loader báo lỗi nếu rỗng thư mục, sai schema hoặc trùng ID. Thông tin mẫu/giả lập phải giữ source và nhãn mẫu.

## Thay component khi thử nghiệm

```python
assistant = CourseAssistant(
    parser=my_parser,
    semantic=my_interpreter,
    kb=my_kb,
    query_builder=my_query_builder,
    answer_generator=my_answer_generator,
)
```

Component cần giữ các method `parse_all(tokens)`, `interpret(tree)`, `execute(query)`, `build(frame)`, `render(frame, records)`. Không cần kế thừa một framework. Mặc định CLI vẫn tự tạo các component hiện tại.

## Lỗi và trạng thái

- `UnsupportedSemanticError`, `InvalidSemanticError`: khác nhau giữa thiếu schema và feature không hợp lệ.
- `UnsupportedQueryError`: chỉ dùng khi không có query spec; thiếu slot, cấu hình sai hoặc lỗi lập trình phải được phát hiện, không bị che thành unsupported query.
- `UnsupportedAnswerError`: query đã có nhưng chưa có template.
- `needs_context`: tham chiếu còn cần giải quyết; không tự đoán entity.
- Nhiều cây nhưng cùng semantic được gộp bằng canonical key; nhiều semantic trả `ambiguous`.

## Kiểm chứng

```bash
python -m unittest discover -s tests -v
python -m src.main grammar
python -m src.main parse
python -m src.main generate --limit 100
python -m src.main batch
python -m src.evaluate
```

Tests dùng thư mục tạm cho file thử nghiệm. Tests mở rộng kiểm tra registry độc lập, truyền component, collection mới, grammar fragment, và phân biệt lỗi chưa hỗ trợ với lỗi thực thi. Các test input hiện tại không thay cho benchmark độc lập.
