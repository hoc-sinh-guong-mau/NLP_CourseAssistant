# Course Assistant — Bài tập lớn CO3085

Trợ lý tra cứu thông tin môn học bằng **Classical NLP**: FCFG, Chart Parser, semantic rules, nhận diện intent/entity theo luật, SQLite và câu trả lời theo mẫu. Có CLI theo từng mục của đề và giao diện hội thoại Streamlit.

## 1. Tác giả
    Trương Hiếu Quyền - MSSV: 2153756

## 2. Hướng dẫn cài đặt

### 2.1. Môi trường

- Python 3.11 trở lên; Dockerfile sử dụng Python 3.11.
- Metadata, dependency và entry point được khai báo tập trung trong [pyproject.toml](pyproject.toml): NLTK, PyYAML, Streamlit và python-dotenv. `requirements.txt` giữ làm lối cài đặt tương thích.
- SQLite dùng thư viện chuẩn `sqlite3` của Python, cần hỗ trợ JSON functions; không cần database server riêng.
- Không cần tải corpus NLTK, API key hoặc mô hình LLM.

Chạy tất cả lệnh trong README tại **thư mục project chứa README.md**:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Trên Windows PowerShell, thay lệnh activate bằng `.venv\Scripts\Activate.ps1`.

### 2.2. Chuẩn bị KB

```bash
python -m src.main build-kb
```

Lệnh đọc `data/raw/` và `models/lexicon/`, chuẩn hóa trong bộ nhớ rồi tạo `data/db/course_assistant_normalized.sqlite3`. Không cần KB JSON trung gian. Chạy lại khi thay đổi nguồn dữ liệu; database legacy `course_assistant.sqlite3` không được dùng hoặc ghi đè.

### 2.3. Cấu hình môi trường và đóng gói

[.env.example](.env.example) là mẫu cấu hình; `.env` dùng riêng trên máy và được loại khỏi Git/Docker build context. Thứ tự ưu tiên: **tham số CLI / RunConfig → biến môi trường tiến trình → .env → giá trị mặc định**. Cấu hình đọc một lần khi khởi động; cần khởi động lại sau khi sửa.

| Biến | Mặc định | Mục đích |
| --- | --- | --- |
| `COURSE_ENV_FILE` | `.env` tại thư mục đang chạy | Chọn tệp môi trường; tệp được chỉ định phải tồn tại |
| `COURSE_ROOT` | Root repository hoặc tài nguyên cài đặt | Gốc tài nguyên |
| `COURSE_DATA_DIR`, `COURSE_MODELS_DIR`, `COURSE_INPUT_DIR` | `data`, `models`, `input` dưới root | Thư mục dữ liệu, grammar/lexicon, đầu vào |
| `COURSE_RAW_DIR`, `COURSE_GRAMMAR_PATH`, `COURSE_LEXICON_DIR` | Theo data/models | Ghi đè từng nguồn |
| `COURSE_OUTPUT_DIR` | `output` | Nơi ghi đúng 9 artifact |
| `COURSE_DB_DIR`, `COURSE_DATABASE` | `data/db`, `data/db/course_assistant_normalized.sqlite3` | Thư mục và tệp SQLite; tệp cụ thể được ưu tiên |
| `COURSE_SAMPLE_LIMIT` | `100` | Số câu sinh mặc định, 1–10.000 |
| `COURSE_GENERATION_MAX_DEPTH` | `12` | Độ sâu sinh, 1–50 |
| `COURSE_GENERATION_CANDIDATE_FACTOR` | `20` | Hệ số giới hạn ứng viên, 1–100 |
| `COURSE_SQLITE_TIMEOUT` | `5` | Timeout SQLite, 0,1–300 giây |
| `COURSE_UI_MAX_TURNS` | `50` | Số lượt hiển thị, 1–1.000 |
| `COURSE_LOG_LEVEL` | `INFO` | Log CLI: DEBUG / INFO / WARNING / ERROR / CRITICAL |
| `STREAMLIT_SERVER_ADDRESS`, `STREAMLIT_SERVER_PORT` | Local: `127.0.0.1:8501`; Docker: `0.0.0.0:8501` | Địa chỉ phục vụ UI |

