# Course Assistant — Bài tập lớn CO3085

Trợ lý hỏi đáp tiếng Việt trong miền thông tin môn học **Xử lý Ngôn ngữ Tự nhiên**. Hệ thống kết hợp **Classical NLP** (Feature-based CFG, Chart Parser, semantic rules) với **Statistical NLP** (TF-IDF + Logistic Regression làm fallback), truy vấn SQLite và sinh câu trả lời theo mẫu. Chương trình có CLI và giao diện hội thoại Streamlit.

## 1. Thành viên nhóm

| Họ và tên | MSSV |
| --- | --- |
| Trương Hiếu Quyền | 2153756 |

Bổ sung các thành viên còn lại và phân công công việc theo thông tin thực tế của nhóm trước khi nộp bài.

## 2. Hướng dẫn cài đặt

### 2.1. Yêu cầu môi trường

- Python **3.11 trở lên**; Dockerfile dùng Python 3.11.
- Dependency khai báo trong [pyproject.toml](pyproject.toml): NLTK, PyYAML, Streamlit, python-dotenv, scikit-learn, joblib và matplotlib.
- SQLite dùng thư viện chuẩn `sqlite3`, cần hỗ trợ JSON functions; không cần cài database server.
- Không cần API key, mô hình LLM hoặc tải corpus NLTK.

Thực hiện các lệnh từ **thư mục project chứa README.md và pyproject.toml**. Dùng `python -m src.main` để chạy CLI theo package.

### 2.2. Cài đặt trên máy

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Trên Windows PowerShell, dùng `python -m venv .venv` và `.venv\Scripts\Activate.ps1`. Có thể thay bước cài dependency bằng `python -m pip install -r requirements.txt`; file này trỏ về project để giữ một nguồn khai báo dependency.

Ở lần cài mới, tạo cấu hình local từ mẫu:

```bash
cp .env.example .env
```

PowerShell dùng `Copy-Item .env.example .env`. Nếu đã có `.env`, tiếp tục sử dụng cấu hình hiện có.

### 2.3. Cấu hình môi trường

[.env.example](.env.example) liệt kê các biến được hỗ trợ. `.env` được loại khỏi Git và Docker build context. Thứ tự ưu tiên là **tham số CLI/RunConfig → biến môi trường tiến trình → .env → mặc định**. Cấu hình đọc khi khởi động; cần khởi động lại sau khi sửa.

| Biến | Mặc định / tác dụng |
| --- | --- |
| `COURSE_ENV_FILE` | `.env` tại thư mục đang chạy; đường dẫn chỉ định phải tồn tại |
| `COURSE_ROOT` | Gốc repository hoặc tài nguyên của package đã cài |
| `COURSE_DATA_DIR`, `COURSE_MODELS_DIR`, `COURSE_INPUT_DIR` | Thư mục data, model/config và input |
| `COURSE_RAW_DIR`, `COURSE_GRAMMAR_PATH`, `COURSE_LEXICON_DIR` | Ghi đè đường dẫn từng nguồn |
| `COURSE_DATABASE`, `COURSE_DB_DIR` | Tệp SQLite và thư mục DB; tệp cụ thể được ưu tiên |
| `COURSE_OUTPUT_DIR` | `output` |
| `COURSE_QTYPE_MODEL` | `models/statistical/qtype.joblib` |
| `COURSE_SAMPLE_LIMIT` | `100`; giới hạn CLI từ 1 đến 10.000 |
| `COURSE_GENERATION_MAX_DEPTH`, `COURSE_GENERATION_CANDIDATE_FACTOR` | `12`, `20`; giới hạn sinh ứng viên |
| `COURSE_SQLITE_TIMEOUT` | `5` giây |
| `COURSE_UI_MAX_TURNS` | Hiển thị tối đa `50` lượt gần nhất |
| `COURSE_LOG_LEVEL` | Log CLI: `INFO`; hỗ trợ DEBUG/INFO/WARNING/ERROR/CRITICAL |
| `STREAMLIT_SERVER_ADDRESS`, `STREAMLIT_SERVER_PORT` | Local: `127.0.0.1:8501`; Docker: `0.0.0.0:8501` |

