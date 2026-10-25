def render(records):
    if not records or not records[0].get("deadline"):
        return "missing_information", "Dữ liệu môn học chưa có thời hạn của bài tập này."
    row = records[0]
    return "ok", f"Hạn nộp {row['name']} là {row['deadline']}."
