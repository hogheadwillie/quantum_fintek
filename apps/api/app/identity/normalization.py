"""Normalization helpers for identity input."""


def normalize_email(email: str) -> str:
    """Return the canonical email form stored and queried by identity services."""
    normalized = email.strip().casefold()
    if not normalized:
        msg = "email must not be empty"
        raise ValueError(msg)
    return normalized
