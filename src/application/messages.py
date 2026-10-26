"""Centralized user messages for non-answer pipeline states."""
MESSAGES = {
    "parse_failed": "Tôi chưa hiểu cấu trúc câu. Ví dụ: Deadline bài tập lớn là khi nào?",
    "unsupported_semantic": "Tôi chưa diễn giải được đầy đủ câu hỏi này.",
    "invalid_semantic": "Tôi chưa diễn giải được đầy đủ câu hỏi này.",
    "ambiguous": "Câu hỏi có nhiều cách hiểu. Bạn vui lòng làm rõ.",
    "needs_context": "Câu hỏi cần ngữ cảnh từ lượt trước.",
    "unsupported_query": "Tôi đã phân tích được câu hỏi nhưng chưa hỗ trợ truy vấn này.",
    "unsupported_answer": "Tôi đã truy xuất được dữ liệu nhưng chưa có mẫu trả lời phù hợp.",
}


def set_status(record, status, **details):
    record.update(status=status, answer=MESSAGES[status], **details)
    return record
