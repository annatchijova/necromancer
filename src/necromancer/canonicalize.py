"""Canonical, typed, versioned serialization and SHA-256 sealing.

Single source of truth for every sealed byte in NECROMANCER. No float may
enter the sealed path: ratios use fractions.Fraction and are encoded as
exact numerator/denominator pairs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from fractions import Fraction
from typing import Any, Callable

CANONICALIZE_VERSION = 1


def _encode(obj: Any) -> Any:
    if obj is None:
        return ["null"]
    if isinstance(obj, bool):
        return ["bool", obj]
    if isinstance(obj, int):
        return ["int", obj]
    if isinstance(obj, Fraction):
        return ["fraction", obj.numerator, obj.denominator]
    if isinstance(obj, float):
        raise TypeError("float is forbidden in the sealed path; use Fraction")
    if isinstance(obj, str):
        return ["str", obj]
    if isinstance(obj, datetime):
        return ["datetime", obj.isoformat()]
    if isinstance(obj, Enum):
        return ["enum", type(obj).__name__, obj.value]
    if isinstance(obj, dict):
        for key in obj:
            if not isinstance(key, str):
                raise TypeError("sealed dict keys must be str")
        return ["dict", [[key, _encode(obj[key])] for key in sorted(obj)]]
    if isinstance(obj, (list, tuple)):
        return ["list", [_encode(item) for item in obj]]
    if isinstance(obj, (set, frozenset)):
        encoded = [_encode(item) for item in obj]
        encoded.sort(key=lambda item: json.dumps(item, sort_keys=True))
        return ["set", encoded]
    raise TypeError(f"cannot canonically encode {type(obj).__name__}")


def canonical_bytes(payload: Any) -> bytes:
    """Return the canonical bytes for a payload, stamped with the version."""
    wrapped = {"v": CANONICALIZE_VERSION, "data": _encode(payload)}
    text = json.dumps(wrapped, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")


def canonical_text(payload: Any) -> str:
    return canonical_bytes(payload).decode("utf-8")


def seal(payload: Any) -> str:
    """SHA-256 over the canonical bytes of the payload."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def verify_seal(payload: Any, expected: str) -> bool:
    return seal(payload) == expected


def check_deterministic(factory: Callable[[], Any], runs: int = 3) -> str:
    """Seal the factory output repeatedly; raise on the first divergence."""
    seals = [seal(factory()) for _ in range(runs)]
    if any(item != seals[0] for item in seals):
        raise AssertionError(f"non-deterministic output, seals diverge: {seals}")
    return seals[0]
