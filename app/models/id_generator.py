import itertools
from typing import Callable

_counters: dict[str, itertools.count] = {}

VALID_PREFIXES = {
    "CMP",
    "CRT",
    "TIR",
    "SG",
    "BKR",
    "PLG",
    "PAY",
    "REF",
    "CHB",
    "STL",
    "WTL",
}


def generate_id(prefix: str) -> str:
    """Generate a unique ID for a given prefix (e.g. CMP_1, CRT_1)."""
    prefix_key = prefix.upper().strip()
    if prefix_key not in _counters:
        _counters[prefix_key] = itertools.count(1)
    return f"{prefix_key}_{next(_counters[prefix_key])}"


def get_id_generator(prefix: str) -> Callable[[], str]:
    """Return a callable that generates a unique ID on each invocation.

    Used as the callable `default` parameter in SQLAlchemy mapped columns
    so that IDs are generated per new object rather than once at class definition.
    """
    def _callable() -> str:
        return generate_id(prefix)
    return _callable
