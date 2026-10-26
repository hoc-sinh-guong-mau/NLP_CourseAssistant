"""Answer templates dispatched by semantic request type."""
from .exceptions import AnswerError, UnsupportedAnswerError


def render_deadline(records):
    if not records or not records[0].get("deadline"):
        return "missing_information", "Dữ liệu môn học chưa có thời hạn của bài tập này."
    row = records[0]
    if not row.get("name"):
        raise AnswerError("Deadline record is missing its display name")
    return "ok", f"Hạn nộp {row['name']} là {row['deadline']}."


ANSWER_HANDLERS = {("GET_DEADLINE", "DEADLINE"): render_deadline}


class AnswerGenerator:
    def __init__(self, handlers=None):
        self.handlers = dict(ANSWER_HANDLERS if handlers is None else handlers)

    def render(self, frame, records):
        key = (frame.predicate, frame.qtype)
        if key not in self.handlers:
            raise UnsupportedAnswerError(f"Unsupported answer template: {key}")
        return self.handlers[key](records)

