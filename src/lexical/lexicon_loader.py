"""Load validated domain entries and generate FCFG lexical productions."""
from pathlib import Path
import yaml
from nltk.grammar import FeatureGrammar, Production, FeatStructNonterminal
from nltk.featstruct import TYPE
from src.preprocessing.preprocessor import tokenize
from .models import Entry
from .validation import validate_entries
from .yaml_reader import UniqueKeyLoader

class LexiconError(ValueError):
    """Raised when lexicon validation fails."""
    pass

class Lexicon:
    def __init__(self, data):
        self.entries = tuple(validate_entries(data))

    @classmethod
    def load(cls, path: Path):
        path = Path(path)
        if path.is_dir():
            paths = sorted([*path.glob("*.yaml"), *path.glob("*.yml")])
            if not paths:
                raise LexiconError(f"No YAML lexicon files in {path}")
        else:
            paths = [path]
        merged = {"lexical_entries": [], "entity_entries": []}
        for file in paths:
            try:
                data = yaml.load(file.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
                validated = cls(data)
            except (LexiconError, yaml.YAMLError) as exc:
                raise LexiconError(f"Invalid lexicon {file}: {exc}") from exc
            # Validation occurs again after merging to catch cross-file duplicates.
            for entry in validated.entries:
                row = {"category": entry.category, "aliases": list(entry.aliases)}
                group = "lexical_entries"
                if entry.canonical_id is not None:
                    row.update(canonical_id=entry.canonical_id, entity_type=entry.entity_type)
                    group = "entity_entries"
                merged[group].append(row)
        return cls(merged)

    def productions(self):
        for entry in self.entries:
            features = {TYPE: entry.category}
            if entry.canonical_id is not None:
                features["ENTITY"] = entry.canonical_id
            lhs = FeatStructNonterminal(features)
            for alias in entry.aliases:
                yield Production(lhs, tuple(tokenize(alias)))

    def grammar_text(self):
        return "\n".join(map(str, self.productions())) + "\n"

    def compile(self, syntax: str):
        # NLTK handles quoting feature values and terminals in production repr.
        return FeatureGrammar.fromstring(syntax + "\n" + self.grammar_text())