Đường dẫn nguồn tương đối được tính theo `COURSE_ROOT`. Đường dẫn DB/output tính theo root khi chạy source, theo thư mục đang chạy khi cài wheel để tránh ghi vào tài nguyên của môi trường Python. `.env` không nội suy `${...}`. Không đưa bí mật vào repository. Giá trị số/path rỗng không hợp lệ báo lỗi có stage `configuration` ngay khi khởi động.

Sau khi cài đặt, có thể dùng entry point thay cho `python -m src.main`:

```bash
course-assistant --help
course-assistant run
course-assistant test
course-assistant-ui
# Hoặc tái hiện workflow rồi mở UI:
course-assistant-workflow
```

`course-assistant-ui` chỉ mở UI; cần build KB trước. Launcher này nạp `.env` trước khi khởi động Streamlit. Có thể truyền thêm cờ như `course-assistant-ui --server.port=8502`.

Tạo wheel/source distribution để chuyển sang môi trường khác:

```bash
python -m build
python -m pip install dist/nlp_course_assistant-0.1.0-py3-none-any.whl
```

Wheel chứa code, grammar, lexicon, raw, input và tests dưới `share/nlp-course-assistant` của môi trường Python; không chứa `.env`, SQLite dựng sẵn hoặc output. Chạy tại thư mục có quyền ghi rồi dùng `course-assistant run`. Giữ cấu trúc `src/` hiện tại để tương thích các lệnh và import đã có. Cách khai báo tuân theo [hướng dẫn pyproject của PyPA](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/).

## 3. Hướng dẫn chạy chương trình

### 3.1. Chạy toàn bộ workflow

```bash
python -m src.main run
```

Tự build KB, chạy các bước đã triển khai của Phần I–IV và xuất đúng **9 file** ở `output/`. Mặc định sinh tối đa 100 câu. Chạy lại ghi đè những file tương ứng, không tự xóa file khác do người dùng tạo.

```bash
python -m src.main run --limit 1000 --input input/sentences.txt \
  --dialogue-input input/dialogues.txt --output-dir /tmp/nlp-output
```

### 3.2. CLI từng mục theo đề

| Mục | Lệnh sau `python -m src.main` | File được xuất trong output/ |
| --- | --- | --- |
| Chuẩn bị KB | `build-kb` | Không có; database nằm trong data/db/ |
| I — 3.1: Grammar | `grammar` | grammar.txt |
| I — 3.2: Sinh câu | `generate --limit 100` | samples.txt |
| I — 3.3: Parser | `parse` | parse-results.txt |
| II — 1: Semantic | `semantic` | semantic.txt |
| II — 2: Intent/entity | `intent-entity` | intent-entity.txt |
| II — 3: Query | `query` | query.txt |
| II — 4/5: Answer và thiếu thông tin | `answer` | answer.txt |
| Toàn bộ Phần II | `batch` | semantic.txt, intent-entity.txt, query.txt, answer.txt |
| III: Hội thoại cục bộ | `dialogue` | dialogue.txt |
| IV: Đánh giá | `evaluate` | evaluation.txt |
| Tái hiện toàn bộ | `run` | 9 file của đề |
| Kiểm thử code | `test` | Không có |
| Demo terminal | `chat` | Không có |

Ví dụ chạy lần lượt:

```bash
python -m src.main grammar
python -m src.main generate --limit 100
python -m src.main parse --input input/sentences.txt
python -m src.main build-kb
python -m src.main semantic
python -m src.main intent-entity
python -m src.main query
python -m src.main answer
python -m src.main dialogue --input input/dialogues.txt
python -m src.main evaluate
```

Mỗi lệnh Phần II tự chạy các bước cần thiết từ câu tự nhiên và dừng ở bước tương ứng; không đọc nối tiếp semantic.txt/query.txt từ lần chạy trước. Các lệnh riêng của Phần II, dialogue, evaluate và chat cần KB đã build; run/test tự build.

