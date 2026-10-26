import json
from pathlib import Path

from src.common.files import write_text
from src.config import OUTPUT_DIR
from src.parsing import grammar_text

from .exceptions import ArtifactError


def dump(value):
    return json.dumps(value, ensure_ascii=False)


def export_grammar(path=OUTPUT_DIR / "grammar.txt"):
    """Write the complete, validated FCFG, including the start directive."""
    text = grammar_text()  # Validate before touching an existing output file.
    path = Path(path)
    write_text(path, text, ArtifactError)
    return path


def export_records(records, output_dir=None):
    output_dir = OUTPUT_DIR if output_dir is None else Path(output_dir)
    export_grammar(output_dir / "grammar.txt")
    fields = {
        "parse-results.txt": "parse_tree", "semantic.txt": "semantic",
        "intent-entity.txt": "intent_entity", "query.txt": "query", "answer.txt": "answer",
    }
    for filename, field in fields.items():
        values = [r[field] if isinstance(r[field], str) else dump(r[field]) for r in records]
        write_text(output_dir / filename, "".join(value + "\n" for value in values), ArtifactError)
    write_text(output_dir / "traces.jsonl", "".join(dump(r) + "\n" for r in records), ArtifactError)
