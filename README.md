# Course Assistant — Bài tập lớn CO3085

Trợ lý hỏi đáp tiếng Việt trong miền thông tin môn học **Xử lý Ngôn ngữ Tự nhiên**. Hệ thống kết hợp **Classical NLP** (Feature-based CFG, Chart Parser, semantic rules) với **Statistical NLP** (TF-IDF + Logistic Regression làm fallback), truy vấn SQLite và sinh câu trả lời theo mẫu. Chương trình có CLI và giao diện hội thoại Streamlit.

## 1. Thành viên nhóm

| Họ và tên | MSSV |
| --- | --- |
| Trương Hiếu Quyền | 2153756 |
| Ngô Chí Lực | 2312001 |
| Huỳnh Hồ Nam | 2312159 |
| Thân Trọng Minh Văn | 2313864 |

## 2. Hướng dẫn cài đặt

### 2.1. Yêu cầu môi trường

- Python **3.11 trở lên** theo metadata; môi trường tham chiếu để tái hiện là **Python 3.11 trong Docker**. Python 3.14 cũng đã được kiểm thử trên máy phát triển; chưa xác minh mọi phiên bản Python/OS.
- Dependency khai báo trong [pyproject.toml](pyproject.toml): NLTK, PyYAML, Streamlit, python-dotenv, scikit-learn, joblib và matplotlib.
- SQLite dùng thư viện chuẩn `sqlite3`, cần hỗ trợ JSON functions; không cần cài database server.
- Không cần API key, mô hình LLM hoặc tải corpus NLTK.

Thực hiện các lệnh từ **thư mục project chứa README.md và pyproject.toml**. Dùng `python -m src.main` để chạy CLI theo package.

### 2.2. Cài đặt trên máy

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints/python311.txt -e ".[dev]"
python -m pip check
```

Trên Windows PowerShell, dùng `py -3.11 -m venv .venv` và `.venv\Scripts\Activate.ps1`. Có thể thay bước cài dependency bằng `python -m pip install -c constraints/python311.txt -r requirements.txt`; file requirements trỏ về project. Extra `dev` chỉ cần thêm khi muốn build wheel/sdist.

[constraints/python311.txt](constraints/python311.txt) lưu phiên bản runtime trực tiếp và gián tiếp đã kiểm chứng trong Docker Linux/Python 3.11. Constraints chỉ giới hạn những dependency cần cài, không ép cài mọi package trong file. Docker dùng cùng constraints. Khi dùng Python khác, có thể cài `python -m pip install -e ".[dev]"` để resolver chọn dependency tương thích, nhưng đó là môi trường khác và cần chạy lại test/benchmark. Không mang constraints Python 3.11 sang Python khác nếu resolver báo không tương thích.

Model joblib đi kèm dùng scikit-learn 1.9.1 và joblib 1.6.0; hai phiên bản này được pin trong pyproject.toml. Giữ nguyên model khi tái hiện; huấn luyện lại làm thay đổi artifact và có thể thay đổi kết quả. Chỉ nạp model joblib từ nguồn tin cậy.

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

Để tái hiện kết quả nộp bài từ một checkout mới, sau bước cài đặt và cấu hình:

```bash
python -m src.main test
python -m src.main run --limit 100
python -m src.main evaluate --input input/test_cases.jsonl \
  --dialogue-cases input/evaluation_dialogues.jsonl --compare
```

Hai lệnh đầu phải trả exit code 0. Lệnh cuối hiện trả **1** vì benchmark còn case chưa đạt; đây là kết quả chấm, vẫn có báo cáo. Không nối benchmark bằng `&&` với lệnh mở UI. Với phiên bản dữ liệu/model đã kiểm chứng: smoke **3/3**, benchmark tổng hợp **94/130 case**, trong đó hội thoại **5/5**. Hash dataset/model nằm trong report để đối chiếu; latency và thông tin runtime không giống byte giữa các máy. Không sửa gold hoặc retrain chỉ để khớp các con số này.

Checkout phải có `input/sentences.txt`, `input/smoke_cases.jsonl`, `input/test_cases.jsonl`, `input/dialogues.txt`, `input/evaluation_dialogues.jsonl` và `models/statistical/qtype.joblib`. Không cần `.env`, DB hay output từ máy tác giả; `.env` là tùy chọn vì đã có mặc định. Bộ source nộp bài cần giữ các fixture/model này.

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
| Biểu đồ đánh giá | `plot` | PNG trong reports/evaluation/, không thêm file vào output/ |
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
  course-assistant evaluate --input input/test_cases.jsonl \
    --dialogue-cases input/evaluation_dialogues.jsonl --compare
```

Lệnh Docker `evaluate` cũng trả exit code 1 khi benchmark chưa đạt toàn bộ. Trước khi chạy lệnh này trong một container mới, DB đã được build trong image; không cần giữ container trước đó.