- Input câu độc lập: `input/sentences.txt`, mỗi dòng một câu. Không dùng cây trong parseTree.txt làm input CLI.
- Input hội thoại: `input/dialogues.txt`, mỗi dòng một câu hỏi; dòng trống ngăn cách các phiên độc lập. Không đưa nguyên file sample có header/U1/A1 vào định dạng này.
- `--input`: có ở parse, semantic, intent-entity, query, answer, batch, dialogue và run.
- `--limit`: có ở generate/run, nhận số nguyên 1–10.000.
- `--output-dir`: đổi nơi ghi output của lệnh; không đổi vị trí database.
- `--dialogue-input`: chọn tập hội thoại cho run.
- Evaluate vẫn đọc `input/test_cases.jsonl`; `--input` không đổi tập đánh giá.
- Không còn các lệnh part1/part2/part3/part4 hoặc lựa chọn backend.

Xem các tùy chọn thực tế:

```bash
python -m src.main --help
python -m src.main query --help
```

### 3.3. Streamlit UI

```bash
python -m src.main build-kb
course-assistant-ui
```

Mở http://localhost:8501. UI dùng `DialogueSession` riêng trong `st.session_state` của từng người dùng, giữ context qua các lần rerun. **Hội thoại mới** xóa lịch sử/context. Bật **Hiện phân tích pipeline** để xem parse tree, semantic, entity, query và context khi demo. Hiển thị số lượt theo `COURSE_UI_MAX_TURNS` (mặc định 50).

UI gọi trực tiếp pipeline, không tự ghi các file output. CLI chat cũng có context; dùng `/reset` để bắt đầu phiên mới và `/exit` để thoát.

### 3.4. Docker: workflow và UI

Cần Docker daemon/Desktop hoạt động:

```bash
docker build -t nlp-course-assistant .
mkdir -p output
docker run --rm -p 127.0.0.1:8501:8501 \
  -v "$PWD/output:/app/output" nlp-course-assistant
```

Lệnh mặc định của container chạy workflow để tái tạo 9 file, kiểm tra smoke evaluation rồi mở Streamlit. Mở http://localhost:8501; Ctrl+C để dừng. Nếu evaluation thất bại thì UI không khởi động. Dockerfile tạo venv tại `/opt/venv`, đưa `/opt/venv/bin` vào `PATH`, cài package trong venv, build KB từ raw và chạy bằng user `assistant` (UID 10001), không phụ thuộc .venv/database/output dựng sẵn trên host; có HTTP health check cho UI. Bind mount output cần cho UID này quyền ghi trên Linux; có thể dùng `--user "$(id -u):$(id -g)"` khi UID host khác.

Đưa cấu hình vào container bằng `--env-file` và ghi đè địa chỉ lắng nghe để truy cập qua port mapping:

```bash
docker run --rm --env-file .env -e STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
  -p 127.0.0.1:8501:8501 -v "$PWD/output:/app/output" nlp-course-assistant
```

Các path trong `.env` khi chạy Docker là path bên trong container. Nếu đổi `STREAMLIT_SERVER_PORT`, đổi cả cổng bên phải của `-p`. Không copy `.env` vào image.

Không cần `source activate` trong container: `python`, `pip`, CLI, Streamlit và health check đều chọn venv qua `PATH`. Venv được tạo trong image Linux, không copy `.venv` từ host.

Ghi đè command để chỉ chạy CLI hoặc test, không mở UI:

```bash
docker run --rm -v "$PWD/output:/app/output" nlp-course-assistant python -m src.main run
docker run --rm nlp-course-assistant python -m src.main test
docker run --rm -v "$PWD/output:/app/output" nlp-course-assistant python -m src.main answer
```

Nếu sửa input trên host sau khi build image:

```bash
docker run --rm -v "$PWD/input:/app/input:ro" -v "$PWD/output:/app/output" \
  nlp-course-assistant python -m src.main batch
```

## 4. Kiến trúc hệ thống

```text
Câu hỏi → Normalize/Tokenize → FCFG Parser → SemanticFrame
                                           ↓
                  Context Resolver (khi chạy DialogueSession)
                                           ↓
               Intent/Entity → QueryBuilder → SQLite → Answer Template
```