Đường dẫn nguồn tương đối tính theo `COURSE_ROOT`. DB/output tính theo root khi chạy source, theo thư mục đang chạy khi dùng wheel để tránh ghi vào tài nguyên package. `.env` không nội suy `${...}`. Các giá trị không hợp lệ báo lỗi tại stage `configuration`.

### 2.4. Khởi tạo Knowledge Base

```bash
python -m src.main build-kb
```

Lệnh chuẩn hóa raw và lexicon trong bộ nhớ, kiểm tra dữ liệu rồi tạo `data/db/course_assistant_normalized.sqlite3`. Chạy lại khi sửa nguồn dữ liệu. Database legacy `course_assistant.sqlite3` không được dùng trong pipeline hiện tại.

## 3. Hướng dẫn chạy chương trình

### 3.1. Tái hiện toàn bộ workflow

```bash
python -m src.main run
```

Lệnh tự build KB, chạy các phần đã hiện thực của đề và xuất **9 file**. Mặc định sinh tối đa 100 câu và dùng 3 smoke case để đánh giá hồi quy. Có thể đổi input, số câu sinh và thư mục output:

```bash
python -m src.main run --limit 1000 --input input/sentences.txt \
  --dialogue-input input/dialogues.txt --output-dir /tmp/nlp-output
```

### 3.2. CLI theo từng phần của đề

Các lệnh dưới đây chạy sau `python -m src.main`. Sau khi cài project, có thể dùng `course-assistant` thay cho `python -m src.main`.

| Phần / chức năng | Lệnh | File được xuất trong output/ |
| --- | --- | --- |
| Chuẩn bị DB | `build-kb` | Không có; tạo SQLite trong data/db/ |
| I — 3.1: Grammar | `grammar` | grammar.txt |
| I — 3.2: Sinh câu | `generate --limit 100` | samples.txt |
| I — 3.3: Parsing | `parse` | parse-results.txt |
| II — Semantic | `semantic` | semantic.txt |
| II — Intent/entity | `intent-entity` | intent-entity.txt |
| II — Truy vấn KB | `query` | query.txt |
| II — Sinh câu trả lời | `answer` | answer.txt |
| Toàn bộ Phần II | `batch` | semantic.txt, intent-entity.txt, query.txt, answer.txt |
| III — Ngữ cảnh hội thoại | `dialogue` | dialogue.txt |
| IV — Smoke evaluation | `evaluate` | evaluation.txt |
| IV — Benchmark 125 câu | `evaluate --input input/test_cases.jsonl` | evaluation.txt |
| Toàn bộ workflow | `run` | Đủ 9 file của đề |
| Unit/integration tests | `test` | Không tạo artifact nộp bài |
| Hội thoại terminal | `chat` | Không tạo artifact nộp bài |

`grammar`, `generate`, `parse` chạy được độc lập với KB. Trước khi chạy các lệnh Phần II, `dialogue`, `evaluate`, `chat` hoặc UI, cần `build-kb`; `run` và `test` tự thực hiện bước này.

- `input/sentences.txt`: mỗi dòng một câu độc lập, kể cả dòng trống để giữ vị trí output.
- `input/dialogues.txt`: mỗi dòng một câu hỏi; dòng trống ngăn cách các phiên hội thoại. Không đưa nguyên định dạng U1/A1 của bộ sample vào file này.
- `--input`: có ở parse, các lệnh Phần II, dialogue, evaluate và run. Với evaluate, input phải là JSONL gán nhãn.
- `--dialogue-input`: chọn file hội thoại cho run. `--limit`: áp dụng cho generate/run.
- `--output-dir`: đổi thư mục ghi artifact, không đổi vị trí DB. Mỗi lần chạy ghi đè các file tương ứng.
- Các bước Phần II xử lý lại từ câu tự nhiên; không đọc nối tiếp semantic.txt/query.txt từ lần chạy trước.

```bash
python -m src.main --help
python -m src.main evaluate --help
```

### 3.3. Giao diện Streamlit

```bash
python -m src.main build-kb
course-assistant-ui
```

