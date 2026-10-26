from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from src.config import ROOT, OUTPUT_DIR
from src.retrieval import KnowledgeBaseError


class StreamlitTests(unittest.TestCase):
    def app(self):
        app=AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=20).run()
        self.assertEqual(len(app.exception),0)
        return app

    def test_chat_and_context_survive_reruns(self):
        app=self.app()
        before={p.name:p.stat().st_mtime_ns for p in OUTPUT_DIR.iterdir() if p.is_file()} if OUTPUT_DIR.exists() else {}
        app.chat_input[0].set_value('Bài tập lớn có phần parser không?').run()
        self.assertEqual(len(app.exception),0)
        app.run()
        app.chat_input[0].set_value('Phần này cần xuất file gì?').run()
        records=app.session_state['chat_history']
        self.assertEqual(len(records),2)
        self.assertEqual(records[-1]['semantic']['arguments']['part_id'],'PART_I')
        self.assertIn('output/grammar.txt',records[-1]['answer'])
        app.checkbox(key='show_analysis').check().run()
        self.assertEqual(len(app.json),2)
        self.assertEqual(len(app.session_state['chat_history']),2)
        after={p.name:p.stat().st_mtime_ns for p in OUTPUT_DIR.iterdir() if p.is_file()} if OUTPUT_DIR.exists() else {}
        self.assertEqual(before,after)

    def test_reset_and_independent_browser_sessions(self):
        first=self.app()
        first.chat_input[0].set_value('Chương 4 nói về gì?').run()
        second=self.app()
        second.chat_input[0].set_value('Nó có liên quan đến parsing không?').run()
        self.assertEqual(second.session_state['chat_history'][-1]['status'],'needs_context')
        first.button(key='reset_conversation').click().run()
        self.assertEqual(first.session_state['chat_history'],[])
        first.chat_input[0].set_value('Nó có liên quan đến parsing không?').run()
        self.assertEqual(first.session_state['chat_history'][-1]['status'],'needs_context')

    def test_error_is_displayed_without_exposing_traceback(self):
        app=self.app()
        app.session_state['dialogue_session'].process=Mock(side_effect=KnowledgeBaseError('internal path detail'))
        with self.assertLogs('src.ui.app',level='ERROR'):
            app.chat_input[0].set_value('Môn NLP có mấy tín chỉ?').run()
        self.assertEqual(len(app.exception),0)
        answer=app.session_state['chat_history'][-1]['answer']
        self.assertNotIn('internal path detail',answer)
        self.assertEqual(app.session_state['chat_history'][-1]['status'],'system_error')

    def test_missing_kb_has_actionable_startup_message(self):
        with patch('src.ui.app.CourseAssistant',side_effect=KnowledgeBaseError('missing database')):
            with self.assertLogs('src.ui.app',level='ERROR'):
                app=AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=20).run()
        self.assertEqual(len(app.exception),0)
        self.assertIn('build-kb',app.error[0].value)
        self.assertEqual(len(app.chat_input),0)

    def test_container_launcher_runs_workflow_then_execs_streamlit(self):
        from src.ui.launch import main
        runner=Mock()
        runner.run.return_value={'passed':3,'total':3}
        with patch('src.ui.launch.AssignmentRunner',return_value=runner), patch('src.ui.launch.os.execv') as execute:
            main()
        runner.run.assert_called_once_with()
        execute.assert_called_once_with(sys.executable,[sys.executable,'-m','streamlit','run',str(ROOT/'streamlit_app.py')])
        runner.run.return_value={'passed':2,'total':3}
        with patch('src.ui.launch.AssignmentRunner',return_value=runner), patch('src.ui.launch.os.execv') as execute:
            with self.assertRaises(SystemExit): main()
        execute.assert_not_called()