`CourseAssistant` xử lý một câu không lưu lịch sử. `DialogueSession` bọc pipeline và quản lý context. `AssignmentRunner` quản lý workflow/file I/O; CLI và Streamlit là hai lớp trình bày riêng. Các bước có thể được truyền component thay thế khi kiểm thử.

```text
project/
├── src/
│   ├── main.py                  # CLI arguments
│   ├── config.py                # Paths, RunConfig, limits, SQLite timeout
│   ├── application/             # Pipeline, workflow runner, messages
│   ├── preprocessing/           # Chuẩn hóa và tokenize
│   ├── lexical/                 # Lexicon, validation, alias resolver
│   ├── parsing/                 # Grammar loader, chart parser, generator
│   ├── semantic/                # Frame, schemas, feature reader, interpreter
│   ├── dialogue/                # Session state và typed reference resolver
│   ├── retrieval/               # Query registry, normalization, SQLite
│   ├── generation/              # Templates, domain handlers, formatting
│   ├── artifacts/               # Export đúng file yêu cầu
│   ├── evaluation/              # Đánh giá expected results
│   ├── ui/                      # Streamlit UI và container launcher
│   └── common/                  # Error protocol, file boundaries
├── data/raw/                    # Tài liệu nguồn
├── data/sample/                 # FAQ, truy vấn và hội thoại tham khảo
├── data/db/                     # SQLite sinh tự động và legacy DB
├── models/grammar/              # syntax.fcfg và rules/*.fcfg
├── models/lexicon/              # Từ vựng/entity aliases YAML
├── input/                       # sentences.txt, dialogues.txt, test_cases.jsonl
├── output/                      # Kết quả theo đề
├── tests/
├── .streamlit/config.toml
├── streamlit_app.py
├── pyproject.toml              # Metadata, dependencies, CLI/UI entry points
├── .env.example                # Mẫu cấu hình triển khai
├── LICENSE                     # MIT
├── requirements.txt
├── README.md
└── Dockerfile
```

Model dataclass và exception nằm trong module sở hữu. Ngoại lệ dùng chung `NLPError`, có stage/code/context và giữ original cause. Lỗi hệ thống không bị chuyển thành câu trả lời thành công; UI không hiện traceback nội bộ cho người dùng.

## 5. Grammar và sinh câu — Phần I / 3.1–3.2

Sử dụng **Feature-based Context-Free Grammar**. `syntax.fcfg` chứa start symbol và entry rules; `rules/*.fcfg` chia cấu trúc theo miền. Loader ghép các fragment theo thứ tự tên và sinh lexical productions từ YAML, kiểm tra cú pháp/category rồi xuất grammar.txt.

Ví dụ lexical productions:

```text
WEEK[ENTITY='WEEK_03'] -> 'tuần' '3'
WEEK[ENTITY='WEEK_03'] -> 'tuần' 'ba'
WEEK[ENTITY='WEEK_03'] -> 'week' '3'
```

Lexicon phân biệt mục từ với entity có canonical_id. Category WEEK/TOPIC là nhãn miền, không phải POS phổ quát. `bài tập 1`, `bài tập lớn`, `btl` cùng ánh xạ BTL01 theo quy ước project. Alias trùng giữa các entity giữ đủ ứng viên.

Sinh câu dùng CFG projection tạo ứng viên, sau đó parse lại bằng FCFG, loại trùng và giới hạn độ sâu/ngân sách. samples.txt có mỗi dòng một câu hợp lệ, tối đa 10.000; có thể ít hơn limit và không đảm bảo phân bố đều các intent.

## 6. Parser — Phần I / 3.3

Tiền xử lý dùng Unicode NFC, casefold, chuẩn hóa khoảng trắng và mã LO; tokenize theo tiếng/khoảng trắng để khớp terminal của grammar, giữ `lo2.5`, `llm/rag`, `context-free`. Chưa dùng bộ phân đoạn từ tiếng Việt tổng quát.

