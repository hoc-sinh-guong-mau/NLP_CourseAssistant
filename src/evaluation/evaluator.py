"""Score independent labeled cases and compare grammar-only with hybrid NLP."""
from pathlib import Path
from time import perf_counter

from src.application.pipeline import CourseAssistant
from src.config import INPUT_DIR, OUTPUT_DIR
from src.dialogue import DialogueSession

from .dataset import load_cases
from .exceptions import EvaluationError
from .metrics import compare_cases, summarize
from .reporting import dataset_metadata, runtime_metadata, write_report
from .scoring import score_turn


def _run(cases, assistant):
    results = []
    for case in cases:
        # Context must never cross a case or system boundary.
        process = DialogueSession(assistant).process if case['dialogue'] else assistant.process
        turns = []
        for number, turn in enumerate(case['turns'], 1):
            started = perf_counter()
            actual = process(turn['input'])
            elapsed = (perf_counter() - started) * 1000
            turns.append({'turn': number, 'input': turn['input'], 'elapsed_ms': elapsed,
                          **score_turn(turn['expected'], actual)})
        results.append({'id': case['id'], 'tags': case['tags'], 'dialogue': case['dialogue'],
                        'correct': all(turn['correct'] for turn in turns), 'turns': turns})
    return {'metrics': summarize(results), 'cases': results}


def _grammar_only(assistant):
    return CourseAssistant(parser=assistant.parser, semantic=assistant.semantic, kb=assistant.kb,
                           query_builder=assistant.query_builder, answer_generator=assistant.answer_generator,
                           use_statistical=False)


def evaluate(assistant=None, *, cases_path=INPUT_DIR / 'test_cases.jsonl',
             output_path=OUTPUT_DIR / 'evaluation.txt', compare=False, baseline=None):
    """Legacy smoke inputs/total/passed stay compatible; --compare adds a baseline.

    Total/passed count whole cases (every labeled turn must match). Missing metric
    annotations produce null accuracy with support=0 rather than an invented zero.
    System/configuration errors propagate; they must not become NLP mistakes.
    """
    if Path(cases_path).resolve() == Path(output_path).resolve():
        raise EvaluationError('Evaluation input and output must be different files')
    if baseline is not None and not compare:
        raise EvaluationError('A baseline assistant requires compare=True')
    cases = load_cases(cases_path)  # Validate every label before model initialization or processing.
    metadata = dataset_metadata(cases_path, cases)
    assistant = CourseAssistant() if assistant is None else assistant
    systems = {}
    if compare:
        baseline = _grammar_only(assistant) if baseline is None else baseline
        systems['grammar_only'] = {**_run(cases, baseline), 'configuration': runtime_metadata(baseline)}
    systems['hybrid'] = {**_run(cases, assistant), 'configuration': runtime_metadata(assistant)}
    primary = systems['hybrid']
    report = {
        'schema_version': 2, 'backend': 'sqlite', 'primary_system': 'hybrid',
        'note': 'Scores describe only the supplied labeled cases. No representative accuracy claim. '
                'Answer text checks and retrieved facts are separate; neither is a general factuality judge.',
        'dataset': metadata,
        'total': len(cases), 'passed': sum(case['correct'] for case in primary['cases']),
        'metrics': primary['metrics'], 'cases': primary['cases'], 'systems': systems,
    }
    if compare:
        report['comparison'] = compare_cases(systems['grammar_only']['cases'], primary['cases'])
        if not primary['configuration']['statistical_model_loaded']:
            report['comparison']['warning'] = 'No statistical model loaded; hybrid cannot use fallback.'
    report['failures'] = [
        {'system': name, 'case_id': case['id'], 'turn': turn['turn'], 'input': turn['input'],
         'status': turn['actual'].get('status'), 'error': turn['actual'].get('error'),
         'statistical_prediction': turn['actual'].get('statistical_prediction'),
         'checks': {key: check for key, check in turn['checks'].items() if not check['correct']}}
        for name, result in systems.items() for case in result['cases'] for turn in case['turns']
        if not turn['correct']
    ]
    write_report(output_path, report)
    print(f"Evaluation: {report['passed']}/{report['total']} cases; report: {output_path}")
    return report


def main():
    report = evaluate()
    if report['passed'] != report['total']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
