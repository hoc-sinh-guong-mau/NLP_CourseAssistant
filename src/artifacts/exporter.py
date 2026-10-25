import json
from pathlib import Path
from src.config import OUTPUT_DIR
from src.parsing.parser import grammar_text


def dump(value):
    return json.dumps(value, ensure_ascii=False)


def export_grammar(path=OUTPUT_DIR / "grammar.txt"):
    """Write the complete, validated FCFG, including the start directive."""
    text = grammar_text()  # Validate before touching an existing output file.
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def export_records(records):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    export_grammar()
    fields = {
        "parse-results.txt": "parse_tree", "semantic.txt": "semantic",
        "intent-entity.txt": "intent_entity", "query.txt": "query", "answer.txt": "answer",
    }
    for filename, field in fields.items():
        values = [r[field] if isinstance(r[field], str) else dump(r[field]) for r in records]
        (OUTPUT_DIR / filename).write_text("\n".join(values) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "traces.jsonl").write_text(
        "".join(dump(r) + "\n" for r in records), encoding="utf-8"
    )
