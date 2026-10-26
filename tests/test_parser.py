import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nltk.grammar import FeatureGrammar
from src.parsing import Parser
from src.parsing.runner import parse_file


class ParserFileTests(unittest.TestCase):
    def test_one_output_per_input_line_including_blank_and_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, trace = root / 'input.txt', root / 'out.txt', root / 'trace.jsonl'
            source.write_text('\ufeffTUẦN BA học gì???\n\ngì học tuần ba\nngoài miền\n', encoding='utf-8')
            stats = parse_file(source, output, trace)
            lines = output.read_text(encoding='utf-8').splitlines()
            self.assertEqual(stats, {'total': 4, 'parsed': 1, 'ambiguous': 0})
            self.assertEqual(len(lines), 4)
            self.assertIn("WEEK_03", lines[0])
            self.assertEqual(lines[1:], ['()', '()', '()'])
            traces = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(traces[0]['tokens'], ['tuần', 'ba', 'học', 'gì'])
            self.assertEqual(traces[0]['trees'], [lines[0]])
            self.assertEqual(traces[-1]['line'], 4)

    def test_ambiguity_keeps_all_trees_in_trace(self):
        grammar = FeatureGrammar.fromstring("% start S\nS[ENTITY=?e] -> X[ENTITY=?e]\nX[ENTITY='A'] -> 'x'\nX[ENTITY='B'] -> 'x'")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, trace = root / 'in.txt', root / 'out.txt', root / 'trace.jsonl'
            source.write_text('x\n', encoding='utf-8')
            with patch('src.parsing.runner.Parser', return_value=Parser(grammar)):
                stats = parse_file(source, output, trace)
            record = json.loads(trace.read_text(encoding='utf-8'))
            self.assertEqual(stats['ambiguous'], 1)
            self.assertEqual(record['parse_count'], 2)
            self.assertEqual(output.read_text(encoding='utf-8').strip(), record['trees'][0])

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory, 'in.txt'), Path(directory, 'out.txt')
            source.write_text('', encoding='utf-8')
            self.assertEqual(parse_file(source, output)['total'], 0)
            self.assertEqual(output.read_text(), '')

    def test_prevents_overwriting_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, 'input.txt')
            source.write_text('tuần ba học gì', encoding='utf-8')
            with self.assertRaises(ValueError):
                parse_file(source, source)
            with self.assertRaises(ValueError):
                parse_file(source, Path(directory, 'out.txt'), source)
            self.assertEqual(source.read_text(encoding='utf-8'), 'tuần ba học gì')
