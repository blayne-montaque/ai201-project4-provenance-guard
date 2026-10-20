"""Common signal contract; detection implementations stay independently testable."""
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Signal:
    name: str
    score: float | None
    available: bool = True
    insufficient_evidence: bool = False
    diagnostics: dict = field(default_factory=dict)

    def public(self):
        return asdict(self)

