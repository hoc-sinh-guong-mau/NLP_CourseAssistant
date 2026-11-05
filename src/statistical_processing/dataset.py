"""Generate and validate the labeled dataset used by the qtype fallback."""
import json
import random
from pathlib import Path

from nltk.featstruct import TYPE

from src.parsing import Parser, load_grammar
from src.preprocessing import normalize, tokenize
from src.semantic import SemanticInterpreter
from src.semantic.exceptions import InvalidSemanticError, UnsupportedSemanticError
from src.semantic.rules import SEMANTIC_RULES


_INTENT_ROOTS = {
    "GET_COURSE_INFO": "COURSE_QUERY",
    "GET_SCHEDULE": "SCHEDULE_QUERY",
    "GET_TOPIC": "TOPIC_QUERY",
    "GET_ASSIGNMENT": "ASSIGNMENT_QUERY",
    "GET_DEADLINE": "DEADLINE_QUERY",
    "GET_RESOURCE": "RESOURCE_QUERY",
    "GET_INSTRUCTOR": "INSTRUCTOR_QUERY",
    "CONTEXT_DEPENDENT": "CONTEXT_QUERY",
    "GET_RULE": "RULE_LO_REQUEST",
    "GET_LO": "RULE_LO_REQUEST",
}


class _DeadEnd(Exception):
    pass


def _expand(symbol, qtype, productions, rng, depth=0, budget=80):
    if isinstance(symbol, str):
        return [symbol]
    if depth > 20 or budget <= 0:
        raise _DeadEnd

    options = []
    for production in productions.get(symbol[TYPE], ()):
        rule_qtype = production.lhs().get("QTYPE")
        if isinstance(rule_qtype, str) and rule_qtype != qtype:
            continue
        options.append(production)
    rng.shuffle(options)

    for production in options:
        try:
            tokens = []
            for child in production.rhs():
                tokens.extend(_expand(child, qtype, productions, rng, depth + 1, budget - 1))
            return tokens
        except _DeadEnd:
            continue
    raise _DeadEnd


def generate_labeled_dataset(sample_count=1000, seed=42):
    """Generate unique, parser-validated samples balanced across supported qtypes."""
    if not isinstance(sample_count, int) or isinstance(sample_count, bool) or sample_count < len(SEMANTIC_RULES):
        raise ValueError(f"sample_count must be at least {len(SEMANTIC_RULES)}")

    grammar = load_grammar()
    parser = Parser(grammar)
    interpreter = SemanticInterpreter()
    productions = {}
    for production in grammar.productions():
        productions.setdefault(production.lhs()[TYPE], []).append(production)

    start_rules = productions.get("S", [])
    qtype_intents = {qtype: intent for intent, qtype in SEMANTIC_RULES}
    qtypes = sorted(qtype_intents)
    base_count, remainder = divmod(sample_count, len(qtypes))
    rng = random.Random(seed)
    samples = []

    for index, qtype in enumerate(qtypes):
        intent = qtype_intents[qtype]
        family = _INTENT_ROOTS[intent]
        roots = [
            production for production in start_rules
            if len(production.rhs()) > 1 and production.rhs()[1][TYPE] == family
        ]
        if not roots:
            raise ValueError(f"No grammar entry rule for {intent}/{qtype}")

        needed = base_count + (index < remainder)
        seen = set()
        max_attempts = max(1000, needed * 300)
        for _ in range(max_attempts):
            root = rng.choice(roots)
            try:
                tokens = []
                for child in root.rhs():
                    tokens.extend(_expand(child, qtype, productions, rng))
            except _DeadEnd:
                continue

            sentence = " ".join(tokens)
            if sentence in seen:
                continue
            trees = parser.parse_all(tokenize(normalize(sentence)))
            if not trees:
                continue

            labels = set()
            for tree in trees:
                try:
                    frame = interpreter.interpret(tree)
                except (InvalidSemanticError, UnsupportedSemanticError):
                    continue
                labels.add((frame.predicate, frame.qtype))
            if labels != {(intent, qtype)}:
                continue
            seen.add(sentence)
            samples.append({
                "sentence": sentence,
                "intent": intent,
                "qtype": qtype,
                "source": "synthetic_fcfg",
            })
            if len(seen) == needed:
                break

        if len(seen) != needed:
            raise RuntimeError(
                f"Could only generate {len(seen)} of {needed} examples for {intent}/{qtype}"
            )

    rng.shuffle(samples)
    return samples


def load_labeled_dataset(path):
    """Load and validate a JSON list of sentence, intent, and qtype records."""
    with Path(path).open(encoding="utf-8") as file:
        records = json.load(file)
    if not isinstance(records, list) or not records:
        raise ValueError("Dataset must be a non-empty JSON list")

    mapping = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"Dataset row {index} must be an object")
        sentence, intent, qtype = (
            record.get("sentence"), record.get("intent"), record.get("qtype")
        )
        if not all(isinstance(value, str) and value.strip() for value in (sentence, intent, qtype)):
            raise ValueError(f"Dataset row {index} needs non-empty sentence, intent, and qtype")
        key = (intent, qtype)
        if key not in SEMANTIC_RULES:
            raise ValueError(f"Dataset row {index} has unsupported label {intent}/{qtype}")
        previous = mapping.setdefault(qtype, intent)
        if previous != intent:
            raise ValueError(f"qtype {qtype} maps to multiple intents")
    return records


def split_labeled_dataset(records, seed=42, test_size=0.15, validation_size=0.15):
    """Return deterministic, stratified train/validation/test partitions."""
    if not 0 < test_size < 1 or not 0 < validation_size < 1 or test_size + validation_size >= 1:
        raise ValueError("test_size and validation_size must be positive and sum to less than 1")

    from sklearn.model_selection import train_test_split

    labels = [record["qtype"] for record in records]
    counts = {label: labels.count(label) for label in set(labels)}
    if not counts or min(counts.values()) < 3:
        raise ValueError("Each qtype needs at least three examples for stratified splitting")

    train_validation, test = train_test_split(
        records, test_size=test_size, random_state=seed, stratify=labels
    )
    train_labels = [record["qtype"] for record in train_validation]
    validation_fraction = validation_size / (1 - test_size)
    train, validation = train_test_split(
        train_validation,
        test_size=validation_fraction,
        random_state=seed,
        stratify=train_labels,
    )
    return {"train": train, "validation": validation, "test": test}


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")
