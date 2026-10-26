"""Data contracts for semantic schemas and interpretation results."""
from dataclasses import asdict, dataclass, field
from typing import Any
import json

FeatureSource = str | tuple[str, ...]
RuleKey = tuple[str, str]


@dataclass
class SemanticFrame:
    predicate: str
    arguments: dict[str, Any]
    qtype: str

    def canonical_key(self) -> str:
        """Stable identity for frame deduplication, including list-valued slots."""
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class SemanticRule:
    slots: dict[str, FeatureSource]
    optional_slots: dict[str, str] = field(default_factory=dict)
