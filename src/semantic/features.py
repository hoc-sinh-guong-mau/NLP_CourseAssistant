"""Read bound root/subtree features without interpreting query semantics."""
from nltk.featstruct import TYPE

from .exceptions import InvalidSemanticError


def require_feature(features, name):
    value = features.get(name)
    if not isinstance(value, str) or not value.strip() or value == 'NONE':
        raise InvalidSemanticError(f'Missing or unresolved feature: {name}')
    return value


def read_source(tree, source):
    if '.' not in source:
        return require_feature(tree.label(), source)
    category, feature = source.split('.', 1)
    nodes = list(tree.subtrees(lambda node: node.label().get(TYPE) == category))
    values = {require_feature(node.label(), feature) for node in nodes}
    if len(values) != 1:
        raise InvalidSemanticError(f'Missing or ambiguous subtree source: {source}')
    return values.pop()
