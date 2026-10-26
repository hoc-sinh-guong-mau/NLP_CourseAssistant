"""Configuration behavior is isolated in fresh startup processes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.config import ROOT


class ConfigurationTests(unittest.TestCase):
    def start(self, directory, *, settings=None, content=''):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(('COURSE_', 'STREAMLIT_'))}
        file = Path(directory) / '.env'
        file.write_text(content, encoding='utf-8')
        env["COURSE_ENV_FILE"] = str(file)
        env.update(settings or {})
        return subprocess.run(
            [sys.executable, '-c',
             'import json; from src.config import RunConfig, SQLITE_TIMEOUT_SECONDS; '
             'c=RunConfig(); print(json.dumps({"limit":c.sample_limit, '
             '"output":str(c.output_dir),"database":str(c.database),'
             '"input":str(c.input_path),"timeout":SQLITE_TIMEOUT_SECONDS}))'],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )

    def test_dotenv_and_relative_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.start(directory, content='COURSE_SAMPLE_LIMIT=7\nCOURSE_OUTPUT_DIR=custom-output\nCOURSE_SQLITE_TIMEOUT=1.5\nCOURSE_INPUT_DIR=custom-input\n')
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data['limit'], 7)
            self.assertEqual(data['timeout'], 1.5)
            self.assertEqual(data['output'], str(ROOT / 'custom-output'))
            self.assertEqual(data['input'], str(ROOT / 'custom-input/sentences.txt'))

    def test_process_environment_overrides_dotenv(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.start(directory, content='COURSE_SAMPLE_LIMIT=7\n',
                                settings={'COURSE_SAMPLE_LIMIT': '9'})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['limit'], 9)

    def test_invalid_settings_report_configuration_stage(self):
        invalid = {'COURSE_SAMPLE_LIMIT': ['0', '10001', 'abc'],
                   'COURSE_SQLITE_TIMEOUT': ['nan', 'inf', '0'],
                   'COURSE_LOG_LEVEL': ['verbose'], 'COURSE_OUTPUT_DIR': ['']}
        with tempfile.TemporaryDirectory() as directory:
            for key, values in invalid.items():
                for value in values:
                    with self.subTest(key=key, value=value):
                        result = self.start(directory, settings={key: value})
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn('[configuration:INVALID_CONFIGURATION]', result.stderr)
                        self.assertIn(key, result.stderr)

    def test_missing_explicit_env_file_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.start(directory, settings={'COURSE_ENV_FILE': str(Path(directory) / 'missing')})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('COURSE_ENV_FILE', result.stderr)

    def test_configured_generation_limit_preserves_cli_override(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {**os.environ, 'COURSE_SAMPLE_LIMIT': '2', 'COURSE_OUTPUT_DIR': directory}
            result = subprocess.run([sys.executable, '-m', 'src.main', 'generate', '--limit', '3'],
                                    cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len((Path(directory) / 'samples.txt').read_text().splitlines()), 3)

    def test_standalone_ui_launcher_forwards_streamlit_arguments(self):
        from unittest.mock import patch
        from src.ui.serve import main
        with patch('src.ui.serve.os.execv') as execute, patch('sys.argv', ['course-assistant-ui', '--server.port=8502']):
            main()
        execute.assert_called_once_with(sys.executable, [sys.executable, '-m', 'streamlit', 'run',
                                                       str(ROOT / 'streamlit_app.py'), '--server.port=8502'])
