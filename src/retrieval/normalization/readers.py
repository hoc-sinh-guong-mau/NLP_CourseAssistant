"""Readers for the supplied text format (not a general document parser)."""
import re

from src.common.files import read_text
from src.retrieval.exceptions import KnowledgeBaseError


def read_source(raw_dir, filename):
    return read_text(raw_dir / filename, KnowledgeBaseError)


def fields(text):
    """Preserve multiline values; a new key starts at column zero."""
    result, key = {}, None
    for line in text.splitlines():
        match = re.match(r'^([A-Za-z_][A-Za-z_0-9]*|Mục tiêu):\s*(.*)$', line)
        if match:
            key = match[1]
            if key in result:
                raise KnowledgeBaseError('Duplicate source field', context={'field': key})
            result[key] = [match[2]]
        elif key is not None:
            result[key].append(line)
    return {key: '\n'.join(lines).strip() for key, lines in result.items()}


def required(data, key):
    value = data.get(key, '').strip()
    if not value:
        raise KnowledgeBaseError('Missing source field', context={'field': key})
    return value


def paragraph(text):
    return ' '.join(text.split())


def items(text):
    return [line.strip().removeprefix('- ').strip() for line in text.splitlines() if line.strip()]


def blocks(text, pattern):
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if not matches:
        raise KnowledgeBaseError('Expected source blocks not found', context={'pattern': pattern})
    return [(match, text[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)].strip())
            for i, match in enumerate(matches)]
