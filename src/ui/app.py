"""Chat UI with per-browser dialogue state and optional pipeline inspection."""
import logging

import streamlit as st

from src.application.pipeline import CourseAssistant
from src.common import NLPError
from src.config import MAX_VISIBLE_TURNS
from src.dialogue import DialogueSession

LOGGER = logging.getLogger(__name__)


def reset_conversation():
    st.session_state['dialogue_session'].reset()
    st.session_state['chat_history'] = []


def render_turn(record, show_analysis):
    with st.chat_message('user'):
        st.write(record['input'])
    with st.chat_message('assistant'):
        st.write(record['answer'])
        if show_analysis:
            with st.expander('Phân tích câu hỏi'):
                st.json({key: record.get(key) for key in (
                    'status', 'tokens', 'parse_tree', 'raw_semantic', 'semantic',
                    'intent_entity', 'context_used', 'query', 'context_after',
                )})


def main():
    st.set_page_config(page_title='Course Assistant', page_icon='📚', layout='centered')
    st.title('Course Assistant')
    st.caption('Tra cứu môn học CO3085 · Classical NLP · SQLite')
    if 'dialogue_session' not in st.session_state:
        try:
            st.session_state['dialogue_session'] = DialogueSession(CourseAssistant())
            st.session_state['chat_history'] = []
        except NLPError:
            LOGGER.exception('Cannot initialize Course Assistant')
            st.error('Chưa mở được dữ liệu môn học. Hãy chạy `python -m src.main build-kb` rồi tải lại trang.')
            st.stop()

    with st.sidebar:
        st.subheader('Hội thoại')
        st.button('Hội thoại mới', key='reset_conversation', on_click=reset_conversation, use_container_width=True)
        show_analysis = st.checkbox('Hiện phân tích pipeline', key='show_analysis')
        st.markdown('**Ví dụ câu hỏi**')
        st.write('• Môn NLP có mấy tín chỉ?')
        st.write('• Bài tập lớn có phần parser không?')
        st.write('• Phần này cần xuất file gì?')
        st.caption(f'Ngữ cảnh được giữ riêng cho phiên này. Hiển thị tối đa {MAX_VISIBLE_TURNS} lượt gần nhất.')
        st.caption('Lịch và một số quy định là dữ liệu mẫu. Hệ thống sẽ nói rõ khi thiếu thông tin.')

    history = st.session_state['chat_history']
    for record in history:
        render_turn(record, show_analysis)
    if not history:
        st.info('Bạn có thể hỏi về môn học, lịch học, chương, bài tập, tài liệu và chuẩn đầu ra.')

    prompt = st.chat_input('Nhập câu hỏi về môn học', key='question')
    if prompt and prompt.strip():
        with st.spinner('Đang tra cứu…'):
            try:
                record = st.session_state['dialogue_session'].process(prompt.strip())
            except NLPError as exc:
                LOGGER.exception('Question processing failed at stage %s (%s)', exc.stage, exc.code)
                record = {'input': prompt.strip(), 'status': 'system_error',
                          'answer': 'Hệ thống gặp lỗi khi xử lý câu hỏi. Vui lòng thử lại hoặc bắt đầu hội thoại mới.'}
            except Exception:
                LOGGER.exception('Unexpected UI request failure')
                record = {'input': prompt.strip(), 'status': 'system_error',
                          'answer': 'Hệ thống gặp lỗi ngoài dự kiến. Vui lòng thử lại hoặc bắt đầu hội thoại mới.'}
        history.append(record)
        del history[:-MAX_VISIBLE_TURNS]
        render_turn(record, show_analysis)