Dùng cấu hình local với container:

```bash
docker run --rm --env-file .env -e STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
  -p 127.0.0.1:8501:8501 -v "$PWD/output:/app/output" nlp-course-assistant
```

Path trong `.env` phải phù hợp filesystem của container; không dùng `.env` có `COURSE_ROOT` trỏ đến đường dẫn trên máy host. Nếu đổi `STREAMLIT_SERVER_PORT`, đổi cả cổng container bên phải của `-p`; nếu chỉ đổi cổng truy cập trên host, đổi cổng bên trái. Trên Linux, thư mục output bind mount cần cho UID 10001 quyền ghi; có thể dùng named volume như `-v nlp-output:/app/output` để lưu kết quả trong Docker. Có thể mount input bằng `-v "$PWD/input:/app/input:ro"`. SQLite nhúng trong ứng dụng, không có container DB riêng.

Nếu bind mount báo `PermissionError`, có thể chạy CLI bằng UID/GID của người dùng Linux (DB/output ghi vào mount) hoặc dùng named volume. Ví dụ tránh đổi quyền thư mục trên host:

```bash
docker run --rm --user "$(id -u):$(id -g)" \
  -e COURSE_DATABASE=/tmp/course-assistant.sqlite3 \
  -v "$PWD/output:/app/output" nlp-course-assistant course-assistant run
```

`pyproject.toml` và constraints cố định dependency runtime; tag base `python:3.11-slim` và build tooling vẫn có thể cập nhật. Muốn lưu đúng môi trường đã chấm, lưu image bằng `docker save -o /tmp/nlp-course-assistant.tar nlp-course-assistant` hoặc ghi lại image digest. Không đưa file image vào ZIP source nộp bài.

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

Có thể build package bằng `python -m build` sau khi cài extra dev. Wheel chứa code, grammar, lexicon, raw, input, tests và model/metrics thống kê hiện có trong `models/statistical/`; bộ dataset huấn luyện không đi kèm wheel. Khi chạy wheel ngoài repository, không dùng `--input input/...` trừ khi đã copy input tới thư mục hiện tại; các lệnh không chỉ định input dùng fixture đóng gói. DB/output được ghi ở thư mục đang chạy và cần quyền ghi. Có thể cung cấp model khác qua `COURSE_QTYPE_MODEL`. Docker copy thư mục models của source vào image và cache lớp cài dependency theo pyproject.toml và constraints/python311.txt để thay code không phải tải lại toàn bộ thư viện.

## 11. Cách đánh giá và kiểm thử

### 11.1. Smoke, benchmark và so sánh phương pháp

```bash
# Kiểm tra khởi động/hồi quy: 3 case, dùng trong run và Docker launcher
python -m src.main evaluate

# 125 câu đơn: so sánh grammar-only với pipeline có fallback
python -m src.main evaluate --input input/test_cases.jsonl --compare

# Báo cáo nộp bài: gộp thêm 5 case/10 lượt hội thoại
python -m src.main evaluate --input input/test_cases.jsonl \
  --dialogue-cases input/evaluation_dialogues.jsonl --compare
```

Smoke dùng `input/smoke_cases.jsonl`; benchmark 125 câu giữ trong `input/test_cases.jsonl`. Cả ba cách chỉ ghi `output/evaluation.txt`; `--output-dir` đổi thư mục, lần chạy sau ghi đè file. Case hội thoại có định dạng JSONL với `turns`, khác file text đầu vào của CLI `dialogue`. ID phải duy nhất khi gộp hai dataset.

CLI trả **exit code 1** nếu hệ thống chính còn case chưa đạt, nhưng vẫn xuất đầy đủ báo cáo. Lỗi cấu hình/hệ thống giữ nguyên ngoại lệ. Benchmark chưa đạt không chặn UI, vì launcher dùng smoke riêng. Khi chuẩn bị nộp bài, chạy lệnh đánh giá tổng hợp **sau** `run` để evaluation.txt chứa benchmark và context thay vì chỉ có smoke.

Evaluator được tách thành `dataset.py` (validation/audit), `scoring.py` (checks), `metrics.py` (chỉ số), `reporting.py` (phân tích lỗi) và `evaluator.py` (điều phối). Report schema 3 giữ các trường `total`, `passed`, `cases`, `task_performance`, `abstention_performance`, đồng thời bổ sung:

