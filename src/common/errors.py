"""Shared error protocol; domain exceptions remain in their owning module."""


class NLPError(ValueError):
    stage = 'application'
    code = 'NLP_ERROR'
    status = None  # Only expected request failures have a response status.

    def __init__(self, message, *, context=None):
        self.message = message
        self.context = dict(context or {})
        super().__init__(message)

    def __str__(self):
        return f'[{self.stage}:{self.code}] {self.message}'

    def to_dict(self):
        return {
            'stage': self.stage, 'code': self.code,
            'type': type(self).__name__, 'message': self.message,
            'context': self.context,
        }


class StageExecutionError(NLPError):
    code = 'STAGE_EXECUTION_FAILED'

    def __init__(self, stage, message):
        self.stage = stage
        super().__init__(message)


def run_stage(stage, operation, *args, **kwargs):
    """Preserve domain errors; attach stage and original cause to unexpected ones."""
    try:
        return operation(*args, **kwargs)
    except NLPError:
        raise
    except Exception as exc:
        raise StageExecutionError(stage, str(exc)) from exc
