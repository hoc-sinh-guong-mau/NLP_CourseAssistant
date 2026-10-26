"""Domain errors raised during semantic interpretation."""

class UnsupportedSemanticError(ValueError):
    """A parsed request has no registered semantic schema."""


class InvalidSemanticError(ValueError):
    """A schema requires features that are missing, ambiguous or unbound."""
