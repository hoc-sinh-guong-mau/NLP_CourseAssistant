"""CLI argument parsing; workflows live in application.runner."""
import argparse
import logging
from pathlib import Path

from src.config import DEFAULT_SAMPLE_LIMIT, MAX_SAMPLE_LIMIT, LOG_LEVEL, RunConfig


def sample_limit(value):
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('limit must be an integer') from exc
    if not 1 <= number <= MAX_SAMPLE_LIMIT:
        raise argparse.ArgumentTypeError(f'limit must be between 1 and {MAX_SAMPLE_LIMIT}')
    return number


def main():
    logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    cli = argparse.ArgumentParser(description='Classical NLP Course Assistant (SQLite)')
    defaults = RunConfig()
    commands = cli.add_subparsers(dest='command', required=True)
    descriptions = {
        'build-kb':'Build SQLite from raw source files',
        'grammar':'Part I / 3.1: export grammar.txt',
        'generate':'Part I / 3.2: generate samples.txt',
        'parse':'Part I / 3.3: parse input sentences',
        'batch':'Part II: semantic, intent/entity, query and answer outputs',
        'dialogue':'Part III: local dialogue context and dialogue.txt',
        'semantic':'Part II / 1: semantic.txt only',
        'intent-entity':'Part II / 2: intent-entity.txt only',
        'query':'Part II / 3: query.txt only',
        'answer':'Part II / 4: answer.txt only',
        'evaluate':'Part IV: evaluate the provided smoke cases',
        'plot':'Render charts from an existing evaluation report (no model or KB needed)',
        'chat':'Interactive demo; /exit to quit',
        'run':'Rebuild KB and reproduce all implemented assignment outputs',
        'test':'Build KB and run unit/integration tests',
    }
    for name, description in descriptions.items():
        command = commands.add_parser(name, help=description)
        if name == 'plot':
            command.add_argument('--input', type=Path, default=defaults.output_dir / 'evaluation.txt',
                                 help='Evaluation report JSON produced by evaluate')
            command.add_argument('--output-dir', type=Path, default=Path('reports/evaluation'),
                                 help='Chart directory; defaults to reports/evaluation')
        if name == 'evaluate':
            command.add_argument('--input', type=Path, default=defaults.evaluation_path,
                                 help='Labeled JSONL cases; defaults to startup smoke checks')
            command.add_argument('--compare', action='store_true',
                                 help='Compare the configured assistant against grammar-only')
            command.add_argument('--dialogue-cases', type=Path,
                                 help='Additional labeled JSONL dialogue cases in the same report')
        if name == 'run':
            command.add_argument('--dialogue-input', type=Path, default=defaults.dialogue_path)
        if name in {'generate','run'}:
            command.add_argument('--limit', type=sample_limit, default=DEFAULT_SAMPLE_LIMIT)
        if name in {'parse','batch','dialogue','semantic','intent-entity','query','answer','run'}:
            command.add_argument('--input', type=Path, default=defaults.dialogue_path if name=='dialogue' else defaults.input_path)
        if name in {'grammar','generate','parse','batch','dialogue','semantic','intent-entity','query','answer','evaluate','run'}:
            command.add_argument('--output-dir', type=Path, default=defaults.output_dir)
    args = cli.parse_args()
    if args.command == 'plot':
        from src.evaluation.plots import plot_evaluation
        paths = plot_evaluation(args.input, args.output_dir)
        print(f'Generated {len(paths)} charts in {args.output_dir}')
        for path in paths:
            print(path)
        return
    # Argument validation/help should not initialize the NLP dependency graph.
    from src.application.runner import AssignmentRunner
    
    config = RunConfig(
        input_path=getattr(args,'input',defaults.input_path),
        output_dir=getattr(args,'output_dir',defaults.output_dir),
        sample_limit=getattr(args,'limit',DEFAULT_SAMPLE_LIMIT),
        dialogue_path=args.input if args.command=='dialogue' else getattr(args,'dialogue_input',defaults.dialogue_path),
        evaluation_path=args.input if args.command=='evaluate' else defaults.evaluation_path,
        evaluation_compare=getattr(args,'compare',False),
        evaluation_dialogue_path=getattr(args,'dialogue_cases',None),
    )
    result = getattr(AssignmentRunner(config), args.command.replace('-','_'))()
    if args.command == 'test' and not result:
        raise SystemExit(1)
    if args.command in {'run','evaluate'} and result['passed'] != result['total']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
