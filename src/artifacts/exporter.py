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


PART_II_OUTPUTS = {
    "semantic": "semantic.txt",
    "intent_entity": "intent-entity.txt",
    "query": "query.txt",
    "answer": "answer.txt",
}


def export_records(records, output_dir=None, fields=None):
    """
    export records (dict) to each file
    
    :args:
    @records: dict
    
    save to the files
    """
    
    output_dir = OUTPUT_DIR if output_dir is None else Path(output_dir)
    fields = tuple(PART_II_OUTPUTS) if fields is None else tuple(fields)
    if any(field not in PART_II_OUTPUTS for field in fields):
        raise ArtifactError("Only assignment Part II outputs may be exported")
    for field in fields:
        values = [r.get(field) if isinstance(r.get(field), str) else dump(r.get(field)) for r in records]
        write_text(output_dir / PART_II_OUTPUTS[field], "".join(value + "\n" for value in values), ArtifactError)
