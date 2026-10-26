"""Grounded domain renderers for lists, relations and special field types."""
from .exceptions import AnswerError
from .formatting import display, label, missing, present


def deadline(frame, records):
    if not records or not present(records[0].get('deadline')):
        return missing('Dữ liệu môn học chưa có thời hạn của bài tập này.')
    row=records[0]
    if not row.get('name'):
        raise AnswerError('Deadline record is missing its display name')
    return 'ok', f"Hạn nộp {row['name']} là {row['deadline']}."


def course_list(frame, records):
    if frame.qtype=='CHAPTER_COUNT':
        return ('ok',f"Theo dữ liệu KB, môn {frame.arguments['course_id']} có {len(records)} chương.") if records else missing()
    if frame.qtype=='MAIN_PARTS':
        values=[r['name'] for r in records if present(r.get('name'))]
        text='Các phần chính của môn học: '
    elif frame.qtype=='ASSESSMENT':
        values=[f"{r['id']}: {r['weight_percent']}%" for r in records if present(r.get('weight_percent'))]
        text='Các thành phần đánh giá: '
    else:
        values=[f"{r['id']}: {r['description']}" for r in records if present(r.get('description'))]
        text='Các chuẩn đầu ra: '
    return ('ok',text+display(values)) if values else missing()


def exam_open_book(frame, records):
    if not records or not isinstance(records[0].get('open_book'),bool):
        return missing('Chưa có thông tin về việc sử dụng tài liệu trong kỳ thi này.')
    allowed='được' if records[0]['open_book'] else 'không được'
    return 'ok',f"Kỳ thi {frame.arguments['exam_id']} {allowed} sử dụng tài liệu."


def schedule(frame, records):
    if not records:
        return missing('Chưa tìm thấy lịch phù hợp trong dữ liệu môn học.')
    if frame.qtype=='WEEK_CONTENT':
        row=records[0]
        if not present(row.get('topics')): return missing()
        return 'ok',f"Tuần {row['week']} học các nội dung: {display(row['topics'])}."
    if frame.qtype=='WEEK_CHAPTER':
        row=records[0]
        if not present(row.get('chapter_ids')): return missing('Chưa có chương được gán cho tuần này.')
        return 'ok',f"Tuần {row['week']} học các chương: {display(row['chapter_ids'])}."
    weeks=[r['week'] for r in records if present(r.get('week'))]
    if not weeks: return missing()
    text=f"Các tuần phù hợp với yêu cầu: {display(weeks)}."
    if frame.qtype in {'TOPIC_WEEK','TOPICS_WEEK'}:
        text+=' Đây là các liên kết chủ đề tìm thấy trong nguồn, chưa xác nhận là danh sách đầy đủ.'
    return 'ok',text


def chapter(frame, records):
    if not records:
        return missing('Chưa tìm thấy bằng chứng về chương/chủ đề được hỏi trong KB.')
    if frame.qtype=='FIND_CHAPTER_BY_LO':
        chapters=records[0].get('chapter_ids',[])
        return ('ok','Các chương đã liên kết: '+display(chapters)+'.') if chapters else missing('Nguồn chưa cung cấp liên kết chuẩn đầu ra này với chương cụ thể.')
    if frame.qtype in {'FIND_CHAPTER_BY_TOPIC','FIND_CHAPTER_BY_TOPICS'}:
        values=[f"Chương {r['number']} ({r['title']})" for r in records]
        return 'ok','Các chương có đề cập phù hợp: '+display(values)+'. Danh sách dựa trên các liên kết đã ghi nhận trong nguồn.'
    row=records[0]
    name=f"Chương {row['number']} ({row['title']})"
    if frame.qtype=='CHAPTER_HAS_TOPIC':
        topic=frame.arguments['topic_id']
        if topic in row.get('topic_ids',[]):
            return 'ok',f'Có. {name} có đề cập đến {topic}.'
        if row.get('topic_links_complete') is True:
            return 'ok',f'Không. Danh sách chủ đề đầy đủ của {name} không có {topic}.'
        return missing(f'Chưa có bằng chứng liên kết {topic} với {name}; dữ liệu chủ đề chưa đầy đủ nên chưa thể kết luận không có.')
    if frame.qtype=='CHAPTER_METHODS':
        if not present(row.get('subtopics')): return missing()
        return 'ok',f"Các mục nội dung được nguồn liệt kê cho {name}: {display(row['subtopics'])}. Nguồn chưa tách riêng một danh sách chỉ gồm các phương pháp."
    summary=row.get('summary')
    if not present(summary): return missing()
    return 'ok',f'{name}: {summary}'


