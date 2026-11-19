# Đối chiếu yêu cầu bài tập CO3085

Nguồn: [course-assistant.pdf](../course-assistant.pdf), bản trùng nội dung với tài liệu người dùng cung cấp. Đề không có bảng trọng số hoặc thang điểm chi tiết; tài liệu này đối chiếu yêu cầu, không ước lượng điểm của giảng viên.

## Ma trận yêu cầu và bằng chứng

| Mục trong đề | Yêu cầu | Hiện trạng / bằng chứng |
| --- | --- | --- |
| 3.1, trang 3 | Grammar cho thông tin môn, lịch, chủ đề, BTL, deadline, tài liệu, quy định; xuất grammar.txt | Có FCFG + YAML lexicon, feature unification và export; `tests/test_assignment_acceptance.py` kiểm tra 8 câu ví dụ của mục 2 bằng parser/semantic trực tiếp |
| 3.2, trang 3 | Sinh câu hợp lệ, mỗi dòng một câu, tối đa 10.000 | CFG projection sinh ứng viên, FCFG kiểm tra lại, loại trùng, giới hạn limit/depth/candidates; tests/test_grammar.py |
| 3.3, trang 3 | Mỗi dòng input có cây hoặc `()` | NLTK FeatureChartParser, giữ dòng trống và số dòng; tests/test_parser.py, tests/test_workflows.py |
| 4.1, trang 4–5 | Parsing → semantic → intent/entity → query → KB → answer | Các module parsing, semantic, retrieval, generation; 4 output Phần II; unit/integration tests và traces trong UI |
| 4.1.5, trang 5 | Không tự tạo thông tin khi thiếu KB/ngoài miền | Status missing_information/parse_failed và các thông báo tương ứng; deadline/tên giảng viên chưa có dữ liệu không bị suy đoán |
| Phần III, trang 7 | Context cục bộ; đầu vào, context, diễn giải và trả lời | DialogueSession, typed resolver và dialogue.txt; input/evaluation_dialogues.jsonl có 5 case/10 lượt kiểm tra tham chiếu, thiếu context, lượt lỗi, đổi chủ đề |
| Phần IV, trang 7–8 | Số mẫu, số đúng, metric, lỗi, nguyên nhân, ưu/nhược điểm | evaluation.txt schema 3 có số case/lượt, answer checks, intent/qtype/entity metrics, abstention, comparison, failure categories/explanations và method_notes |
| 7.1, trang 8 | Python/Java, tái hiện môi trường, Dockerfile | Python >=3.11, pyproject.toml, .env.example, Docker với /opt/venv và user thường; CLI run/test |
| 7.2–7.3, trang 8–9 | Dữ liệu có nguồn; dùng thư viện phù hợp; Classical không bị LLM thay thế | Raw + provenance; parser NLTK, TF-IDF/LR, SQLite, template; không có API/LLM trong pipeline |
| 7.4, trang 9 | src/data/models/input/output/README/Dockerfile; ZIP nên <10MB | Các thư mục đã có; loại .venv/.git/build/cache khỏi gói nộp; model nhỏ đã được đưa vào wheel; cần kiểm tra kích thước gói sau khi thêm báo cáo/video |
| 7.5, trang 10 | README có đủ 12 nhóm nội dung | README mục 1–12; có 4 thành viên, CLI/UI/Docker, DB và test |
| 7.6, trang 10 | Báo cáo và video demo ngắn | Cần nhóm kiểm tra/hoàn thiện riêng. Chưa review báo cáo LaTeX ngoài repository hoặc xác minh video. Xem kịch bản gợi ý bên dưới |
| 8–9, trang 11 | Hiểu code, ghi nguồn/AI, thể hiện pipeline đầy đủ | README ghi nhận hỗ trợ và nguồn; mỗi thành viên cần tự giải thích thuật toán, lựa chọn model, chỉ số và lỗi khi demo |

Phần LLM/RAG là lựa chọn mở rộng, không phải điều kiện còn thiếu của hướng Classical/Statistical. Ví dụ tuần 5 trong đề là minh họa; không thay dữ liệu lịch học thực tế của bộ raw bằng ví dụ để làm đẹp câu trả lời.

