"""Standalone syntax analysis for assignment section 3.3 (no KB required)."""
import json
from pathlib import Path

from src.artifacts.exceptions import ArtifactError
from src.common.files import read_text, write_text
from src.config import ROOT, OUTPUT_DIR
from src.parsing import Parser
from src.preprocessing import normalize, tokenize

from .exceptions import ParseInputError


def parse_file(input_path=ROOT / "input" / "sentences.txt",
               output_path=OUTPUT_DIR / "parse-results.txt", trace_path=None):
    input_path, output_path = Path(input_path), Path(output_path)
    if input_path.resolve() == output_path.resolve():
        raise ParseInputError("Input and output must be different files")
    if trace_path is not None:
        trace_path = Path(trace_path)
        if trace_path.resolve() in {input_path.resolve(), output_path.resolve()}:
            raise ParseInputError("Trace, input and output must be different files")
    lines = read_text(input_path, ParseInputError, encoding="utf-8-sig").splitlines()
    parser = Parser()
    results, traces = [], []
    for line_number, text in enumerate(lines, 1):
        normalized = normalize(text)
        tokens = tokenize(normalized)
        trees = parser.parse_all(tokens) if tokens else []
        # Very large margin alone is not enough to promise a single output line.
        formatted = [" ".join(tree.pformat(margin=1000000).split()) for tree in trees]
        results.append(formatted[0] if formatted else "()")
        traces.append({
            "line": line_number, "input": text, "normalized": normalized,
            "tokens": tokens, "parse_count": len(formatted),
            "status": "parsed" if formatted else "parse_failed",
            "trees": formatted,
        })
    write_text(output_path, "".join(result + "\n" for result in results), ArtifactError)
    if trace_path is not None:
        write_text(trace_path, "".join(json.dumps(t, ensure_ascii=False) + "\n" for t in traces), ArtifactError)
    return {"total": len(lines), "parsed": sum(t["parse_count"] > 0 for t in traces),
            "ambiguous": sum(t["parse_count"] > 1 for t in traces)}
