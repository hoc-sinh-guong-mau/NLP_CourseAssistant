"""Conservative lexical evidence checks for model predictions, not an OOD classifier."""

import math
import re
import unicodedata

from src.preprocessing import normalize, tokenize

from .fallback_rules import QTYPE_CUES, REFERENCE_CUES


def _fold(tokens):
    # Accent-insensitive cue evidence tolerates a mistyped accent, without
    # rewriting entity IDs or introducing fuzzy entity matching.
    return tuple(
        "".join(
            c
            for c in unicodedata.normalize("NFD", word)
            if not unicodedata.combining(c)
        ).replace("đ", "d")
        for word in tokens
    )


def _phrases(cues):
    return tuple(_fold(tokenize(normalize(cue))) for cue in cues)


def _contains(tokens, phrases):
    return any(
        tokens[start : start + len(phrase)] == phrase
        for phrase in phrases
        for start in range(len(tokens) - len(phrase) + 1)
    )


def has_context_reference(text):
    tokens = _fold(tokenize(normalize(text)))
    return any(_contains(tokens, _phrases(cues)) for cues in REFERENCE_CUES.values())


class FallbackPolicy:
    """Require positive question evidence and reject explicit unsupported courses."""

    def __init__(self, lexicon, *, minimum_confidence=0.0):
        if not math.isfinite(minimum_confidence) or not 0 <= minimum_confidence <= 1:
            raise ValueError("Fallback minimum confidence must be between 0 and 1")
        self.minimum_confidence = minimum_confidence
        aliases = {
            (tuple(tokenize(alias)), entry.canonical_id)
            for entry in lexicon.entries
            if entry.canonical_id is not None
            for alias in entry.aliases
        }
        self._entity_aliases = sorted(aliases, key=lambda item: -len(item[0]))
        self._course_names = {
            tuple(tokenize(alias.removeprefix("môn ")))
            for entry in lexicon.entries
            if entry.category == "COURSE"
            for alias in entry.aliases
        }
        self._course_codes = {
            entry.canonical_id.casefold()
            for entry in lexicon.entries
            if entry.category == "COURSE"
        }
        self._cues = {qtype: _phrases(cues) for qtype, cues in QTYPE_CUES.items()}
        self._references = {
            qtype: _phrases(cues) for qtype, cues in REFERENCE_CUES.items()
        }

    def _other_course(self, tokens):
        if any(
            re.fullmatch(r"co\d{4}", token) and token not in self._course_codes
            for token in tokens
        ):
            return True
        generic = {
            "có",
            "là",
            "cần",
            "phải",
            "được",
            "kéo",
            "gồm",
            "bao",
            "mấy",
            "này",
            "đó",
            "ấy",
            "vừa",
            "đang",
            "nào",
            "gì",
            "của",
            "với",
            "về",
            "trong",
        }
        for start, token in enumerate(tokens):
            if token != "môn":
                continue
            tail = tokens[start + 1 :]
            if tail and tail[0] == "học":
                tail = tail[1:]
            if not tail or tail[0] in generic:
                continue
            if not any(tail[: len(name)] == name for name in self._course_names):
                return True
        return False

    def _question_tokens(self, tokens, arguments):
        entity_ids = {
            entity
            for value in arguments.values()
            for entity in (value if isinstance(value, list) else [value])
        }
        result = list(tokens)
        occupied = set()
        for alias, canonical_id in self._entity_aliases:
            if canonical_id not in entity_ids:
                continue
            for start in range(len(tokens) - len(alias) + 1):
                end = start + len(alias)
                if tuple(tokens[start:end]) == alias and not occupied.intersection(
                    range(start, end)
                ):
                    occupied.update(range(start, end))
                    result[start:end] = ["<entity>"] * len(alias)
        return _fold(result)

    def prediction_rejection(self, text, qtype, confidence):
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence)
            or not 0 < confidence <= 1
        ):
            return "invalid_confidence"
        if confidence < self.minimum_confidence:
            return "low_confidence"
        tokens = tuple(tokenize(normalize(text)))
        if self._other_course(tokens):
            return "unsupported_course"
        if qtype not in self._cues:
            return "unsupported_qtype"
        if qtype in self._references and not _contains(
            _fold(tokens), self._references[qtype]
        ):
            return "missing_reference"
        return None

    def arguments_rejection(self, text, qtype, arguments):
        tokens = tuple(tokenize(normalize(text)))
        if not _contains(self._question_tokens(tokens, arguments), self._cues[qtype]):
            return "missing_qtype_evidence"
        return None