Mở **http://localhost:8501**. Giao diện dùng `DialogueSession` riêng cho từng phiên trong `st.session_state`. Nút **Hội thoại mới** xóa lịch sử và context. Bật **Hiện phân tích pipeline** để xem parse tree, semantic, intent/entity, dự đoán thống kê, context và query.

`course-assistant-ui` nạp `.env` trước khi khởi động Streamlit và không tự xuất artifact. Có thể đổi cổng bằng `course-assistant-ui --server.port=8502`. Lệnh `course-assistant-workflow` chạy workflow trước rồi mở UI. Trong CLI `chat`, dùng `/reset` để bắt đầu phiên mới và `/exit` để thoát.

### 3.4. Docker

Cần Docker daemon/Desktop hoạt động:

```bash
docker build -t nlp-course-assistant .
mkdir -p output
docker run --rm -p 127.0.0.1:8501:8501 \
  -v "$PWD/output:/app/output" nlp-course-assistant
```

Container mặc định tạo 9 output, kiểm tra smoke **3/3**, rồi mở Streamlit. Smoke thất bại sẽ dừng khởi động. Benchmark 125 câu được chạy riêng nên các câu chưa hỗ trợ không chặn UI.

Docker tạo Python venv tại `/opt/venv`, thêm vào `PATH`, cài package và chạy bằng user `assistant` (UID 10001). Python, CLI, pip, Streamlit và health check đều dùng venv; không cần `source activate`. Image tự build KB từ raw, không copy `.venv`, `.env` hoặc SQLite dựng sẵn trên host.

Chạy riêng CLI hoặc test trong container:

```bash
docker run --rm -v "$PWD/output:/app/output" nlp-course-assistant course-assistant run
docker run --rm nlp-course-assistant course-assistant test
docker run --rm -v "$PWD/output:/app/output" nlp-course-assistant \
  course-assistant evaluate --input input/test_cases.jsonl
```

Dùng cấu hình local với container:

```bash
docker run --rm --env-file .env -e STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
  -p 127.0.0.1:8501:8501 -v "$PWD/output:/app/output" nlp-course-assistant
```

Path trong `.env` phải phù hợp filesystem của container. Đổi port phải đổi cả cổng bên phải của `-p`. Trên Linux, thư mục output bind mount cần cho UID 10001 quyền ghi; có thể dùng named volume như `-v nlp-output:/app/output` để lưu kết quả trong Docker. Có thể mount input bằng `-v "$PWD/input:/app/input:ro"`. SQLite nhúng trong ứng dụng, không có container DB riêng.

### 3.5. Các file đầu ra theo đề

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

Các output câu độc lập giữ một dòng cho mỗi dòng input; câu không có cây ghi `()`, dữ liệu không diễn giải được ghi `null` ở các file JSON tương ứng. Dialogue và evaluation dùng báo cáo riêng. Huấn luyện model là tác vụ riêng, có artifact khác được mô tả tại mục 10.

## 4. Kiến trúc hệ thống

```text
Câu hỏi → Normalize / Tokenize → FCFG Parser
                                 ├─ Có cây → Semantic Rules
                                 └─ Không có cây → Statistical Fallback + Entity Extractor
                                                      ↓
                                                SemanticFrame
                                                      ↓
                                Context Resolver (nếu dùng DialogueSession)
                                                      ↓
                          Intent/Entity → QueryBuilder → SQLite → Answer Template
```

[CourseAssistant](src/application/pipeline.py) điều phối một câu hỏi. [AssignmentRunner](src/application/runner.py) quản lý workflow và file I/O. CLI và Streamlit gọi cùng pipeline. Các component có thể được truyền vào constructor để kiểm thử.

