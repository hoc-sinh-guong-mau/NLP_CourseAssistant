"""Source-backed KB normalization and validation."""
from .builder import build_collections, normalize_kb
from .validation import validate_collections

__all__ = ['build_collections', 'normalize_kb', 'validate_collections']
