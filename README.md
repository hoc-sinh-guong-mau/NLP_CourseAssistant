# Course Assistant — Classical NLP

Khung CO3085 dùng FCFG, NLTK FeatureChartParser và semantic theo feature. Hiện chỉ có query/answer handler cho `GET_DEADLINE / DEADLINE`; những câu khác có thể parse và trích xuất semantic nhưng trả trạng thái `unsupported_query`.

## Thành viên

Điền tên, MSSV và phân công của nhóm.

## Cài đặt và chạy

Chạy từ `NLP_Project`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m src.main grammar
python -m src.main batch
python -m src.main generate --limit 1000
python -m src.main chat
python -m src.evaluate
```

Không cần tải corpus NLTK. Chat in toàn bộ trace; `/exit` để thoát. Evaluation hiện chỉ là smoke check, chưa phải benchmark độc lập.

## Dữ liệu và cấu trúc

```text
data/
├── grammar/
│   └── syntax.fcfg
├── lexicon/
│   ├── course.yaml
│   ├── weeks.yaml
│   ├── topics.yaml
│   ├── assignments.yaml
│   └── question_patterns.yaml
├── KB/
│   ├── course.json
│   ├── schedule.json
│   └── assignments.json
└── raw/                    # Giữ dữ liệu gốc để đối chiếu nguồn
```

- `syntax.fcfg`: cấu trúc câu và feature unification; không lặp các alias đã đưa vào YAML. Một số từ chức năng vẫn nằm trực tiếp trong luật để dễ đọc.
- `course.yaml`: môn, kỳ thi, thành phần đánh giá và tên/nhóm tài liệu.
- `weeks.yaml`: tuần 1–15, có biến thể số viết bằng chữ và `week N`.
- `topics.yaml`: chủ đề, chương, phần nội dung môn học.
- `assignments.yaml`: tên bài tập lớn, phần và thành phần bài tập.
- `question_patterns.yaml`: mục từ để hỏi và các alias thuộc chính sách/chuẩn đầu ra. Các mẫu cú pháp hoàn chỉnh vẫn nằm ở syntax.
- `KB/*.json`: mỗi file là danh sách bản ghi có `id` duy nhất. Các tên thư mục có phân biệt hoa/thường trên Linux; phải dùng đúng `KB`.

`course.json` được trích từ các trường trong `raw/course_info.txt`; `schedule.json` được chuyển từ `raw/schedule.txt` và đánh dấu `is_sample: true` vì nguồn là kế hoạch mẫu, không phải lịch học chính thức. `assignments.json` vẫn chứa deadline **giả lập năm 2030**, có nguồn `SYNTHETIC_DEMO_ONLY`; thay bằng dữ liệu chính thức trước demo/đánh giá thực tế. Mã bài tập lớn được thống nhất là `BTL01`.

## Lexicon và entity normalization

Mỗi YAML có hai nhóm (có thể để danh sách rỗng):

```yaml
lexical_entries:
- category: WHEN
  aliases:
  - khi nào
entity_entries:
- category: WEEK
  entity_type: week
  canonical_id: WEEK_03
  aliases:
  - tuần 3
  - tuần ba
  - week 3
```

`category` là nhãn grammar theo miền, không phải POS phổ quát. Không cần gán noun/verb nếu grammar không dùng những thuộc tính đó.

`Lexicon.load(LEXICON_DIR)` đọc mọi file `.yaml`/`.yml` theo thứ tự tên, dùng `yaml.safe_load`, kiểm tra schema và trùng entry `(category, canonical_id)` giữa các file. Các alias được chuẩn hóa bằng cùng hàm normalization dùng cho câu hỏi. Một entity/category nên có một entry; thêm alias vào entry có sẵn.

Loader sinh các lexical productions:

```text
WEEK[ENTITY='WEEK_03'] -> 'tuần' 'ba'
WEEK[ENTITY='WEEK_03'] -> 'tuần' '3'
WEEK[ENTITY='WEEK_03'] -> 'week' '3'
```

Parser nhận token bề mặt và truyền ID bằng feature unification. Không thay câu hỏi bằng ID trước parsing. Khi thêm entity mới, thêm cả dữ liệu KB tương ứng nếu muốn truy vấn được; việc có alias trong lexicon không đảm bảo có câu trả lời trong KB.

`EntityResolver.lookup_alias(text, category=None)` trả danh sách tất cả ứng viên. `collisions()` liệt kê alias trùng trong cùng category; không coi alias trùng là lý do tự chọn ID đầu tiên. `get_entity(id)` trả các entry có ID đó, có thể thuộc nhiều category.

## Pipeline và module

```text
Câu gốc → normalize → tokenize
                     ↓
syntax.fcfg + YAML → FeatureGrammar → FeatureChartParser
                     ↓
Cây cú pháp → semantic → intent/entity → query → KB → answer
```

- `preprocessing/preprocessor.py`: API hàm `normalize(text)` và `tokenize(normalized_text)`; NFC, casefold, khoảng trắng, mã LO, chỉ bỏ dấu kết thúc `?!.`. Giữ dấu câu bên trong và token `lo2.5`, `llm/rag`, `context-free`. Tách theo tiếng/khoảng trắng, chưa phân đoạn từ tiếng Việt tổng quát.
- `lexical/lexicon_loader.py`: load/validate lexicon, tạo luật từ vựng.
- `lexical/entity_resolver.py`: tra alias và phát hiện collision.
- `parser.py`: `parse_all()` giữ các cây, `parse()` báo lỗi nếu có nhiều cây.
- `semantics.py`: đọc INTENT, ENTITY, QTYPE, TARGET từ gốc; tạo arguments có tên cụ thể cho deadline và nội dung tuần. Các loại khác giữ entity/target để phát triển handler sau.
- `pipeline.py`: các cây có cùng semantic được gộp; nhiều semantic khác nhau trả `ambiguous`. Không parse được trả `parse_failed`; chưa có handler trả `unsupported_query`; thiếu deadline trả `missing_information`.
- `knowledge_base.py`: đọc ba collection, kiểm tra ID và lọc theo query. Trường `select` hiện mô tả trường cần hỏi; chưa thực hiện projection.
- `generator.py`: sinh ứng viên từ CFG projection, rồi kiểm tra lại bằng feature parser; giới hạn độ sâu/số ứng viên và tối đa 10.000 câu đầu ra. Có thể trả ít hơn limit nếu hết ngân sách ứng viên.

## Đầu ra

`python -m src.main grammar` kiểm tra grammar và xuất riêng `output/grammar.txt` (bao gồm `% start S`, luật cấu trúc và luật từ vựng). Không cần khởi tạo KB hay chạy hỏi đáp. File xuất được kiểm thử đọc lại bằng `FeatureGrammar`, bảo toàn luật và khả năng parse. Tests ghi vào thư mục tạm; lệnh CLI mới tạo artifact trong output.

Loader cũng chặn khóa YAML trùng, trường schema không hợp lệ và token chứa ký tự không thể biểu diễn an toàn trong FCFG. Grammar được kiểm tra category tham chiếu có định nghĩa trước khi ghi. Đây là kiểm tra cấu trúc, chưa chứng minh mọi luật có thể sinh câu hoặc mọi feature đều hợp nhất được.

`batch` xuất `grammar.txt` chứa grammar hoàn chỉnh đã ghép YAML, cùng `parse-results.txt`, `semantic.txt`, `intent-entity.txt`, `query.txt`, `answer.txt`, `traces.jsonl`. Các dòng cùng thứ tự input không rỗng; parse thất bại là `()`.

`generate` xuất `samples.txt`; `evaluate` xuất `evaluation.txt`. Tập smoke hiện có ba câu nhỏ, chưa phản ánh độ chính xác tổng quát. Tests bao phủ normalization, tokenization, alias, collision, YAML không hợp lệ và đường truy vấn deadline.

## Phát triển tiếp

1. Kiểm tra dữ liệu chuẩn hóa theo nguồn chính thức và bỏ dữ liệu giả lập.
2. Thêm query/answer handler cho course info và week content; sau đó mở rộng các QTYPE còn lại.
3. Bổ sung câu hỏi tự viết độc lập, đánh giá intent/entity/semantic và câu trả lời; không chỉ đánh giá trên câu sinh từ grammar.
4. Nếu làm hội thoại, thêm trạng thái phiên và `output/dialogue.txt`.
5. Sau baseline mới thử TF-IDF + classifier để so sánh thống kê; FCFG viết tay không phải statistical parsing.
6. Hoàn thiện báo cáo, video, thành viên và nguồn tham khảo theo đề.

## Docker

```bash
docker build -t course-assistant .
docker run --rm -v "$PWD/output:/app/output" course-assistant
```

Mặc định chạy batch. Tạo thư mục `output` trước khi mount. Docker chưa được kiểm chứng trong lần chỉnh sửa này.

## Tham khảo

- Đặc tả bài tập NLPAssignment-Course Assistant.pdf do người dùng cung cấp.
- NLTK: https://www.nltk.org/ — FeatureGrammar và FeatureChartParser.
- PyYAML: https://pyyaml.org/ — đọc YAML bằng safe loader.
- Khung được xây dựng với hỗ trợ Codex; nhóm cần tự kiểm tra, hiểu thuật toán và ghi nhận nguồn hỗ trợ theo quy định môn học.
