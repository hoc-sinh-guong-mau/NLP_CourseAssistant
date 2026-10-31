"""Apply semantic schemas to a feature-based parse tree."""
from copy import deepcopy

from .exceptions import InvalidSemanticError, UnsupportedSemanticError
from .features import read_source, require_feature
from .models import SemanticFrame
from .rules import SEMANTIC_RULES


class SemanticInterpreter:
    def __init__(self, rules=None):
        # Configuring one interpreter must not mutate another or the defaults.
        self.rules = deepcopy(SEMANTIC_RULES if rules is None else rules)

    def interpret(self, tree) -> SemanticFrame:
        """
        collect Predicate, intent

        :args:
        @tree: ntlk tree

        :args:
        return SemanticFrame
        """
        
        features = tree.label()
        intent: str = require_feature(features, 'INTENT')
        qtype: str = require_feature(features, 'QTYPE')
        rule = self.rules.get((intent, qtype))
        if rule is None:
            raise UnsupportedSemanticError(f'Unsupported semantic mapping: {intent}/{qtype}')
        arguments = {}
        
        for slot, source in rule.slots.items():
            if isinstance(source, tuple):
                arguments[slot] = [read_source(tree, item) for item in source]
            else:
                arguments[slot] = read_source(tree, source)
                
        for slot, source in rule.optional_slots.items():
            # Only absent/NONE are optional; unbound variables are errors.
            if features.get(source) is not None and features.get(source) != 'NONE':
                arguments[slot] = read_source(tree, source)
                
        return SemanticFrame(intent, arguments, qtype)

