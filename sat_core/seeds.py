"""
Deterministic seeding helpers.

Random instances are generated from a Random object seeded with a string that
combines every parameter that shapes the instance, for example
("gnp", nodes, p, seed). Two consequences:

- the same parameters and seed always give the same instance, in the Solve
  page and in benchmarks alike, so any benchmark row can be reproduced;
- different parameters with the same seed give independent instances.

Python seeds str inputs through SHA-512, so this is stable across runs,
machines and PYTHONHASHSEED values.
"""

from __future__ import annotations

import hashlib
import random
import secrets
from typing import Any


SEED_LIMIT = 2**31


def seed_text(*parts: Any) -> str:
    return "|".join(repr(part) for part in parts)


def rng_for(*parts: Any) -> random.Random:
    return random.Random(seed_text(*parts))


def derive_seed(*parts: Any) -> int:
    digest = hashlib.sha256(seed_text(*parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % SEED_LIMIT


def fresh_seed() -> int:
    return secrets.randbelow(SEED_LIMIT)


def repeat_seed(seed: int, repeat: int) -> int:
    """Seed for benchmark repeat r; repeat 1 keeps the seed the user typed."""

    if repeat <= 1:
        return seed
    return derive_seed("repeat", seed, repeat)
