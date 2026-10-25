"""Exact normalized lookup for inspection; never replaces tokens before parsing."""
from ..preprocessing.preprocessor import normalize


class EntityResolver:
    def __init__(self, lexicon):
        self.lexicon = lexicon

    def lookup_alias(self, text, category=None):
        alias = normalize(text)
        return [entry for entry in self.lexicon.entries
                if entry.canonical_id is not None
                and (category is None or entry.category == category)
                and alias in entry.aliases]

    def get_entity(self, canonical_id):
        # The same ID can participate in multiple grammar categories.
        return [e for e in self.lexicon.entries if e.canonical_id == canonical_id]

    def collisions(self):
        index = {}
        for entry in self.lexicon.entries:
            if entry.canonical_id is not None:
                for alias in entry.aliases:
                    index.setdefault((entry.category, alias), set()).add(entry.canonical_id)
        return {key: sorted(ids) for key, ids in index.items() if len(ids) > 1}