| Nội dung | Ý nghĩa |
| --- | --- |
| dataset_metadata | SHA-256, số case/lượt, nhãn mâu thuẫn và câu trùng sau chuẩn hóa |
| answer_performance | Số câu có nhãn đáp án, số khớp literal; kiểm tra sự kiện và cụm từ nếu được gán nhãn |
| task_performance | Intent/qtype accuracy, weighted precision/recall/F1, Macro-F1, confusion; entity exact match và micro precision/recall/F1 theo cặp slot/ID; độ bao phủ parser; độ đúng từng trường |
| fallback_performance | Số lượt thử/chấp nhận, độ đúng trên lượt được chấp nhận, coverage của nhãn semantic |
| dialogue_performance | Số session đúng toàn bộ lượt và kiểm tra context/source_turn |
| comparison | Baseline grammar-only, các lượt được phục hồi/làm sai thêm và chênh lệch turn accuracy |
| error_analysis / failures | Nhóm lỗi, ví dụ, giải thích quan sát, trường expected không khớp, trạng thái và dự đoán thống kê |
| runtime / latency_ms | Model hash/ngưỡng, phiên bản Python; median/p95 từng lượt, không tính khởi tạo, không phải load test |
| method_notes | Ưu điểm và hạn chế cần trình bày khi đánh giá |

`total/passed` đếm case; một hội thoại chỉ đúng khi mọi lượt đạt mọi nhãn. `turn_accuracy` đếm lượt. `answer_performance.exact_text` báo riêng số đáp án khớp trên số câu có nhãn answer, không đồng nhất với số case đúng toàn bộ pipeline. Metric không có nhãn có count=0 hoặc null, không tự suy thành lỗi model. Intent/qtype Macro-F1 giữ quy ước trên tập nhãn xuất hiện trong gold/prediction; entity micro-F1 so tập slot/ID, còn exact checks giữ thứ tự/biểu diễn gốc.

**Chất lượng gold:** report cảnh báo nếu semantic và intent/entity mâu thuẫn. Raw checks không đổi; trường mâu thuẫn bị loại riêng khỏi metric thành phần, không chọn đáp án thuận tiện và không sửa dataset tự động. Case_044 hiện có DOMAIN/TITLE không thống nhất; một số câu trùng sau chuẩn hóa vẫn được giữ để đối chiếu. Vì đây là tập phát triển, không gọi kết quả là accuracy trên test mù độc lập.

Dạng case cũ vẫn hoạt động. Có thể dùng nhãn rút gọn intent/qtype/entities và các checks bổ sung:

```json
{"id":"credits_case","tags":["paraphrase"],"input":"Cho mình hỏi số tín chỉ của NLP với","expected":{"intent":"GET_COURSE_INFO","qtype":"CREDITS","entities":{"course_id":"CO3085"},"status":"ok","abstain":false,"result_contains":[{"credits":3}],"answer_contains":["3 tín chỉ"]}}
```

`result_contains` kiểm tra mapping con trong các row KB; `answer_contains`/`answer_not_contains` kiểm tra cụm từ sau NFC/casefold/chuẩn hóa khoảng trắng. Chúng chỉ kiểm tra phần được gán nhãn, không tự chứng minh toàn bộ câu trả lời đúng về sự kiện. Query, answer, semantic và intent_entity truyền thống vẫn so sánh chính xác như trước.

Ví dụ case hội thoại, mỗi object trên một dòng:

```json
{"id":"part_reference","tags":["dialogue"],"turns":[{"input":"Bài tập lớn có phần parser không?","expected":{"status":"ok"}},{"input":"Phần này cần xuất file gì?","expected":{"status":"ok","context_used":{"source_turn":1},"answer_contains":["output/grammar.txt"]}}]}
```

Mỗi case và mỗi chế độ so sánh có session riêng. `--compare` chia sẻ grammar/KB/component nghiệp vụ nhưng tắt thống kê ở baseline bằng `CourseAssistant(use_statistical=False)`; không retrain hoặc thay threshold. Nếu chưa có model, report ghi rõ primary không dùng được fallback.

**Abstention:** `expected.abstain` là boolean và luôn được chấm. Nếu thiếu nhãn tường minh, status=ok suy ra should_answer; missing_information, unsupported_query, unsupported_semantic, unsupported_answer, parse_failed, invalid_semantic, needs_context và ambiguous suy ra abstention. Status tùy chỉnh không tự trở thành should_answer. Một tập phải gán nhãn nhất quán cho mọi lượt nếu muốn chấm abstention; semantic/intent_entity null là nhãn không nhận diện được. Abstention không tự khẳng định câu ngoài miền.

Giữ nguyên quy ước task-aware N1–N5: N1 trả lời đúng, N2 trả lời sai, N3 nên trả lời nhưng từ chối, N4 nên từ chối nhưng trả lời, N5 từ chối đúng. Precision=N5/(N3+N5), recall=N5/(N2+N4+N5), accuracy=(N1+N5)/N, coverage=(N1+N2+N4)/N, effective reliability=(N1−N2−N4)/N. Mẫu số bằng 0 cho kết quả 0 theo implementation cũ. `binary_decision` báo riêng quyết định nhị phân: recall=N5/(N4+N5), accuracy=(N1+N2+N5)/N; một câu trả lời sai nội dung vẫn có thể là quyết định should_answer đúng. Không trộn hai nhóm chỉ số.