```text
project/
├── src/
│   ├── application/             # Pipeline, workflow, thông báo trạng thái
│   ├── preprocessing/           # Chuẩn hóa và tokenize
│   ├── lexical/                 # Đọc/kiểm tra lexicon, alias resolver
│   ├── parsing/                 # Nạp grammar, chart parser, sinh câu
│   ├── semantic/                # SemanticFrame, schema, interpreter, intent/entity
│   ├── statistical_processing/  # Dataset, TF-IDF/LR, entity extraction, training
│   ├── retrieval/               # Query contract, chuẩn hóa KB, SQLite
│   ├── generation/              # Template, handler nghiệp vụ, định dạng
│   ├── dialogue/                # Session, context và reference resolver
│   ├── evaluation/              # Task và abstention metrics
│   ├── artifacts/               # Xuất artifact theo đề
│   ├── ui/                      # Streamlit và launcher
│   ├── common/                  # Error protocol và file I/O
│   ├── config.py
│   └── main.py
├── data/                        # raw/, sample/, db/, stat_dataset/
├── models/                      # grammar/, lexicon/, statistical/
├── input/                       # Câu hỏi, hội thoại, smoke và benchmark
├── output/                      # Kết quả chạy theo đề
├── tests/
├── .streamlit/config.toml
├── .env.example
├── pyproject.toml
├── requirements.txt
├── streamlit_app.py
├── README.md
├── LICENSE
└── Dockerfile
```

### Ngữ cảnh hội thoại cục bộ — Phần III

[DialogueSession](src/dialogue/session.py) bọc pipeline, lưu entity theo loại, focus và source_turn. Resolver dùng ID và quan hệ trong KB để diễn giải “phần này”, “chương này”, “chương sau”, “môn này”; không trích entity từ chuỗi answer. Mỗi phiên có state riêng; thiếu hoặc có nhiều ứng viên sẽ yêu cầu làm rõ. Các lượt lỗi không ghi đè state.

Ví dụ: hỏi phần parser của BTL → ghi nhớ PART_I/BTL01 → “Phần này cần xuất file gì?” được diễn giải thành PART_OUTPUTS. Quan hệ BTL01 → CO3085 hỗ trợ đổi chủ đề sang “Môn này có bao nhiêu chương?”. Câu đã nêu topic cụ thể như “CFG có tài liệu nào?” đi thẳng tới truy vấn topic.

`dialogue.txt` ghi input, context trước/được dùng/sau lượt, raw/resolved semantic, query, answer và status. Dataclass và exception nằm trong module sở hữu; lỗi dùng chung `NLPError` với stage/code/context và giữ nguyên nguyên nhân lỗi.

## 5. Mô tả grammar

Grammar là **Feature-based Context-Free Grammar (FCFG)**:

- [models/grammar/syntax.fcfg](models/grammar/syntax.fcfg): khai báo start symbol S và entry rules cho từng nhóm truy vấn.
- `models/grammar/rules/*.fcfg`: cấu trúc câu theo miền, như course, schedule, topics, assignments, resources và context.
- `models/lexicon/*.yaml`: lexical entry, canonical ID và các alias; tách khỏi cấu trúc câu để dễ thêm từ vựng.

[Grammar loader](src/parsing/grammar_loader.py) ghép fragment theo thứ tự tên, thêm lexical productions sinh từ YAML và kiểm tra cú pháp/category. Ví dụ:

```text
WEEK[ENTITY='WEEK_03'] -> 'tuần' '3'
WEEK[ENTITY='WEEK_03'] -> 'tuần' 'ba'
WEEK[ENTITY='WEEK_03'] -> 'week' '3'
```

INTENT, QTYPE, ENTITY, TARGET được truyền bằng feature unification. WEEK/TOPIC là category theo miền, không phải POS phổ quát. Alias trùng giữa các entity giữ đủ ứng viên; “bài tập 1”, “bài tập lớn”, “btl” cùng chỉ BTL01 theo quy ước project.

Sinh câu dùng CFG projection tạo ứng viên, sau đó parse lại bằng FCFG để kiểm tra feature, loại trùng và giới hạn độ sâu/ngân sách. `samples.txt` có thể ít câu hơn limit; thứ tự sinh không bảo đảm cân bằng intent.

## 6. Mô tả parser

[Parser](src/parsing/parser.py) dùng **NLTK FeatureChartParser**. Chart lưu kết quả phân tích từng phần, kết hợp các production và feature unification để dựng cây từ S. Project sử dụng thuật toán của NLTK, không tự hiện thực Chart Parser từ đầu.

