"""Answer templates dispatched by semantic request type."""


class UnsupportedAnswerError(ValueError):
    """A query has no registered answer template."""


def render_deadline(records):
    if not records or not records[0].get("deadline"):
        return "missing_information", "Dữ liệu môn học chưa có thời hạn của bài tập này."
    row = records[0]
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


def render(records):
    """Legacy deadline-only function; pipeline uses AnswerGenerator."""
    return render_deadline(records)
