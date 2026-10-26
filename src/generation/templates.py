"""Simple field templates keyed by semantic request type."""
from dataclasses import dataclass


@dataclass(frozen=True)
class FieldTemplate:
    field: str
    slot: str
    text: str


def build_templates():
    templates = {}
    course = {
        'CREDITS':('credits','Môn {entity} có {value} tín chỉ.'),
        'COURSE_ID':('id','Mã môn học là {value}.'),
        'COURSE_NAME':('course_name','Tên môn học là {value}.'),
        'SEMESTER':('semester','Môn {entity} thuộc học kỳ {value}.'),
        'ECTS':('ects','Môn {entity} có {value} ECTS.'),
        'COURSE_TYPE':('course_type','Khối kiến thức của môn {entity}: {value}.'),
        'DEPARTMENT':('department','Môn {entity} thuộc {value}.'),
        'FORMAT':('format','Hình thức học của môn {entity}: {value}.'),
        'DURATION_WEEKS':('duration_weeks','Môn {entity} kéo dài {value} tuần.'),
        'TOTAL_HOURS':('total_course_hours','Tổng giờ học được nguồn ghi cho môn {entity}: {value} giờ.'),
        'LECTURE_HOURS':('lecture_hours','Môn {entity} có {value} giờ lý thuyết.'),
        'ASSIGNMENT_HOURS':('major_assignment_hours','Môn {entity} có {value} giờ dành cho bài tập lớn.'),
        'SELF_STUDY_HOURS':('self_study_hours','Môn {entity} có {value} giờ tự học.'),
        'DESCRIPTION':('description','Tổng quan môn {entity}: {value}'),
        'OBJECTIVES':('objectives','Mục tiêu môn {entity}: {value}'),
    }
    for qtype,(field,text) in course.items():
        templates['GET_COURSE_INFO',qtype] = FieldTemplate(field,'course_id',text)
    for qtype,field,text in [
        ('EXAM_DURATION','duration_minutes','Kỳ thi {entity} kéo dài {value} phút.'),
        ('EXAM_FORMAT','format','Hình thức thi {entity}: {value}.'),
        ('ASSESSMENT_WEIGHT','weight_percent','Thành phần {entity} chiếm {value}% điểm.'),
    ]:
        slot = 'assessment_item_id' if qtype=='ASSESSMENT_WEIGHT' else 'exam_id'
        templates['GET_COURSE_INFO',qtype] = FieldTemplate(field,slot,text)
    for qtype,field,text in [
        ('TITLE','title','Tên bài tập: {value}.'),
        ('GOAL','goal','Mục tiêu của {entity}: {value}'),
        ('DOMAIN','domain','Miền dữ liệu của {entity}: {value}.'),
    ]:
        templates['GET_ASSIGNMENT',qtype] = FieldTemplate(field,'assignment_id',text)
    for qtype,field in [('WEEK_ACTIVITY','activity'),('WEEK_MILESTONE','milestone')]:
        templates['GET_SCHEDULE',qtype] = FieldTemplate(field,'week_id','Thông tin tuần {entity}: {value}.')
    templates['GET_RESOURCE','RESOURCE_YEAR'] = FieldTemplate('year','resource_id','Năm xuất bản của {entity}: {value}.')
    return templates


FIELD_TEMPLATES = build_templates()