## Chạy lại để kiểm tra và chuẩn bị output

```bash
python -m src.main run --limit 100
python -m src.main test
python -m src.main evaluate --input input/test_cases.jsonl \
  --dialogue-cases input/evaluation_dialogues.jsonl --compare
```

Lệnh cuối tổng hợp 125 câu đơn và 5 case hội thoại vào **một** output/evaluation.txt. Nếu còn case không đạt, lệnh trả exit code 1 và vẫn ghi báo cáo. Không dùng kết quả benchmark chưa hoàn hảo làm điều kiện chặn UI; launcher vẫn dùng smoke riêng 3 case.

`total/passed` đếm case đạt toàn bộ nhãn (một hội thoại phải đúng mọi lượt). `answer_performance.exact_text` đếm riêng các câu có nhãn đáp án và số đáp án khớp literal; `turn_accuracy` đếm lượt. Các chỉ số này không đồng nghĩa khả năng trả lời đúng trên mọi câu ngoài tập đánh giá.

## Các điểm cần trình bày trung thực trong báo cáo

- Test set phát triển hiện có câu lặp sau chuẩn hóa và một nhãn qtype mâu thuẫn: case_044 ghi DOMAIN trong semantic nhưng TITLE trong intent/entity. Code giữ nguyên gold và exact checks, chỉ cảnh báo và loại trường xung đột khỏi metric thành phần. Nhóm cần rà soát nguồn trước khi sửa nhãn, rồi đánh giá lại theo phiên bản dataset mới.
- Khi mở rộng grammar sau khi xem lỗi trên test phát triển, không gọi điểm mới là điểm trên một test mù độc lập. Cần bộ câu do người khác viết/chưa dùng để điều chỉnh grammar và ngưỡng nếu muốn đo tổng quát hóa.
- N1–N5 kế thừa quy ước task-aware của project. `binary_decision` báo riêng quyết định abstain theo nhị phân; không trộn hai công thức recall/accuracy.
- Các nguyên nhân trong error_analysis mô tả bottleneck quan sát được, không tự chứng minh nguyên nhân gốc. Đối chiếu expected, semantic, query và nguồn KB trước khi kết luận.
- Không bổ sung deadline, tên giảng viên, permission hay liên kết tài liệu bằng suy đoán. Khi thiếu bằng chứng, missing_information là hành vi đúng yêu cầu.
- So sánh grammar-only/hybrid dùng cùng dữ liệu và component nghiệp vụ; không tự retrain hay hạ ngưỡng trên test. Latency là đo tuần tự trên môi trường hiện tại, không phải kiểm thử tải.

## Kịch bản demo gợi ý

1. Mở Streamlit, bật phân tích pipeline. Hỏi “Môn NLP có bao nhiêu tín chỉ?” và giải thích tokens, cây, SemanticFrame, intent/entity, query và nguồn đáp án.
2. Hỏi “Bài tập lớn có những yêu cầu gì?” để minh họa grammar và truy vấn các phần BTL.
3. Hỏi “Bạn cho mình hỏi số tín chỉ của NLP với” để quan sát có dùng fallback hay không trong model hiện tại; chỉ khẳng định khi statistical_used=true.
4. Hỏi phần parser của BTL rồi “Phần này cần xuất file gì?” để minh họa context/source_turn.
5. Hỏi deadline BTL để thể hiện thiếu dữ liệu và một câu ngoài miền để thể hiện giới hạn.
6. Mở evaluation.txt: số mẫu/đáp án khớp, so sánh baseline, một lỗi cụ thể, nhãn mâu thuẫn, ưu điểm và hạn chế.

Đây là kịch bản và bằng chứng kỹ thuật, không thay thế việc ghi video thật và thuyết trình của nhóm. Khi đóng gói, dùng tên theo đề: `2153756-2312001-2312159-2313864.zip`; thêm báo cáo/video hoặc đường dẫn theo hướng dẫn nộp bài thực tế.
