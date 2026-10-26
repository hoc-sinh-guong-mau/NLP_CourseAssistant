"""Compose grammar fragments and lexical productions; validate FCFG references."""
from pathlib import Path

from nltk.grammar import FeatureGrammar
from nltk.featstruct import TYPE

from src.common.files import read_text
from src.config import GRAMMAR_PATH, LEXICON_DIR
from src.lexical import Lexicon

from .exceptions import GrammarError


def load_syntax(path=GRAMMAR_PATH):
    """Load the entry grammar and its sibling rules directory deterministically."""
    path = Path(path)
    fragments = sorted((path.parent / "rules").glob("*.fcfg"))
    parts = [read_text(path, GrammarError)]
    for fragment in fragments:
        text = read_text(fragment, GrammarError)
        if any(line.strip().startswith("% start") for line in text.splitlines()):
            raise GrammarError(f"Only syntax.fcfg may declare a start symbol: {fragment}")
        parts.append(f"# Source: rules/{fragment.name}\n{text}")
    return "\n".join(parts)


def grammar_text(grammar_path=None, lexicon_dir=None):
    syntax = load_syntax(GRAMMAR_PATH if grammar_path is None else grammar_path)
    text = syntax + "\n# Generated lexical productions; edit data/lexicon/*.yaml.\n" + Lexicon.load(LEXICON_DIR if lexicon_dir is None else lexicon_dir).grammar_text()
    validate_grammar(text)
    return text


def validate_grammar(text):
    try:
        grammar = FeatureGrammar.fromstring(text)
    except ValueError as exc:
        raise GrammarError("Invalid FCFG syntax", context={"reason": str(exc)}) from exc
    defined = {p.lhs()[TYPE] for p in grammar.productions()}
    referenced = {symbol[TYPE] for p in grammar.productions()
                  for symbol in p.rhs() if not isinstance(symbol, str)}
    missing = (referenced | {grammar.start()[TYPE]}) - defined
    if missing:
        raise GrammarError(f"Undefined grammar categories: {sorted(missing)}")
    return grammar


def load_grammar(grammar_path=None, lexicon_dir=None):
    return validate_grammar(grammar_text(grammar_path, lexicon_dir))

