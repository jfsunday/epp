"""Token types and Token dataclass for E++."""

from dataclasses import dataclass
from enum import Enum, auto


class TokenKind(Enum):
    WORD = auto()
    NUMBER = auto()
    COMMA = auto()
    PERIOD = auto()
    EOF = auto()


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    value: str
    line: int

    def __repr__(self) -> str:
        return f"Token({self.kind.name}, {self.value!r}, line={self.line})"
