"""Feature chart parsing, independent of input/output and semantic interpretation."""
from nltk.parse import FeatureChartParser

from .exceptions import AmbiguousParseError
from .grammar_loader import load_grammar


class Parser:
    def __init__(self, grammar=None, parser_type = FeatureChartParser):
        self.grammar = grammar if grammar is not None else load_grammar()
        self.parser = parser_type(self.grammar)

    def parse_all(self, tokens: list[str]):
        """
        Parse all the tokens.
        :args:
        @tokens: list of tokens
        :return: List of ntlk Tree
        """
        tokens = list(tokens)
        try:
            self.grammar.check_coverage(tokens)
        except ValueError:
            return []  # Normal no-match result; grammar coverage is not a system failure.
        return list(self.parser.parse(tokens))

    def parse(self, tokens: list[str]):
        """
        Parse all and check ambigious parse
        """        
        trees = self.parse_all(tokens)
        if len(trees) > 1:
            raise AmbiguousParseError("Multiple parses: use parse_all and compare semantics")
        return trees[0] if trees else None

