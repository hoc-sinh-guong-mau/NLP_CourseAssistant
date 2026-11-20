"""Observed failure diagnostics; explanations describe evidence, not guessed root causes."""

from collections import Counter

from .metrics import accuracy, flatten

EXPLANATIONS = {
    "inconsistent_gold": "Gold labels contradict each other; raw exact checks are preserved for review.",
    "model_rejected": "No grammar parse; the statistical model returned UNKNOWN or no supported intent.",
    "fallback_unresolved": "No grammar parse; fallback predicted an intent but could not create a complete semantic frame.",
    "fallback_rejected": "Fallback prediction failed course scope, reference or question-focus validation; inspect fallback_validation.",
    "grammar_no_parse": "No complete grammar parse and no usable statistical prediction.",
    "semantic_ambiguity": "More than one distinct semantic interpretation was found.",
    "unresolved_context": "The reference could not be grounded uniquely in the local session.",
    "semantic_mismatch": "The recognized intent, qtype or entities differ from the annotated request.",
    "query_mismatch": "The logical query differs from the expected query.",
    "missing_evidence": "The request did not produce enough KB evidence for an answer; inspect the query and source completeness.",
    "answer_mismatch": "The answer text/fact checks failed; literal wording differences may also trigger exact match.",
    "output_mismatch": "One or more annotated output fields did not match.",
}


def _category(row, conflicting_cases):
    actual = row["actual"]
    if (row["case_id"], row["turn"]) in conflicting_cases:
        return "inconsistent_gold"
    status = actual.get("status")
    if status == "parse_failed":
        prediction = actual.get("statistical_prediction")
        if prediction is None:
            return "grammar_no_parse"
        if prediction.get("qtype") == "UNKNOWN" or prediction.get("intent") is None:
            return "model_rejected"
        validation = actual.get('fallback_validation') or {}
        if validation.get('accepted') is False and validation.get('reason') != 'missing_entities':
            return 'fallback_rejected'
        return "fallback_unresolved"
    if status == "ambiguous":
        return "semantic_ambiguity"
    if status == "needs_context":
        return "unresolved_context"
    failed = {key for key, ok in row["checks"].items() if not ok}
    if failed & {"intent", "qtype", "entities", "semantic", "intent_entity"}:
        return "semantic_mismatch"
    if "query" in failed:
        return "query_mismatch"
    if status == "missing_information":
        return "missing_evidence"
    if failed & {"answer", "answer_contains", "answer_not_contains", "result_contains"}:
        return "answer_mismatch"
    return "output_mismatch"


def describe_failures(systems, metadata):
    conflicts = {
        (warning["case"], warning["turn"])
        for warning in metadata["annotation_warnings"]
        if warning["kind"] == "conflicting_labels"
    }
    failures = []
    summary = {}
    for name, system in systems.items():
        counts = Counter()
        examples = {}
        for row in flatten(system["cases"]):
            if row["correct"]:
                continue
            category = _category(row, conflicts)
            counts[category] += 1
            failure = {
                "system": name,
                "case_id": row["case_id"],
                "turn": row["turn"],
                "input": row["input"],
                "category": category,
                "explanation": EXPLANATIONS[category],
                "status": row["actual"].get("status"),
                "failed_fields": [key for key, ok in row["checks"].items() if not ok],
                "error": row["actual"].get("error"),
                "statistical_prediction": row["actual"].get("statistical_prediction"),
                "fallback_validation": row["actual"].get("fallback_validation"),
            }
            failures.append(failure)
            examples.setdefault(category, [])
            if len(examples[category]) < 2:
                examples[category].append(
                    {
                        "case_id": row["case_id"],
                        "turn": row["turn"],
                        "input": row["input"],
                    }
                )
        summary[name] = {
            "counts": dict(counts),
            "examples": examples,
            "note": "Categories identify observed bottlenecks, not an automatic proof of the root cause.",
        }
    return failures, summary


def answer_performance(cases):
    rows = flatten(cases)
    return {
        "exact_text": accuracy(
            row["checks"]["answer"] for row in rows if "answer" in row["checks"]
        ),
        "retrieved_facts": accuracy(
            row["checks"]["result_contains"]
            for row in rows
            if "result_contains" in row["checks"]
        ),
        "text_constraints": accuracy(
            all(
                row["checks"][key]
                for key in ("answer_contains", "answer_not_contains")
                if key in row["checks"]
            )
            for row in rows
            if any(
                key in row["checks"]
                for key in ("answer_contains", "answer_not_contains")
            )
        ),
        "note": "An exact text or fragment match is not a general semantic/factual correctness judge.",
    }
