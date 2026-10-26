"""Assignment workflows: configuration, file I/O and service lifecycle."""
import json
import unittest

from src.artifacts.exceptions import ArtifactError
from src.artifacts.exporter import export_grammar, export_records
from src.common import run_stage
from src.common.files import read_text, write_text
from src.config import ROOT, RunConfig, MAX_SAMPLE_LIMIT
from src.evaluation.evaluator import evaluate
from src.dialogue import DialogueSession
from src.dialogue.runner import run_dialogues
from src.parsing import ParseInputError, GenerationError
from src.parsing.generator import generate_sentences
from src.parsing.runner import parse_file
from src.retrieval.sqlite import SQLiteKnowledgeBase, build_sqlite
from .pipeline import CourseAssistant


class AssignmentRunner:
    def __init__(self, config=None):
        self.config = RunConfig() if config is None else config
        self._assistant = None

    @property
    def assistant(self):
        if self._assistant is None:
            kb = run_stage('knowledge_base', SQLiteKnowledgeBase, self.config.database)
            self._assistant = CourseAssistant(kb=kb)
        return self._assistant

    def build_kb(self):
        counts = build_sqlite(database=self.config.database)
        self._assistant = None  # Reopen catalog after replacing the snapshot.
        print(f'SQLite KB: {sum(counts.values())} records in {len(counts)} collections.')
        return counts

    def grammar(self):
        return export_grammar(self.config.output_dir / 'grammar.txt')

    def generate(self):
        sentences = generate_sentences(self.config.sample_limit)
        write_text(self.config.output_dir / 'samples.txt', ''.join(s+'\n' for s in sentences), ArtifactError)
        print(f'Generated {len(sentences)} sentences.')
        return len(sentences)

    def parse(self):
        return parse_file(self.config.input_path, self.config.output_dir / 'parse-results.txt')

    def process(self, text, *, stop_after='answer'):
        return self.assistant.process(text, stop_after=stop_after)

    def batch(self, *, fields=None, stop_after='answer'):
        texts = read_text(self.config.input_path, ParseInputError, encoding='utf-8-sig').splitlines()
        # Keep blank lines too: all output files stay aligned with input line numbers.
        records = [self.process(text, stop_after=stop_after) for text in texts]
        export_records(records, output_dir=self.config.output_dir, fields=fields)
        print(f'Processed {len(records)} questions. Outputs: {self.config.output_dir}')
        return records

    def semantic(self):
        return self.batch(fields=('semantic',), stop_after='semantic')

    def intent_entity(self):
        return self.batch(fields=('intent_entity',), stop_after='intent_entity')

    def query(self):
        return self.batch(fields=('query',), stop_after='query')

    def answer(self):
        return self.batch(fields=('answer',))

    def dialogue(self):
        return run_dialogues(self.assistant,self.config.dialogue_path,self.config.output_dir / 'dialogue.txt')

    def evaluate(self):
        return evaluate(self.assistant, cases_path=self.config.evaluation_path,
                        output_path=self.config.output_dir / 'evaluation.txt')

    def run(self):
        limit = self.config.sample_limit
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_SAMPLE_LIMIT:
            raise GenerationError(f'limit must be between 1 and {MAX_SAMPLE_LIMIT}')
        self.build_kb()
        self.grammar()
        self.generate()
        self.parse()
        self.batch()
        self.dialogue()
        return self.evaluate()

    def test(self):
        self.build_kb()
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
        return unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()

    def chat(self):
        session=DialogueSession(self.assistant)
        print('Course Assistant — dữ liệu mẫu. /reset bắt đầu hội thoại mới; /exit để thoát.')
        while True:
            try:
                text = input('> ')
            except (EOFError, KeyboardInterrupt):
                break
            if text.strip() == '/exit':
                break
            if text.strip() == '/reset':
                session.reset()
                print('Đã bắt đầu hội thoại mới.')
                continue
            print(json.dumps(session.process(text), ensure_ascii=False, indent=2))
