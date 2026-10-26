# Knowledge Base đã chuẩn hóa

## Tái tạo và nguồn sự thật

```bash
python -m src.main normalize-kb
python -m unittest discover -s tests -p 'test_kb_normalization.py' -v
python -m src.main batch
```

`retrieval/normalization/readers.py` đọc định dạng text được cung cấp; `builder.py` chuẩn hóa ID và các trường; `validation.py` kiểm tra provenance, ID và liên kết trước khi ghi JSON. Không dùng FAQ, sample queries hoặc câu trả lời hội thoại làm bảng đáp án thay cho dữ liệu gốc.

Lệnh ghi lại 14 file JSON được quản lý trong `data/db/`. Những collection tùy chỉnh khác và SQLite không bị sửa. Toàn bộ dữ liệu được parse/validate trước khi ghi; thao tác ghi nhiều file không phải transaction database. Nếu có lỗi I/O giữa chừng, sửa lỗi và chạy lại lệnh để tái tạo đầy đủ.

Tài liệu raw và lexicon được giữ nguyên. SQLite legacy có thể khác JSON; backend đang hoạt động là JSON, không đồng bộ ngầm hai nguồn. `output/kb-normalization.json` chứa số lượng record và các vấn đề chất lượng nguồn.

## Collection và ID

| Collection | ID / trường chính | Nguồn |
| --- | --- | --- |
| course | CO3085; credits, description, objectives, format, duration_weeks, hours | course_info.txt |
| course_parts | SYNTACTIC_PROCESSING, SEMANTIC_INTERPRETATION, CONTEXT_WORLD_KNOWLEDGE | course_info.txt |
| exams | MIDTERM, FINAL; duration_minutes, open_book, format | course_info.txt |
| assessment_items | CLASS_ATTENTION_AND_ASSIGNMENTS, MAJOR_ASSIGNMENT, MIDTERM, FINAL; weight_percent | course_info.txt |
| learning_outcomes | LO1–LO4, LO1.1…LO4.2; parent_id, description | course_info.txt |
| chapters | CH01–CH12; summary, keywords, subtopics, topic_ids | topics.txt |
| topics | canonical IDs từ category TOPIC; aliases, chapter_ids | lexicon và bằng chứng trong topics.txt |
| schedule | WEEK_01–WEEK_15; week, chapter_ids, topic_ids, topics, activity, milestone | schedule.txt |
| assignments | BTL01; title, goal, domain, team_size, part_ids, deadline, milestones | assignments.txt và schedule.txt |
| assignment_parts | PART_I–PART_IV; assignment_id, requirements, outputs, optional | assignments.txt |
| resources | TEXTBOOK_1–3, REFERENCE_1–5; title, authors, publisher, year, category_ids | resources.txt |
| resource_categories | STATISTICAL_NLP, PYTHON_NLP, MACHINE_TRANSLATION, WORLD_KNOWLEDGE | lexicon |
| policies | ATTENDANCE, ACADEMIC_INTEGRITY, AI_USAGE, SOURCE_CODE, ASSIGNMENT_SHARING, EXTERNAL_LIBRARIES, LLM_RAG, OUT_OF_SCOPE | regulations.txt |
| instructors | Danh sách rỗng; chưa có tên giảng viên trong nguồn | Chưa có |

Mọi record có `id`, `source`, `source_section`, `is_sample`. `is_sample: false` nghĩa là record không thuộc nhóm được đánh dấu mô phỏng, không chứng nhận đó là thông tin hành chính chính thức. `MAJOR_ASSIGNMENT` là mục trọng số đánh giá, không phải ID của bài tập `BTL01`. PART_I là phần bài tập, khác phần nội dung môn học SYNTACTIC_PROCESSING.

## Quan hệ và bằng chứng

- ID chương/chủ đề/tuần dùng đúng canonical ID trong lexicon; không dùng tên hiển thị để join.
- `chapter_ids` và `topic_ids` là danh sách, hỗ trợ nhiều–nhiều.
- Link chapter↔topic và week→topic được tạo từ các đề cập thực sự trong văn bản, ưu tiên alias dài khi có chồng lấn, kèm một số biến thể spelling của nguồn. `topic_evidence` ghi chuỗi khớp. Topic có `chapter_link_source` trỏ về raw/topics.txt.
- `topic_links_complete` / `chapter_links_complete` là false: các link này chỉ là bằng chứng tìm thấy, không phải annotation đầy đủ. Không dùng link thiếu để kết luận một chương không có chủ đề.
- PCFG được liên kết với CH03 và CH06. CFG cũng được nhắc ở CH05 (questions in context-free grammar), nên không ép dữ liệu về chỉ CH03 theo câu trả lời FAQ rút gọn.
- `resources.category_ids` có bằng chứng theo title/usage. Chưa gán tài liệu cho mọi chủ đề hay chương chỉ vì đó là sách NLP tổng quát; `resources.topic_ids` rỗng và `topic_links_complete=false`.
- LO có description và parent_id; liên kết LO→chapter/topic chưa được cung cấp rõ trong raw nên để rỗng, `links_complete=false`. Hội thoại mẫu gợi ý LO2.5→CH06 chưa được tự động nhập như một sự kiện raw.

## Thông tin thiếu và khác biệt nguồn

- Chỉ một assignment BTL01; bỏ bản ghi minh họa HW1. “bài tập 1” tiếp tục là alias BTL01.
- Deadline năm 2030 không có nguồn đã được bỏ, thay bằng null. Các mốc tuần 8/12/15 là mốc mẫu, không quy đổi thành ngày lịch.
- Kết quả hỏi deadline giờ là `missing_information`, không phải một ngày giả lập. Smoke fixtures được cập nhật; test renderer vẫn kiểm tra đường trả lời khi có deadline bằng dữ liệu test độc lập.
- Không đoán tên giảng viên, năm xuất bản hoặc tác giả còn thiếu; dùng null hoặc danh sách rỗng. Raw resources được giữ đúng nguyên văn, không sửa thông tin thư mục theo trí nhớ.
- Policy giữ nguyên description; `permission=null` vì chưa xây annotation cho phép/cấm theo từng hành động. Không tự suy ra “có” chỉ vì có record chính sách.
- Output bài tập mới bao gồm những đường dẫn thực sự liệt kê trong raw; `outputs_complete=false`, chưa giả định đây là danh sách nộp bài đầy đủ theo PDF.
- Nguồn ghi total_course_hours=150, nhưng lecture+assignment+self-study=135. Cả hai được giữ nguyên và báo `SOURCE_HOURS_MISMATCH`.

## Phạm vi thay đổi

Query builder hiện có registry cho các QTYPE nghiệp vụ và executor hỗ trợ eq/contains/contains_all/contains_any, xem queries.md. Các answer handler ngoài deadline vẫn cần phát triển. Thông tin hoặc liên kết còn thiếu trong KB không được suy đoán khi trả lời.
