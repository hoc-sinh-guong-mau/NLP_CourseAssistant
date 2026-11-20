"""Read and validate labeled JSONL; audit contradictions without rewriting gold."""

import hashlib
import json
from pathlib import Path

from src.preprocessing import normalize

from .exceptions import EvaluationError
from .scoring import expected_abstention, label_conflicts

RECORD_FIELDS = {
    "status",
    "semantic",
    "intent_entity",
    "query",
    "answer",
    "parse_tree",
    "parse_count",
    "tokens",
    "normalized",
    "result",
    "raw_semantic",
    "context_before",
    "context_after",
    "context_used",
    "statistical_prediction",
    "fallback_validation",
    "statistical_used",
    "statistical_attempted",
    "abstained",
}
CHECK_FIELDS = RECORD_FIELDS | {
    "abstain",
    "intent",
    "qtype",
    "entities",
    "answer_contains",
    "answer_not_contains",
    "result_contains",
}


def _error(message, **context):
    raise EvaluationError(message, context=context)


def _entities(value, **context):
    if not isinstance(value, dict):
        _error("Entity slots must be a mapping", **context)
    for slot, ids in value.items():
        values = ids if isinstance(ids, list) else [ids]
        if (
            not slot
            or not values
            or any(not isinstance(item, str) or not item for item in values)
        ):
            _error("Entity slots require canonical IDs or nonempty ID lists", **context)


def _expected(value, **context):
    if not isinstance(value, dict) or not value:
        _error("Each evaluation case needs nonempty expected fields", **context)
    if set(value) - CHECK_FIELDS:
        _error(
            f"Unknown expected fields: {sorted(set(value) - CHECK_FIELDS)}", **context
        )
    if "abstain" in value and not isinstance(value["abstain"], bool):
        _error("expected.abstain must be a boolean", **context)
    for key, slot_key in (("semantic", "arguments"), ("intent_entity", "entities")):
        frame = value.get(key)
        if frame is None:
            continue
        if not isinstance(frame, dict):
            _error(f"expected.{key} must be a mapping or null", **context)
        fields = {slot_key, "qtype", "predicate" if key == "semantic" else "intent"}
        if not frame or set(frame) - fields:
            _error(f"Invalid expected.{key} fields", **context)
        if slot_key in frame:
            _entities(frame[slot_key], **context)
        for field in ("intent", "predicate", "qtype"):
            if field in frame and (
                not isinstance(frame[field], str) or not frame[field]
            ):
                _error(f"{key}.{field} must be a nonempty string", **context)
    if "entities" in value:
        _entities(value["entities"], **context)
    for key in ("intent", "qtype", "status"):
        if key in value and (not isinstance(value[key], str) or not value[key]):
            _error(f"{key} must be a nonempty string", **context)
    for key in ("statistical_used", "statistical_attempted", "abstained"):
        if key in value and not isinstance(value[key], bool):
            _error(f"{key} must be boolean", **context)
    if "parse_count" in value and (
        type(value["parse_count"]) is not int or value["parse_count"] < 0
    ):
        _error("parse_count must be a nonnegative integer", **context)
    if (
        "query" in value
        and value["query"] is not None
        and not isinstance(value["query"], dict)
    ):
        _error("query must be a mapping or null", **context)
    for key in ("answer_contains", "answer_not_contains"):
        if key in value:
            fragments = value[key]
            if (
                not isinstance(fragments, list)
                or not fragments
                or any(not isinstance(v, str) or not v.strip() for v in fragments)
            ):
                _error(f"{key} must be a nonempty list of text fragments", **context)
    if "result_contains" in value:
        rows = value["result_contains"]
        if (
            not isinstance(rows, list)
            or not rows
            or any(not isinstance(row, dict) or not row for row in rows)
        ):
            _error("result_contains requires nonempty row mappings", **context)
    for key in ("context_used", "context_after"):
        if key in value and not isinstance(value[key], dict):
            _error(f"{key} must be a mapping", **context)


