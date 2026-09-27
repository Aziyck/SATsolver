from __future__ import annotations

from typing import Protocol

from sat_core.models import ProblemInstance


class ProblemBuilder(Protocol):
    name: str

    def build(self) -> ProblemInstance:
        ...
