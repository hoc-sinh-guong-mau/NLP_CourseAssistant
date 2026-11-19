"""Compose grammar fragments and lexical productions; validate FCFG references."""
from pathlib import Path

from nltk.grammar import FeatureGrammar
from nltk.featstruct import TYPE

from src.common.files import read_text
from src.config import GRAMMAR_PATH, LEXICON_DIR
from src.lexical import Lexicon

from .exceptions import GrammarError


def load_syntax(path=GRAMMAR_PATH) -> str:    
    """
    Load the entry grammar and its sibling rules directory deterministically.

    :args:
    @path: grammar path
    :return:
    sentences: type
    """
    path = Path(path)
    fragments = sorted((path.parent / "rules").glob("*.fcfg"))
    parts = [read_text(path, GrammarError)]
    for fragment in fragments:
        text = read_text(fragment, GrammarError)
        if any(line.strip().startswith("% start") for line in text.splitlines()):
            raise GrammarError(f"Only syntax.fcfg may declare a start symbol: {fragment}")
        parts.append(f"# Source: rules/{fragment.name}\n{text}")
    return "\n".join(parts)


def _compose_grammar(grammar_path=None, lexicon_dir=None) -> str:
    """Compose syntax and lexical productions; callers validate exactly once."""
    
    syntax = load_syntax(GRAMMAR_PATH if grammar_path is None else grammar_path)
    text = syntax + "\n# Generated lexical productions; edit models/lexicon/*.yaml.\n" + Lexicon.load(LEXICON_DIR if lexicon_dir is None else lexicon_dir).grammar_text()
    return text


def grammar_text(grammar_path=None, lexicon_dir=None) -> str:
    text = _compose_grammar(grammar_path, lexicon_dir)
    validate_grammar(text)
    return text


def validate_grammar(text: str) -> FeatureGrammar:
    """
    Try to read grammar using FeatureGrammar.
    (Checks whether nonterminal categories exist.)

    Args:
    @text: str: loaded grammar text
    Return:
    -> Feature Grammar (NLTK FeatureGrammar object)
    """
    try:
        grammar = FeatureGrammar.fromstring(text)
    except ValueError as exc:
        raise GrammarError("Invalid FCFG syntax", context={"reason": str(exc)}) from exc
    multiword = {symbol for production in grammar.productions() for symbol in production.rhs()
                 if isinstance(symbol, str) and any(char.isspace() for char in symbol)}
    if multiword:
        raise GrammarError("Split multiword terminals to match whitespace tokenization",
                           context={"terminals": sorted(multiword)})
    defined = {p.lhs()[TYPE] for p in grammar.productions()}
    referenced = {symbol[TYPE] for p in grammar.productions()
                  for symbol in p.rhs() if not isinstance(symbol, str)}
    missing = (referenced | {grammar.start()[TYPE]}) - defined
    if missing:
        raise GrammarError(f"Undefined grammar categories: {sorted(missing)}")
    return grammar


def load_grammar(grammar_path=None, lexicon_dir=None):
    """
    Wrapper of validate grammar
    """
    return validate_grammar(_compose_grammar(grammar_path, lexicon_dir))