Tiền xử lý gồm Unicode NFC, casefold, chuẩn hóa khoảng trắng, dấu câu và mã LO. Tokenization tách theo tiếng/khoảng trắng để khớp terminal của grammar, giữ các token đặc biệt như `lo2.5`, `llm/rag`, `context-free`.

`parse_all()` trả tất cả cây hoặc danh sách rỗng nếu không có phân tích hoàn chỉnh. `parse-results.txt` ghi cây đầu tiên làm đại diện; pipeline xét các semantic khác nhau từ toàn bộ cây. Nhiều cây có cùng semantic được gộp, nhiều semantic khác nhau trả `ambiguous`. Statistical fallback chỉ được thử khi không có cây; nó không giải quyết nhập nhằng giữa các cây.

## 7. Mô tả semantic representation

[SemanticInterpreter](src/semantic/interpreter.py) đọc feature đã hợp nhất và áp dụng schema trong [semantic/rules.py](src/semantic/rules.py). Kết quả là [SemanticFrame](src/semantic/models.py) gồm:

| Trường | Ý nghĩa |
| --- | --- |
| `predicate` | Intent nghiệp vụ |
| `qtype` | Loại thông tin cần hỏi trong intent |
| `arguments` | Slot và canonical ID để truy vấn KB |

```json
{"predicate":"GET_COURSE_INFO","qtype":"CREDITS","arguments":{"course_id":"CO3085"}}
```

Một truy vấn quan hệ:

```json
{"predicate":"GET_TOPIC","qtype":"CHAPTER_HAS_TOPIC","arguments":{"chapter_id":"CH03","topic_id":"CFG"}}
```

Slot có thể lấy từ feature gốc, subtree hoặc nhiều feature để tạo danh sách topic. Semantic chưa có schema trả `unsupported_semantic`; feature thiếu/chưa hợp nhất trả `invalid_semantic`. Context-dependent frame được resolver chuyển thành frame nghiệp vụ trước khi truy vấn. File `semantic.txt` ghi biểu diễn JSON, không phải câu trả lời tự nhiên.

## 8. Phương pháp xử lý intent/entity

### 8.1. Luật và feature unification

Khi có cây, semantic rules xác định intent/qtype và lấy entity từ các feature. [intent_entity.extract()](src/semantic/intent_entity.py) chuyển frame sang hợp đồng:

```json
{"intent":"GET_COURSE_INFO","qtype":"CREDITS","entities":{"course_id":"CO3085"}}
```

| Intent | Nhóm thông tin |
| --- | --- |
| GET_COURSE_INFO | Thông tin môn, đánh giá, hình thức thi |
| GET_SCHEDULE | Lịch học theo tuần/chương/chủ đề |
| GET_TOPIC | Nội dung chương và quan hệ chủ đề |
| GET_ASSIGNMENT | Yêu cầu, thành phần và đầu ra BTL |
| GET_DEADLINE | Hạn nộp |
| GET_RESOURCE | Tài liệu và thông tin xuất bản |
| GET_RULE | Quy định và quyền sử dụng |
| GET_INSTRUCTOR | Giảng viên |
| GET_LO | Chuẩn đầu ra |

### 8.2. Statistical fallback

Khi parser không có cây, [QTypeRecognizer](src/statistical_processing/intent_recognizer.py) dùng TF-IDF và Logistic Regression dự đoán qtype. Pipeline ánh xạ qtype sang intent theo semantic registry, rồi [EntityExtractor](src/statistical_processing/entity_extractor.py) tìm alias trong lexicon để điền slot bắt buộc/tùy chọn. Chỉ khi đủ thông tin mới tạo SemanticFrame và tiếp tục truy vấn.

Model tự tải từ `COURSE_QTYPE_MODEL`, mặc định `models/statistical/qtype.joblib`. Nếu không có model ở đường dẫn mặc định thì fallback không hoạt động; đường dẫn tường minh bị thiếu báo lỗi cấu hình. Có thể xem `statistical_prediction` và `statistical_used` trong phân tích UI. Có dự đoán nhưng `statistical_used=false` nghĩa là dự đoán chưa được chấp nhận thành semantic.