Parser sử dụng **NLTK FeatureChartParser**: lưu phân tích từng phần trong chart, kết hợp rule và feature unification để dựng cây từ S. Đây là sử dụng thuật toán thư viện, không phải tự cài chart parser từ đầu.

parse-results.txt có một dòng cho mỗi dòng input, kể cả dòng trống. Câu không thuộc grammar xuất `()`. Nếu có nhiều cây, file ghi cây đầu tiên làm đại diện; pipeline xét các semantic khác nhau trước khi trả lời, không coi cây đầu tiên là ý nghĩa chắc chắn đúng.

## 7. Semantic representation — Phần II / 1

`SemanticInterpreter` đọc INTENT/ENTITY/QTYPE/TARGET đã hợp nhất từ cây và áp dụng schema theo `(INTENT, QTYPE)`. Slot có thể lấy từ feature gốc, subtree hoặc danh sách feature khi phối hợp nhiều chủ đề.

Ví dụ trong semantic.txt:

```json
{"predicate":"GET_COURSE_INFO","qtype":"CREDITS","arguments":{"course_id":"CO3085"}}
```

Ví dụ quan hệ hai entity:

```json
{"predicate":"GET_TOPIC","qtype":"CHAPTER_HAS_TOPIC","arguments":{"chapter_id":"CH03","topic_id":"CFG"}}
```

Chưa có schema → unsupported_semantic; feature thiếu/chưa hợp nhất → invalid_semantic. Nhiều cây cùng semantic được gộp; nhiều semantic khác nhau trả ambiguous. Không diễn giải được thì output tương ứng là null.

## 8. Nhận diện intent/entity — Phần II / 2

Nhận diện dựa trên **luật và feature unification**. `intent_entity.extract()` chuẩn hóa SemanticFrame sang hợp đồng dưới đây, deep-copy slot danh sách để không chia sẻ mutable state:

```json
{"intent":"GET_COURSE_INFO","qtype":"CREDITS","entities":{"course_id":"CO3085"}}
```

Các intent nghiệp vụ: GET_COURSE_INFO, GET_SCHEDULE, GET_TOPIC, GET_ASSIGNMENT, GET_DEADLINE, GET_RESOURCE, GET_RULE, GET_INSTRUCTOR, GET_LO. QTYPE phân biệt loại thông tin trong cùng intent.

UNKNOWN chưa được xuất như một nhãn riêng: câu không nhận diện được có intent/entity null và trạng thái parse_failed. Parse thất bại không đủ để khẳng định câu ngoài miền; có thể thiếu mẫu grammar hoặc lỗi gõ.

### Hội thoại cục bộ — Phần III

Resolver chuyển CONTEXT_DEPENDENT thành semantic nghiệp vụ bằng context đúng loại: phần này, chương này/nó, chương sau, môn này. Ví dụ BTL01 → course_id=CO3085 giúp chuyển từ câu hỏi BTL sang “Môn này có bao nhiêu chương?”.

State lưu ID theo loại/focus/source_turn, lấy quan hệ cha từ KB và không trích entity từ chuỗi answer. Chỉ dùng context cục bộ của phiên, không chia sẻ giữa người dùng. Nhiều ứng viên hoặc thiếu context yêu cầu làm rõ; lượt lỗi không ghi đè state.

`dialogue.txt` thể hiện INPUT, CONTEXT_BEFORE/USED/AFTER, RAW_SEMANTIC, RESOLVED_SEMANTIC, QUERY, ANSWER và STATUS. Mỗi nhóm câu trong input/dialogues.txt được reset thành phiên riêng.

## 9. Knowledge Base và truy vấn — Phần II / 3–5

### 9.1. Nguồn và chuẩn hóa

Nguồn raw gồm thông tin môn, lịch, chủ đề, bài tập, tài liệu và quy định. Bộ sample phục vụ tham khảo/evaluation, không dùng bảng FAQ để thay thế pipeline hoặc nhập đáp án hội thoại mẫu thành sự kiện.

Raw + lexicon được chuẩn hóa trong bộ nhớ thành 14 collection/118 record. Kiểm tra ID, provenance và liên kết trước khi ghi SQLite. Record giữ source, source_section, is_sample. Deadline chưa có ngày cụ thể; giảng viên chưa có dữ liệu. Link chapter/topic và LO/resource còn partial; không tự bịa liên kết để khớp sample.