def load_cases(path):
    path = Path(path)
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise EvaluationError(
            "Cannot read evaluation dataset", context={"path": str(path)}
        ) from exc
    cases, seen, warnings, sentences = [], set(), [], {}
    annotations = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(
                line,
                parse_constant=lambda v, line_number=line_number: _error(
                    f"Non-finite JSON number: {v}", line=line_number
                ),
            )
        except json.JSONDecodeError as exc:
            raise EvaluationError(
                "Invalid evaluation JSON",
                context={"line": line_number, "path": str(path)},
            ) from exc
        if not isinstance(row, dict) or set(row) - {
            "id",
            "tags",
            "input",
            "expected",
            "turns",
            "description",
        }:
            _error("Invalid evaluation case fields", line=line_number)
        case_id = row.get("id", f"case_{line_number:03}")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen:
            _error("Case IDs must be nonempty and unique", line=line_number)
        seen.add(case_id)
        tags = row.get("tags", [])
        if not isinstance(tags, list) or any(
            not isinstance(tag, str) or not tag.strip() for tag in tags
        ):
            _error("tags must be a list of nonempty strings", case=case_id)
        dialogue = "turns" in row
        if dialogue and ("input" in row or "expected" in row):
            _error("Use turns or input/expected, never both", case=case_id)
        turns = (
            row["turns"]
            if dialogue
            else [{"input": row.get("input"), "expected": row.get("expected")}]
        )
        if not isinstance(turns, list) or not turns:
            _error("Dialogue turns must be a nonempty list", case=case_id)
        for number, turn in enumerate(turns, 1):
            context = {"case": case_id, "turn": number}
            if (
                not isinstance(turn, dict)
                or set(turn) != {"input", "expected"}
                or not isinstance(turn["input"], str)
            ):
                _error("Each turn requires input text and expected labels", **context)
            _expected(turn["expected"], **context)
            annotations.append(expected_abstention(turn["expected"]) is not None)
            conflicts = label_conflicts(turn["expected"])
            if conflicts:
                warnings.append(
                    {
                        **context,
                        "kind": "conflicting_labels",
                        "fields": conflicts,
                        "note": "Raw checks preserved; conflicting fields excluded from component metrics.",
                    }
                )
            # Separate sessions may repeat the same reference legitimately.
            if not dialogue:
                sentence = normalize(turn["input"])
                if sentence in sentences:
                    warnings.append(
                        {
                            **context,
                            "kind": "duplicate_normalized_input",
                            "first_case": sentences[sentence],
                        }
                    )
                sentences.setdefault(sentence, case_id)
        cases.append(
            {
                "id": case_id,
                "tags": list(dict.fromkeys(tags)),
                "dialogue": dialogue,
                "turns": turns,
            }
        )
    if not cases:
        _error("Evaluation dataset must not be empty")
    if any(annotations) and not all(annotations):
        _error(
            "Abstention evaluation needs expected.abstain or a recognized expected.status on every case"
        )
    return cases, {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "case_count": len(cases),
        "turn_count": len(annotations),
        "annotation_warnings": warnings,
    }


def load_evaluation_data(path, dialogue_path=None):
    cases, metadata = load_cases(path)
    if dialogue_path is None:
        return cases, metadata
    dialogues, extra = load_cases(dialogue_path)
    if not all(case["dialogue"] for case in dialogues):
        _error("Supplemental dialogue cases must use the turns format")
    duplicates = {case["id"] for case in cases} & {case["id"] for case in dialogues}
    if duplicates:
        _error(f"Case IDs overlap between datasets: {sorted(duplicates)}")
    combined = cases + dialogues
    annotations = [
        expected_abstention(turn["expected"]) is not None
        for case in combined
        for turn in case["turns"]
    ]
    if any(annotations) and not all(annotations):
        _error("Combined datasets must consistently annotate abstention on every turn")
    metadata = {
        **metadata,
        "supplemental_dialogue_dataset": extra,
        "combined_case_count": len(combined),
        "combined_turn_count": len(annotations),
        "annotation_warnings": metadata["annotation_warnings"]
        + extra["annotation_warnings"],
    }
    return combined, metadata
