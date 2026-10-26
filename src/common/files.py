"""File boundaries preserve the owning module's error type and original cause."""
from pathlib import Path


def read_text(path, error_type, *, encoding='utf-8'):
    path = Path(path)
    try:
        return path.read_text(encoding=encoding)
    except (OSError, UnicodeError) as exc:
        raise error_type(f'Cannot read {path}', context={'path': str(path)}) from exc


def write_text(path, text, error_type):
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    except (OSError, UnicodeError) as exc:
        raise error_type(f'Cannot write {path}', context={'path': str(path)}) from exc
