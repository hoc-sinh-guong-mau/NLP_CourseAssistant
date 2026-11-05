"""Extract canonical lexicon entities for statistical intent predictions."""
from dataclasses import dataclass
from typing import Mapping

from src.lexical import Lexicon
from src.preprocessing import normalize, tokenize


FeatureSource = str | tuple[str, ...]


_SLOT_CATEGORIES = {
    "assignment_id": ("ASSIGNMENT_NAME",),
    "assessment_item_id": ("ASSESSMENT_ITEM",),
    "chapter_id": ("CHAPTER",),
    "component_id": ("ASSIGNMENT_COMPONENT",),
    "course_id": ("COURSE",),
    "course_part_id": ("COURSE_PART",),
    "exam_id": ("EXAM",),
    "learning_outcome_id": ("LO_ID",),
    "part_id": ("PART",),
    "resource_category_id": ("RESOURCE_TOPIC",),
    "resource_id": ("RESOURCE_TITLE",),
    "rule_id": ("RULE_SUBJECT", "USE_SUBJECT", "OBLIGATION_ACTION"),
    "topic_id": ("TOPIC",),
    "topic_ids": ("TOPIC",),
    "week_id": ("WEEK",),
}


@dataclass(frozen=True)
class _Match:
    start: int
    end: int
    canonical_id: str


class EntityExtractor:
    """Resolve semantic argument slots from normalized lexicon aliases."""

    def __init__(self, lexicon: Lexicon):
        self._aliases = tuple(
            (entry.category, tuple(tokenize(alias)), entry.canonical_id)
            for entry in lexicon.entries
            if entry.canonical_id is not None
            for alias in entry.aliases
        )

    def extract(
        self,
        text: str,
        slots: Mapping[str, FeatureSource],
        optional_slots: dict[str, str] | None = None,
    ) -> dict[str, object] | None:
        """Return required and present optional entity slots, or None if unresolved."""
        tokens = tokenize(normalize(text))
        arguments: dict[str, object] = {}

        for slot in slots:
            categories = _SLOT_CATEGORIES.get(slot)
            if slot == "context_ref":
                arguments[slot] = "CONTEXT_REF"
                continue
            if categories is None:
                return None

            matches = self._find(tokens, categories)
            if slot == "topic_ids":
                ids = list(dict.fromkeys(match.canonical_id for match in matches))
                if len(ids) < 2:
                    return None
                arguments[slot] = ids
            elif len({match.canonical_id for match in matches}) == 1:
                arguments[slot] = matches[0].canonical_id
            else:
                return None

        for slot in (optional_slots or {}):
            categories = _SLOT_CATEGORIES.get(slot)
            if categories is None:
                continue
            matches = self._find(tokens, categories)
            ids = {match.canonical_id for match in matches}
            if len(ids) == 1:
                arguments[slot] = ids.pop()

        return arguments

    def _find(self, tokens: list[str], categories: tuple[str, ...]) -> list[_Match]:
        candidates = []
        for category, alias, canonical_id in self._aliases:
            if category not in categories:
                continue
            width = len(alias)
            candidates.extend(
                _Match(start, start + width, canonical_id)
                for start in range(len(tokens) - width + 1)
                if tuple(tokens[start:start + width]) == alias
            )

        # Prefer the longest alias at a given position and avoid counting an
        # alias nested inside a longer entity name as a separate entity.
        candidates.sort(key=lambda match: (match.start, -(match.end - match.start), match.canonical_id))
        selected = []
        occupied_until = -1
        index = 0
        while index < len(candidates):
            start = candidates[index].start
            same_start = []
            while index < len(candidates) and candidates[index].start == start:
                same_start.append(candidates[index])
                index += 1
            if start < occupied_until:
                continue
            longest_end = max(match.end for match in same_start)
            selected.extend(
                match for match in same_start
                if match.end == longest_end
            )
            occupied_until = longest_end
        return selected
