"""Error hierarchy for E++. All messages are plain English with line numbers."""


class EppError(Exception):
    """Base error for all E++ errors."""

    def __init__(self, message: str, line: int | None = None):
        self.line = line
        if line is not None:
            self.message = f"Problem on line {line}: {message}"
        else:
            self.message = message
        super().__init__(self.message)


class EppLexError(EppError):
    """Raised when the lexer encounters an illegal character."""
    pass


class EppParseError(EppError):
    """Raised when the parser encounters unexpected structure."""
    pass


class EppRuntimeError(EppError):
    """Raised during interpretation for runtime problems."""
    pass