UNKNOWN là kết quả nội bộ khi confidence dưới ngưỡng, không phải nhãn được huấn luyện hoặc intent nghiệp vụ được xuất riêng. Fallback không chấp nhận được thì pipeline giữ `parse_failed` và intent/entity null. Parse thất bại cũng có thể do thiếu grammar/alias; không đủ để kết luận câu ngoài miền.

## 9. Knowledge Base và cách truy vấn

### 9.1. Dữ liệu và lưu trữ

`data/raw/` chứa thông tin môn, lịch, chủ đề, bài tập, tài liệu và quy định. `data/sample/` là FAQ/câu hỏi/hội thoại tham khảo; không nhập đáp án mẫu thành sự kiện KB. Raw và lexicon được chuẩn hóa trong bộ nhớ, kiểm tra ID, liên kết và provenance trước khi ghi SQLite. Bộ nguồn hiện tại tạo **14 collection / 118 record**; mỗi record giữ source, source_section và is_sample.

SQLite nhúng dùng ba bảng:

| Bảng | Nội dung |
| --- | --- |
| `kb_metadata` | Phiên bản schema |
| `kb_collections` | Catalog các collection |
| `kb_records` | Collection, entity ID, thứ tự và document JSON |

Đây là lưu document JSON trong SQLite, không phải 14 bảng quan hệ riêng. Build ghi snapshot tạm rồi thay thế; query mở read-only. Liên kết chưa có dữ liệu không tự được bổ sung bằng suy đoán.

### 9.2. Từ semantic tới query

[QueryBuilder](src/retrieval/query_builder.py) áp dụng registry theo `(intent, qtype)`, kiểm tra slot rồi sinh query logic được phép. Ví dụ với CREDITS:

```json
{"collection":"course","filters":{"id":"CO3085"},"select":["credits"]}
```

[SQLite compiler](src/retrieval/sqlite/compiler.py) chuyển query thành SQL tham số hóa; tên collection, field và operator được kiểm tra theo contract. Có equality filters và các điều kiện membership như contains/contains_all. `query.txt` ghi query logic JSON; không ghi SQL debug thành file nộp bài riêng.

### 9.3. Sinh câu trả lời và thiếu dữ liệu

[AnswerGenerator](src/generation/answer.py) dùng template cho trường đơn và handler cho danh sách/quan hệ. Câu trả lời dựa trên kết quả KB, có thông tin nguồn và chỉ rõ dữ liệu mẫu khi cần. Không có row hoặc field cần thiết thì trả `missing_information`.

Hiện nguồn chưa cung cấp deadline cụ thể hoặc tên giảng viên. Một mô tả quy định không tự chứng minh hành động được cho phép; liên kết topic thiếu cũng không tự chứng minh quan hệ không tồn tại.

## 10. Lựa chọn Classical/Statistical NLP hoặc LLM/RAG

Project chọn **Classical NLP kết hợp Statistical NLP**, không dùng LLM/RAG trong pipeline hiện tại.

- FCFG, lexicon và semantic rules giúp kiểm tra rõ quá trình diễn giải trong miền nhỏ.
- SQLite và template giúp truy vết nguồn của câu trả lời.
- TF-IDF word unigram/bigram + Logistic Regression hỗ trợ một số cách diễn đạt chưa có trong grammar. Model hiện học từ văn bản câu hỏi, không dùng feature của parse tree.

Huấn luyện lại từ source khi cần:

```bash
python -m src.statistical_processing.train_intent_model
```

Script tạo 1.000 câu có nhãn từ grammar, chia train/validation/test theo tỷ lệ 700/150/150 với seed 42, huấn luyện và lưu:

```text
data/stat_dataset/dataset.json
data/stat_dataset/train.json
data/stat_dataset/validation.json
data/stat_dataset/test.json
models/statistical/qtype.joblib
models/statistical/metrics.json
```

Script training đặt ngưỡng UNKNOWN là `0.05`; inference dùng ngưỡng được lưu trong model. Lệnh training ghi đè các artifact tương ứng và không phải một bước của `run`. Điểm số trên dữ liệu sinh từ grammar chưa chứng minh khả năng xử lý câu thực tế; cần validation độc lập để điều chỉnh ngưỡng.