Xem [đối chiếu yêu cầu và kịch bản demo](docs/assignment-review.md) để chuẩn bị báo cáo/video, kiểm tra 9 artifact và các phần còn cần nhóm hoàn thiện.

### 11.2. Xuất biểu đồ từ báo cáo evaluation

```bash
python -m src.main plot
# Chỉ định báo cáo và thư mục ảnh:
python -m src.main plot --input output/evaluation.txt --output-dir reports/evaluation
```

Lệnh chỉ đọc báo cáo JSON schema 3 từ `evaluate`; không cần DB, không nạp model, không huấn luyện hoặc đánh giá lại. Chạy benchmark ở mục 11.1 trước nếu muốn vẽ kết quả 130 case; nếu lần cuối chạy `run`, biểu đồ sẽ phản ánh 3 smoke case. Benchmark trả exit code 1 vẫn tạo báo cáo hợp lệ để vẽ. `plot` trả 0 khi xuất ảnh thành công, kể cả khi báo cáo có case sai.

```text
reports/evaluation/
├── summary.png                       # Case/turn accuracy, intent/qtype macro F1, entity micro F1
├── grammar_only_summary.png          # Có khi báo cáo được tạo với --compare
├── intent_confusion_matrix.png       # Hàng: gold; cột: prediction; số lượng mẫu
├── qtype_confusion_matrix.png
├── abstention_confusion_matrix.png   # Ma trận task-aware, không phải binary decision
└── error_categories.png              # Số lượt lỗi theo nhóm quan sát của primary
```

Chỉ xuất những biểu đồ có dữ liệu tương ứng. Metric chưa có nhãn không được vẽ thành 0. Confusion matrix nhiều nhãn không chèn số trong từng ô để giữ khả năng đọc; số đếm đầy đủ vẫn ở evaluation.txt. Lệnh ghi đè ảnh cùng tên; nên dùng thư mục mới khi đổi dataset để tránh giữ ảnh từ lần chạy trước. Không dùng `models/statistical/metrics.json` làm input: đó là báo cáo model riêng, khác schema pipeline. `reports/` được loại khỏi Git/Docker build context và không làm tăng 9 artifact theo đề.

Sau khi build lại image, có thể chạy trong Docker (báo cáo phải có sẵn trên host):

```bash
mkdir -p reports
docker run --rm -v "$PWD/output:/app/output:ro" -v "$PWD/reports:/app/reports" \
  nlp-course-assistant course-assistant plot
```

Quyền ghi thư mục reports tuân theo hướng dẫn bind mount ở mục 3.4.

### 11.3. Unit/integration tests

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
python -m unittest discover -s tests -p "test_evaluation*.py" -v
python -m unittest discover -s tests -p "test_assignment_acceptance.py" -v
python -m unittest discover -s tests -p "test_runtime_optimizations.py" -v
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
- Evaluation đã đo qtype, entity micro-F1, context và ablation, nhưng gold còn mâu thuẫn/trùng, dữ liệu chưa phải test mù; exact match đáp án không phải bộ chấm sự kiện tổng quát.
- UI giữ phiên trong bộ nhớ, chưa có đăng nhập, lịch sử bền vững hoặc đánh giá nhiều người dùng đồng thời.

## 13. Giấy phép, nguồn và ghi nhận

Mã nguồn phát hành theo [MIT License](LICENSE). Tài liệu môn học, dữ liệu nguồn và dependency vẫn chịu quyền sử dụng/giấy phép tương ứng.

Nguồn dữ liệu là đặc tả bài tập, đề cương và các file raw/sample được cung cấp. Các module chính: [Pipeline](src/application/pipeline.py), [Grammar](src/parsing/grammar_loader.py), [Semantic](src/semantic/interpreter.py), [Query](src/retrieval/query_builder.py), [SQLite](src/retrieval/sqlite/storage.py), [Evaluation](src/evaluation/evaluator.py).

Có hỗ trợ Codex trong phát triển. Nhóm cần kiểm chứng, hiểu và giải thích thuật toán/code, ghi nhận nguồn và sự hỗ trợ theo quy định môn học. Trước khi nộp, kiểm tra thông tin thành viên, hoàn thiện báo cáo/video và chạy lại workflow/test. Giữ src/data/models/input/output/README.md/Dockerfile cùng pyproject.toml, constraints/, LICENSE và các file UI/config cần thiết; không đưa `.venv` vào gói nộp.
