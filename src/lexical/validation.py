"""Validate lexical schema independently of file format and NLTK."""
import re

from src.preprocessing import normalize, tokenize

from .exceptions import LexiconError
from .models import Entry


def validate_entries(data):
    if not isinstance(data, dict) or not data or set(data) - {"lexical_entries", "entity_entries"}:
        raise LexiconError("Lexicon must contain lexical_entries and/or entity_entries")
    entries = []
    seen = set()
    for group in ("lexical_entries", "entity_entries"):
        rows = data.get(group, [])
        if not isinstance(rows, list):
            raise LexiconError(f"{group} must be a list")
        for row in rows:
            if not isinstance(row, dict):
                raise LexiconError("Each lexicon entry must be a mapping")
            allowed = {"category", "aliases"}
            if group == "entity_entries":
                allowed |= {"canonical_id", "entity_type"}
            if set(row) - allowed:
                raise LexiconError(f"Unknown entry fields: {set(row) - allowed}")
            category = row.get("category", "")
            if not isinstance(category, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", category):
                raise LexiconError("Invalid grammar category")
            entity_id = row.get("canonical_id")
            entity_type = row.get("entity_type")
            if group == "entity_entries" and not all(isinstance(v, str) and v for v in (entity_id, entity_type)):
                raise LexiconError("Entity entries require canonical_id and entity_type")
            if group == "entity_entries" and (
                not re.fullmatch(r"[A-Z][A-Z0-9_.-]*", entity_id)
                or not entity_type.strip()
            ):
                raise LexiconError("Invalid canonical_id or empty entity_type")
            if group == "lexical_entries" and (entity_id is not None or entity_type is not None):
                raise LexiconError("Lexical entries cannot define entity identity")
            aliases = row.get("aliases")
            if not isinstance(aliases, list) or not aliases or not all(isinstance(a, str) for a in aliases):
                raise LexiconError("aliases must be a nonempty list of strings")
            aliases = tuple(dict.fromkeys(normalize(a) for a in aliases))
            if any(not alias for alias in aliases):
                raise LexiconError("Empty normalized alias")
            # NLTK's textual grammar reader does not decode Python string
            # escapes; a backslash can silently change on a text round trip.
            if any("\\" in token or ("'" in token and '"' in token)
                   for alias in aliases for token in tokenize(alias)):
                raise LexiconError("Alias token cannot be represented safely in FCFG text")
            key = (category, entity_id)
            if key in seen:
                raise LexiconError(f"Duplicate entry: {key}; merge its aliases")
            seen.add(key)
            entries.append(Entry(category, aliases, entity_id, entity_type))
    return entries