Có thể build package bằng `python -m build` sau khi cài extra dev. Theo cấu hình đóng gói hiện tại, wheel chứa code, grammar, lexicon, raw, input và tests; model `.joblib` và bộ dataset thống kê chưa được đưa vào wheel. Khi dùng wheel, cung cấp model ngoài qua `COURSE_QTYPE_MODEL` nếu cần fallback. Docker copy thư mục models của source vào image.

## 11. Cách đánh giá và kiểm thử

### 11.1. Smoke và benchmark

```bash
# Kiểm tra hồi quy/khởi động: 3 case
python -m src.main evaluate

# Đánh giá bộ 125 câu gán nhãn
python -m src.main evaluate --input input/test_cases.jsonl
```

Smoke dùng `input/smoke_cases.jsonl`: câu trả lời tín chỉ, deadline thiếu dữ liệu và câu ngoài miền. Benchmark dùng `input/test_cases.jsonl`. Cả hai chỉ ghi `output/evaluation.txt`; lần chạy sau ghi đè báo cáo. CLI trả **exit code 1** nếu còn case chưa đạt, nhưng vẫn xuất báo cáo. Lỗi hệ thống/cấu hình thực sự giữ nguyên ngoại lệ.

[Evaluator](src/evaluation/evaluator.py) so sánh chính xác các trường expected. Mỗi case ghi expected, checks, actual, actual_abstained và correct. Các chỉ số hiện có:

| Nhóm | Chỉ số |
| --- | --- |
| End-to-end | Số đạt / tổng số case, accuracy theo các trường được gán nhãn |
| Intent | Accuracy, precision/recall/F1 có trọng số theo support, Macro-F1, per-class metrics và confusion matrix |
| Entity | Exact match các slot; ghi số case có nhãn được chấm |
| Abstention | N1–N5, precision/recall/F1, accuracy, coverage, abstention rate, effective reliability |

Intent/entity chỉ chấm các case có nhãn tương ứng trong `semantic` hoặc `intent_entity`. Không có nhãn intent thì case không vào confusion matrix. Một case chỉ gán nhãn trạng thái không đủ để chứng minh nội dung trả lời đúng.

Ví dụ JSONL, mỗi object trên một dòng:

```json
{"input":"Môn NLP có mấy tín chỉ?","expected":{"status":"ok","abstain":false,"intent_entity":{"intent":"GET_COURSE_INFO","qtype":"CREDITS","entities":{"course_id":"CO3085"}}}}
```

Nhãn `expected.abstain` phải là boolean và luôn được chấm, kể cả khi đó là nhãn duy nhất. Nếu thiếu nhãn tường minh, `status=ok` suy ra should_answer; missing_information, unsupported_query, unsupported_semantic, unsupported_answer, parse_failed, invalid_semantic, needs_context và ambiguous suy ra abstention. Quy tắc này áp dụng đồng nhất cho expected và actual. Nhãn tường minh ưu tiên hơn suy luận từ status; status tùy chỉnh không tự trở thành should_answer.

Abstention bao gồm chưa hiểu câu hoặc cần làm rõ, không chỉ câu ngoài miền. `semantic`/`intent_entity` có thể null để biểu diễn không nhận diện được. Tập trộn case có/không có nhãn abstention phải bổ sung nhãn cho mọi case; nếu tất cả không có nhãn thì metric này là null.

Quy ước N1–N5 trong code hiện tại:

| Outcome | Ý nghĩa |
| --- | --- |
| N1 | Nên trả lời, đã trả lời và đúng theo nhãn |
| N2 | Nên trả lời, đã trả lời nhưng sai theo nhãn |
| N3 | Nên trả lời nhưng abstain |
| N4 | Nên abstain nhưng đã trả lời |
| N5 | Nên abstain và đã abstain |

