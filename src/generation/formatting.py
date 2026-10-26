"""Small formatting helpers; missing data is never a negative assertion."""
from pathlib import Path


def missing(message='Tôi chưa tìm thấy thông tin được hỏi trong dữ liệu môn học.'):
    return 'missing_information', message


def present(value):
    return value is not None and value != '' and value != []


def display(value):
    if isinstance(value,list):
        return '; '.join(str(item) for item in value)
    return str(value)


def label(frame, row, slot):
    if slot=='week_id' and 'week' in row:
        return str(row['week'])
    return row.get('name') or row.get('title') or frame.arguments.get(slot, row.get('id',''))


def qualify(records, text):
    if any(row.get('is_sample') for row in records):
        text = 'Theo dữ liệu mẫu: ' + text
    sources = sorted({Path(row['source']).name for row in records if row.get('source')})
    if sources:
        text += ' Nguồn: ' + ', '.join(sources) + '.'
    return text