### 9.2. SQLite

Database nhúng, không cần server/container database riêng. Schema hiện tại:

| Bảng | Nội dung |
| --- | --- |
| kb_metadata | Phiên bản schema |
| kb_collections | Catalog, kể cả collection rỗng |
| kb_records | collection, entity_id, position, document |

Document là cột JSON có cấu trúc trong SQLite; **chưa phải 14 bảng quan hệ nghiệp vụ**. Khóa chính `(collection, entity_id)` và position giữ thứ tự nguồn. Runtime dùng kết nối read-only; importer tạo DB tạm, commit rồi atomic replace, không ghi đè database legacy.

### 9.3. Query và answer

QueryBuilder ánh xạ semantic bằng registry cho 61 QTYPE nghiệp vụ. Ví dụ query.txt:

```json
{"collection":"course","filters":{"id":"CO3085"},"select":["credits"]}
```

SQL compiler dùng placeholder cho giá trị/JSON paths; chỉ cho phép equality và contains/contains_all/contains_any đã định nghĩa. `select` giới hạn trường trả về, giữ ID/nguồn/tên hiển thị. Bộ lọc thực thi bằng SQL/json_each, không tải toàn bộ KB rồi lọc bằng Python.

AnswerGenerator dùng field templates và handler theo miền, không đọc lại câu hỏi để đoán đáp án. Câu trả lời có nguồn; record mô phỏng có nhãn “Theo dữ liệu mẫu”. Thiếu dữ liệu trả missing_information. Không suy ra “không” chỉ vì quan hệ chưa có, hoặc “được phép” chỉ vì có record policy.

query.txt vẫn là logical query có cấu trúc, không phải file SQL thực thi. SQL có thể kiểm tra qua API `kb.compile(query)`; CLI không xuất file SQL/trace phụ.

## 10. Lựa chọn phương pháp NLP

Project chọn **Classical NLP** trong lựa chọn Classical/Statistical NLP của đề:

- CFG/FCFG và Chart Parser.
- Semantic interpretation và intent/entity theo luật.
- Chuẩn hóa entity qua lexicon, truy vấn KB có cấu trúc.
- Context resolution theo một tập quy tắc và answer template.

Chưa có mô hình thống kê, classifier ML, Deep Learning, LLM hoặc RAG. Không coi việc dùng NLTK/SQLite là học máy thống kê. TF-IDF + classifier/fallback có thể là hướng mở rộng, nhưng chưa có trong pipeline hiện tại.

## 11. Đánh giá và kiểm thử — Phần IV

### 11.1. Đánh giá theo tập expected

```bash
python -m src.main build-kb
python -m src.main evaluate
```

Đọc input/test_cases.jsonl, so sánh chính xác các trường expected và xuất evaluation.txt. Hiện có **3 smoke cases**, không phải benchmark độc lập hoặc accuracy trên toàn bộ input/sample.

Thêm dòng JSON để mở rộng tập đánh giá:

```json
{"input":"Môn NLP có mấy tín chỉ?","expected":{"status":"ok","intent_entity":{"intent":"GET_COURSE_INFO","qtype":"CREDITS","entities":{"course_id":"CO3085"}}}}
```

Báo cáo cuối kỳ còn cần test độc lập bao phủ intent/QTYPE, paraphrase, ngoài miền, thiếu dữ liệu và hội thoại; báo số đúng, accuracy/F1, lỗi và nguyên nhân.

### 11.2. Unit/integration tests

```bash
python -m src.main test
```

Tự build KB và chạy toàn bộ tests. Kết quả OK nghĩa là test đạt; FAIL/ERROR kèm tên test/traceback. Exit code khác 0 khi thất bại. Tests dùng thư mục tạm, không xuất file nộp bài vào output/.

Chạy unittest trực tiếp hoặc test riêng:

