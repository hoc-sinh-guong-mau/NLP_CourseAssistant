"""Feature chart parsing, independent of input/output and semantic interpretation."""
from nltk.parse import FeatureChartParser

# Re-export helpers to preserve the existing parser module API.
from .grammar_loader import grammar_text, load_grammar, validate_grammar

class ParseError(ValueError):
    """Raised when parsing fails due to a grammar coverage issue."""
    pass


class Parser:
    def __init__(self, grammar=None):
        self.grammar = grammar if grammar is not None else load_grammar()
        self.parser = FeatureChartParser(self.grammar)

    def parse_all(self, tokens):
        tokens = list(tokens)
        try:
            self.grammar.check_coverage(tokens)
        except ValueError:
            raise ParseError("Tokens are not covered by the grammar")
        return list(self.parser.parse(tokens))

    def parse(self, tokens):
        trees = self.parse_all(tokens)
        if len(trees) > 1:
            raise ParseError("Multiple parses: use parse_all and compare semantics")
        return trees[0] if trees else None

