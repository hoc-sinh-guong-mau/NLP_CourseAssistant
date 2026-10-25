"""Validated domain lexicon and generation of FCFG lexical productions."""
import re
from dataclasses import dataclass
from pathlib import Path
import yaml

from nltk.grammar import FeatureGrammar, Production
from nltk.grammar import FeatStructNonterminal
from nltk.featstruct import TYPE
from ..preprocessing.preprocessor import normalize, tokenize


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys instead of silently discarding data."""


def _unique_mapping(loader, node):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str):
            raise ValueError("YAML mapping keys must be strings")
        if key in mapping:
            raise ValueError(f"Duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping
)


@dataclass(frozen=True)
class Entry:
    category: str
    aliases: tuple[str, ...]
    canonical_id: str | None = None
    entity_type: str | None = None


class Lexicon:
    def __init__(self, data):
        if not isinstance(data, dict) or not data or set(data) - {"lexical_entries", "entity_entries"}:
            raise ValueError("Lexicon must contain lexical_entries and/or entity_entries")
        self.entries = []
        seen = set()
        for group in ("lexical_entries", "entity_entries"):
            rows = data.get(group, [])
            if not isinstance(rows, list):
                raise ValueError(f"{group} must be a list")
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError("Each lexicon entry must be a mapping")
                allowed = {"category", "aliases"}
                if group == "entity_entries":
                    allowed |= {"canonical_id", "entity_type"}
                if set(row) - allowed:
                    raise ValueError(f"Unknown entry fields: {set(row) - allowed}")
                category = row.get("category", "")
                if not isinstance(category, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", category):
                    raise ValueError("Invalid grammar category")
                entity_id = row.get("canonical_id")
                entity_type = row.get("entity_type")
                if group == "entity_entries" and not all(isinstance(v, str) and v for v in (entity_id, entity_type)):
                    raise ValueError("Entity entries require canonical_id and entity_type")
                if group == "entity_entries" and (
                    not re.fullmatch(r"[A-Z][A-Z0-9_.-]*", entity_id)
                    or not entity_type.strip()
                ):
                    raise ValueError("Invalid canonical_id or empty entity_type")
                if group == "lexical_entries" and (entity_id is not None or entity_type is not None):
                    raise ValueError("Lexical entries cannot define entity identity")
                aliases = row.get("aliases")
                if not isinstance(aliases, list) or not aliases or not all(isinstance(a, str) for a in aliases):
                    raise ValueError("aliases must be a nonempty list of strings")
                aliases = tuple(dict.fromkeys(normalize(a) for a in aliases))
                if any(not alias for alias in aliases):
                    raise ValueError("Empty normalized alias")
                # NLTK's textual grammar reader does not decode Python string
                # escapes; a backslash can silently change on a text round trip.
                if any("\\" in token or ("'" in token and '"' in token)
                       for alias in aliases for token in tokenize(alias)):
                    raise ValueError("Alias token cannot be represented safely in FCFG text")
                key = (category, entity_id)
                if key in seen:
                    raise ValueError(f"Duplicate entry: {key}; merge its aliases")
                seen.add(key)
                self.entries.append(Entry(category, aliases, entity_id, entity_type))

    @classmethod
    def load(cls, path: Path):
        path = Path(path)
        if path.is_dir():
            paths = sorted([*path.glob("*.yaml"), *path.glob("*.yml")])
            if not paths:
                raise ValueError(f"No YAML lexicon files in {path}")
        else:
            paths = [path]
        merged = {"lexical_entries": [], "entity_entries": []}
        for file in paths:
            try:
                data = yaml.load(file.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
                validated = cls(data)
            except (ValueError, yaml.YAMLError) as exc:
                raise ValueError(f"Invalid lexicon {file}: {exc}") from exc
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