```bash
python -m src.main build-kb
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p "test_grammar.py" -v
python -m unittest discover -s tests -p "test_semantics.py" -v
python -m unittest discover -s tests -p "test_queries.py" -v
python -m unittest discover -s tests -p "test_answers.py" -v
python -m unittest discover -s tests -p "test_dialogue.py" -v
python -m unittest discover -s tests -p "test_ui.py" -v
```

Có thể dùng cùng mẫu `-p "<tên_file>"` với test_normalizer.py, test_tokenizer.py, test_lexicon.py, test_parser.py, test_intent_entity.py, test_kb_normalization.py, test_sqlite.py, test_errors.py, test_extensibility.py và test_workflows.py.

Tests bao phủ dữ liệu/đường lỗi, registry, output alignment, session isolation và SQLite injection/read-only/atomic import. Streamlit dùng AppTest để kiểm tra chat/rerun/reset/lỗi; không cần mở server riêng. Bộ test đã được chạy cả local và Docker, nhưng không thay thế đánh giá chất lượng NLP độc lập.

## 12. Hạn chế của hệ thống

- Độ bao phủ phụ thuộc grammar/alias; chưa có sửa lỗi gõ hoặc ML fallback.
- Context chỉ hỗ trợ những mẫu định trước, không phải coreference/dialogue manager tổng quát.
- Liên kết tài liệu–chương, LO–chương và một số quan hệ topic chưa đầy đủ; có thể resolution thành công nhưng answer vẫn thiếu thông tin.
- Không có deadline chính thức hoặc tên giảng viên trong nguồn; không suy đoán.
- Lịch/mốc BTL/quy định là dữ liệu mẫu, không thay thế thông tin hành chính chính thức.
- Nguồn ghi tổng giờ 150 nhưng các thành phần cộng 135; giữ nguyên thay vì tự sửa.
- SQLite document/JSON phù hợp miền nhỏ; chưa có schema quan hệ riêng, join nghiệp vụ hoặc tối ưu dựa trên benchmark lớn.
- Evaluation mặc định còn nhỏ; số câu có status ok hoặc câu sinh từ grammar không phải accuracy tổng quát.
- UI giữ phiên trong bộ nhớ, không có đăng nhập hoặc lưu lịch sử bền vững.

## 13. File đầu ra và nộp bài

```text
output/
├── grammar.txt
├── samples.txt
├── parse-results.txt
├── semantic.txt
├── intent-entity.txt
├── query.txt
├── answer.txt
├── dialogue.txt
└── evaluation.txt
```

Mỗi output câu độc lập có một dòng cho mỗi dòng input, kể cả dòng trống. Dữ liệu không diễn giải được là null; parse không hợp lệ là `()`. Dialogue/evaluation dùng định dạng báo cáo riêng. Không tự xuất kb-normalization.json, traces.jsonl, parse-traces.jsonl hoặc sql-query.txt.

Trước khi nộp: điền thành viên, chạy run/test, kiểm tra output, hoàn thiện báo cáo/video demo và đóng gói src/data/models/input/output/README.md/Dockerfile theo đề. Giữ requirements.txt và entry point/config UI nếu nộp giao diện; tests hỗ trợ tái hiện và kiểm chứng. Không cần nộp .venv hoặc Docker image.

## 14. Tài liệu và ghi nhận

- Code theo module: [Pipeline](src/application/pipeline.py), [Query](src/retrieval/query_builder.py), [SQLite](src/retrieval/sqlite/storage.py), [Dialogue](src/dialogue/session.py), [UI](src/ui/app.py).
- Nguồn dữ liệu: đặc tả bài tập và bộ raw/sample được cung cấp.
- Thư viện: [NLTK](https://www.nltk.org/), [PyYAML](https://pyyaml.org/), [Streamlit](https://docs.streamlit.io/).

Có hỗ trợ Codex trong phát triển; nhóm cần kiểm chứng, hiểu và giải thích thuật toán/code, ghi nhận nguồn và sự hỗ trợ theo quy định môn học.

Mã nguồn phát hành theo [MIT License](LICENSE). Giấy phép này không thay thế quyền sử dụng tài liệu môn học, dữ liệu nguồn hoặc giấy phép riêng của dependency.
