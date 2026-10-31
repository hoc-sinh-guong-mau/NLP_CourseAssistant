"""CLI argument parsing; workflows live in application.runner."""
import argparse
import logging
from pathlib import Path

from src.application.runner import AssignmentRunner
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
        'chat':'Interactive demo; /exit to quit',
        'run':'Rebuild KB and reproduce all implemented assignment outputs',
        'test':'Build KB and run unit/integration tests',
    }
    for name, description in descriptions.items():
        command = commands.add_parser(name, help=description)
        if name == 'run':
            command.add_argument('--dialogue-input', type=Path, default=defaults.dialogue_path)
        if name in {'generate','run'}:
            command.add_argument('--limit', type=sample_limit, default=DEFAULT_SAMPLE_LIMIT)
        if name in {'parse','batch','dialogue','semantic','intent-entity','query','answer','run'}:
            command.add_argument('--input', type=Path, default=defaults.dialogue_path if name=='dialogue' else defaults.input_path)
        if name in {'grammar','generate','parse','batch','dialogue','semantic','intent-entity','query','answer','evaluate','run'}:
            command.add_argument('--output-dir', type=Path, default=defaults.output_dir)
    args = cli.parse_args()
    
    config = RunConfig(
        input_path=getattr(args,'input',defaults.input_path),
        output_dir=getattr(args,'output_dir',defaults.output_dir),
        sample_limit=getattr(args,'limit',DEFAULT_SAMPLE_LIMIT),
        dialogue_path=args.input if args.command=='dialogue' else getattr(args,'dialogue_input',defaults.dialogue_path),
    )
    result = getattr(AssignmentRunner(config), args.command.replace('-','_'))()
    if args.command == 'test' and not result:
        raise SystemExit(1)
    if args.command in {'run','evaluate'} and result['passed'] != result['total']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
