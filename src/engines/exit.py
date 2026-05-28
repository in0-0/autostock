from __future__ import annotations

from src.models import Candidate, ExitSignal


class ExitEngine:
    def evaluate(self, candidate: Candidate, technical_context: dict | None = None) -> ExitSignal:
        if candidate.peg > 1.5:
            return ExitSignal.REDUCE
        if 1.2 < candidate.peg <= 1.5:
            return ExitSignal.WARNING
        return ExitSignal.NONE
