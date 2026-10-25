from nltk.parse import FeatureChartParser
from nltk.grammar import FeatureGrammar
from nltk.featstruct import TYPE
from src.config import GRAMMAR_PATH, LEXICON_DIR
from src.lexical import Lexicon


def grammar_text():
    syntax = GRAMMAR_PATH.read_text(encoding="utf-8")
    text = syntax + "\n# Generated lexical productions; edit data/lexicon/*.yaml.\n" + Lexicon.load(LEXICON_DIR).grammar_text()
    validate_grammar(text)
    return text


def validate_grammar(text):
    grammar = FeatureGrammar.fromstring(text)
    defined = {p.lhs()[TYPE] for p in grammar.productions()}
    referenced = {symbol[TYPE] for p in grammar.productions()
                  for symbol in p.rhs() if not isinstance(symbol, str)}
    missing = (referenced | {grammar.start()[TYPE]}) - defined
    if missing:
        raise ValueError(f"Undefined grammar categories: {sorted(missing)}")
    return grammar


def load_grammar():
    return validate_grammar(grammar_text())


class Parser:
    def __init__(self, grammar=None):
        self.grammar = grammar if grammar is not None else load_grammar()
        self.parser = FeatureChartParser(self.grammar)

    def parse_all(self, tokens):
        try:
            return list(self.parser.parse(tokens))
        except ValueError:
            return []

    def parse(self, tokens):
        trees = self.parse_all(tokens)
        if len(trees) > 1:
            raise ValueError("Multiple parses: use parse_all and compare semantics")
        return trees[0] if trees else None
