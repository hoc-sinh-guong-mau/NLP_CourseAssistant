"""Declarative query contracts; no SQL or executable expressions."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ConditionSpec:
    field: str
    operator: str
    slot: str


@dataclass(frozen=True)
class QuerySpec:
    collection: str
    filters: tuple[tuple[str, str], ...]  # (KB field, semantic argument) # equality_clause
    select: tuple[str, ...]
    conditions: tuple[ConditionSpec, ...] = () # membership_clause
    constants: tuple[tuple[str, str], ...] = ()
    optional_context: tuple[str, ...] = ()
    required_context: tuple[str, ...] = ()