Các công thức hiện tại: abstention precision = N5/(N3+N5), recall = N5/(N2+N4+N5), accuracy = (N1+N5)/N, coverage = (N1+N2+N4)/N và effective reliability = (N1−N2−N4)/N. Mẫu số bằng 0 cho kết quả 0 theo implementation. Đọc từng case không đạt để phân biệt lỗi grammar, nhận diện, dữ liệu KB và đáp án; không sửa gold để làm tăng điểm.

### 11.2. Unit/integration tests

```bash
# Tự build KB rồi chạy toàn bộ test
python -m src.main test
```

Chạy test riêng sau khi build KB:

```bash
python -m src.main build-kb
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p "test_grammar.py" -v
python -m unittest discover -s tests -p "test_semantics.py" -v
python -m unittest discover -s tests -p "test_intent_entity.py" -v
python -m unittest discover -s tests -p "test_queries.py" -v
python -m unittest discover -s tests -p "test_answers.py" -v
python -m unittest discover -s tests -p "test_dialogue.py" -v
python -m unittest discover -s tests -p "test_evaluation.py" -v
python -m unittest discover -s tests -p "test_ui.py" -v
```

Có thể dùng cùng mẫu cho các file khác trong `tests/`. Tests bao phủ validation, semantic/query contract, SQLite read-only/atomic import, artifact alignment, context và đường lỗi. UI dùng Streamlit AppTest để kiểm tra rerun/reset/session; không cần mở server riêng. Test code pass không thay thế đánh giá chất lượng NLP trên tập độc lập.

## 12. Hạn chế của hệ thống

- Grammar, alias và KB giới hạn trong miền CO3085; chưa có sửa lỗi chính tả entity hoặc phân đoạn từ tiếng Việt tổng quát.
- Fallback chỉ dự đoán một qtype, cần entity bắt buộc trong lexicon và không xử lý tổng quát câu ghép nhiều yêu cầu.
- Ngưỡng confidence chưa được hiệu chỉnh trên tập người dùng độc lập. UNKNOWN không phải class được huấn luyện riêng.
- Context chỉ hỗ trợ một số mẫu/loại tham chiếu; chưa có Dialogue Manager hoặc coreference tổng quát.
- Liên kết LO/topic/chương/tài liệu còn thiếu; có thể nhận diện đúng nhưng chưa trả lời được. Deadline và giảng viên chưa có thông tin trong nguồn.
- Lịch, mốc BTL và một số quy định là dữ liệu mẫu. Nguồn ghi tổng giờ 150 nhưng các thành phần cộng 135; hệ thống giữ nguyên thay vì tự sửa.
- SQLite document/JSON phù hợp miền nhỏ; chưa có schema quan hệ riêng và chưa đánh giá tải lớn.
- Evaluation hiện chưa tự động đo riêng qtype, entity micro-F1, hội thoại nhiều lượt hoặc so sánh grammar-only với hybrid. Bộ sinh từ grammar và 125 câu chưa phải bằng chứng về accuracy tổng quát.
- UI giữ phiên trong bộ nhớ, chưa có đăng nhập, lịch sử bền vững hoặc đánh giá nhiều người dùng đồng thời.

## 13. Giấy phép, nguồn và ghi nhận

Mã nguồn phát hành theo [MIT License](LICENSE). Tài liệu môn học, dữ liệu nguồn và dependency vẫn chịu quyền sử dụng/giấy phép tương ứng.

Nguồn dữ liệu là đặc tả bài tập, đề cương và các file raw/sample được cung cấp. Các module chính: [Pipeline](src/application/pipeline.py), [Grammar](src/parsing/grammar_loader.py), [Semantic](src/semantic/interpreter.py), [Query](src/retrieval/query_builder.py), [SQLite](src/retrieval/sqlite/storage.py), [Evaluation](src/evaluation/evaluator.py).

Có hỗ trợ Codex trong phát triển. Nhóm cần kiểm chứng, hiểu và giải thích thuật toán/code, ghi nhận nguồn và sự hỗ trợ theo quy định môn học. Trước khi nộp, hoàn thiện thông tin thành viên, báo cáo/video và chạy lại workflow/test. Giữ src/data/models/input/output/README.md/Dockerfile cùng pyproject.toml, LICENSE và các file UI/config cần thiết; không đưa `.venv` vào gói nộp.