def assignment(frame, records):
    if not records: return missing('Chưa tìm thấy thông tin bài tập/phần được hỏi.')
    row=records[0]
    if frame.qtype=='TEAM_SIZE':
        size=row.get('team_size')
        if not isinstance(size,dict) or not present(size.get('min')) or not present(size.get('max')): return missing()
        return 'ok',f"Bài tập lớn làm theo nhóm {size['min']}–{size['max']} sinh viên."
    if frame.qtype=='ASSIGNMENT_LIST':
        return 'ok','Các bài tập được ghi nhận: '+display([f"{r['id']}: {r.get('title',r['id'])}" for r in records])+'.'
    if frame.qtype=='HAS_COMPONENT':
        return 'ok',f"Có. Bài tập {frame.arguments['assignment_id']} có {row['id']} — {row['title']}."
    if frame.qtype=='REQUIREMENTS':
        values=[f"{r['id']} ({r['title']})"+(' [mở rộng]' if r.get('optional') else '')+': '+display(r['requirements'])
                for r in records if present(r.get('requirements'))]
        return ('ok','Yêu cầu theo từng phần: '+display(values)) if values else missing()
    if frame.qtype in {'OUTPUTS','PART_OUTPUTS'}:
        outputs=row.get('outputs')
        if not present(outputs): return missing('Nguồn chưa liệt kê file đầu ra cho phần được hỏi.')
        text='Các file được nguồn liệt kê: '+display(outputs)+'.'
        if row.get('outputs_complete') is False:
            text+=' Chưa xác nhận đây là toàn bộ danh sách file cần nộp.'
        return 'ok',text
    requirements=row.get('requirements')
    if not present(requirements): return missing()
    text=f"{row['id']} — {row['title']}: {display(requirements)}."
    if frame.qtype=='PART_INFO' and present(row.get('outputs')):
        text+=' File đầu ra được liệt kê: '+display(row['outputs'])+'.'
    return 'ok',text


def resource(frame, records):
    if not records:
        return missing('Chưa tìm thấy tài liệu phù hợp hoặc liên kết tài liệu–chủ đề trong KB.')
    if frame.qtype=='RESOURCE_AUTHOR':
        if not present(records[0].get('authors')): return missing('Nguồn chưa cung cấp tác giả của tài liệu này.')
        return 'ok',f"Tác giả của {label(frame,records[0],'resource_id')}: {display(records[0]['authors'])}."
    values=[]
    for row in records:
        if not present(row.get('title')): continue
        text=row['title']
        if present(row.get('authors')): text+=' — '+display(row['authors'])
        if present(row.get('year')): text+=f" ({row['year']})"
        values.append(text)
    return ('ok','Các tài liệu được ghi nhận: '+display(values)+'.') if values else missing()


def policy(frame, records):
    if not records or not present(records[0].get('description')): return missing('Chưa có quy định tương ứng trong nguồn.')
    row=records[0]
    text=f"Quy định về {frame.arguments['rule_id']}: {row['description']}"
    if frame.qtype=='PERMISSION':
        # Global policy descriptions do not settle an assignment-scoped permission.
        if 'assignment_id' not in frame.arguments and isinstance(row.get('permission'),bool):
            text=('Có. ' if row['permission'] else 'Không. ')+text
        else:
            return missing('Chưa có xác nhận trực tiếp cho phép/cấm hành động trong tình huống này. '+text)
    return 'ok',text


def learning_outcome(frame, records):
    if not records or not present(records[0].get('description')): return missing()
    row=records[0]
    return 'ok',f"Chuẩn đầu ra {row['id']}: {row['description']}"


def instructor(frame, records):
    names=[r['name'] for r in records if present(r.get('name'))]
    return ('ok','Giảng viên được ghi nhận: '+display(names)+'.') if names else missing('Dữ liệu môn học chưa cung cấp thông tin giảng viên.')
