# Xây dựng truy vấn từ semantic representation

Chạy từ root project:

```bash
python -m src.main batch
python -m unittest discover -s tests -p 'test_queries.py' -v
```

`output/query.txt` có một dòng JSON cho mỗi câu input không rỗng, cùng thứ tự semantic.txt và intent-entity.txt. Câu không parse được, semantic chưa hỗ trợ/mơ hồ hoặc context chưa giải quyết có query `null`. Các dòng còn lại được tạo trước khi thực thi KB và sinh câu trả lời, nên vẫn có query nếu chưa có answer template.

## Trách nhiệm

- `retrieval/models.py`: QuerySpec, ConditionSpec.
- `retrieval/query_rules.py`: registry cho toàn bộ cặp INTENT/QTYPE nghiệp vụ hiện có.
- `retrieval/query_builder.py`: kiểm tra slot bắt buộc và tạo query thuần dữ liệu; không truy cập KB.
- `retrieval/knowledge_base.py`: kiểm tra query, lọc và chiếu dữ liệu trên JSON collections.
- `application/pipeline.py`: điều phối và ghi stage/error; `artifacts/exporter.py` ghi query.txt.

## Query theo ID

Semantic:

```json
{"predicate":"GET_COURSE_INFO","qtype":"DESCRIPTION","arguments":{"course_id":"CO3085"}}
```

Query:

```json
{"collection":"course","filters":{"id":"CO3085"},"select":["description"]}
```

`filters` là các điều kiện bằng nhau kết hợp AND. `select` chỉ định trường được hỏi; KB giữ thêm id, name/title nếu có và source/source_section/is_sample để truy vết và render. Trường được hỏi chưa có trong record được trả null. Khi execute một query không có select, kết quả là bản sao đầy đủ của record.

## Query quan hệ

```json
{
  "collection":"chapters",
  "filters":{},
  "select":["number","title","topic_ids","topic_evidence","topic_links_complete"],
  "conditions":[{"field":"topic_ids","operator":"contains","value":"PCFG"}]
}
```

Các operator cho trường danh sách:

- `contains`: chứa một ID.
- `contains_all`: chứa tất cả ID; quy ước cho “CFG và parsing” là **cùng một chương/tuần chứa cả hai**.
- `contains_any`: chứa ít nhất một ID; executor hỗ trợ, grammar hiện chưa có schema riêng cho phép “hoặc”.

Không dùng SQL từ text, eval hoặc chuỗi biểu thức tùy ý. Operator ngoài danh sách, slot sai kiểu, collection lạ và query sai cấu trúc đều bị từ chối bằng QueryError. Query sai có thể bị phát hiện dù collection không có record.

## Kiểm tra quan hệ và scope

“Chương 3 có CFG không?” lấy record CH03 gồm topic_ids, topic_links_complete và giữ `context.topic_id=CFG` như tham số cần kiểm tra ở bước answer. Không lọc bỏ record chương ngay khi không thấy link: điều này giúp phân biệt thiếu bằng chứng với câu trả lời “không”. topic_id là context bắt buộc cho QTYPE này.

GET_RULE lấy policy theo rule_id. Nếu semantic có assignment_id, query giữ trong context, không giả vờ rằng dữ liệu policies có cột assignment_id. Context là tham số để bước trả lời xem xét phạm vi, không phải bộ lọc và không tự chứng minh chính sách có hiệu lực cho một tình huống cụ thể.

## Các ánh xạ chính

| Intent | Collection |
| --- | --- |
| GET_COURSE_INFO | course, course_parts, learning_outcomes, exams, assessment_items |
| GET_SCHEDULE | schedule |
| GET_TOPIC | chapters |
| GET_ASSIGNMENT | assignments, assignment_parts |
| GET_DEADLINE | assignments |
| GET_RESOURCE | resources |
| GET_RULE | policies |
| GET_INSTRUCTOR | instructors |
| GET_LO | learning_outcomes |

PART_INFO/PART_OUTPUTS/PART_REQUIREMENTS/HAS_COMPONENT lọc cả assignment_id và part/component ID. REQUIREMENTS trả requirements theo từng phần; MAIN_PARTS/ASSESSMENT/LEARNING_OUTCOMES trả các record liên quan đến course_id. CHAPTER_METHODS truy xuất subtopics và summary làm bằng chứng, chưa tự trích riêng danh sách phương pháp.

## Giới hạn dữ liệu và bước tiếp theo

- Không có giảng viên: query hợp lệ, result rỗng.
- Deadline/năm xuất bản còn thiếu: query hợp lệ, giá trị null.
- Resource-topic và LO-chapter links chưa được chuẩn hóa đầy đủ: không tự suy đoán kết quả.
- Kết quả rỗng hoặc link chưa có trong bảng quan hệ không đồng nghĩa câu trả lời “không”. Phải kiểm tra completeness và nguồn khi xây answer handler.
- Chỉ deadline có answer template hiện tại. Các intent còn lại có thể trả `unsupported_answer` sau khi query/result đã có; không gọi đó là lỗi query.

Thêm một QTYPE: bổ sung semantic schema, QuerySpec/ConditionSpec và test; thêm answer handler riêng ở bước sau. UNKNOWN và CONTEXT_DEPENDENT không có query spec trước khi được nhận diện/giải quyết.
