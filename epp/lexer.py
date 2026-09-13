"""Lexer for E++. Turns source code into a flat list of tokens.

Only produces WORD, NUMBER, COMMA, PERIOD, and EOF tokens.
All alphabetic runs become WORD tokens; the parser decides keyword-ness.
"""

from .tokens import Token, TokenKind
from .errors import EppLexError


_MAX_EXTENSION_LEN = 5


def _file_extension_end(source: str, i: int) -> int | None:
    """If a file extension starts at i, return the index just past it.

    A file extension is a dot immediately followed by one to five lowercase
    letters or digits, e.g. the ".png" in "bird.png". Sentence-ending periods
    never match because E++ statements start with a capital letter.
    """
    end = None
    while i < len(source) and source[i] == '.':
        j = i + 1
        while j < len(source) and (source[j].islower() or source[j].isdigit()):
            j += 1
        if j == i + 1 or j - i - 1 > _MAX_EXTENSION_LEN:
            break
        end = i = j
    return end


def lex(source: str) -> list[Token]:
    """Tokenize E++ source code into a list of Tokens."""
    tokens: list[Token] = []
    i = 0
    line = 1
    length = len(source)

    while i < length:
        ch = source[i]

        # Newlines
        if ch == '\n':
            line += 1
            i += 1
            continue

        # Whitespace (non-newline)
        if ch in (' ', '\t', '\r'):
            i += 1
            continue

        # Comments: lines starting with "Note" are handled by the parser,
        # but we still need to lex them as normal tokens.

        # Comma
        if ch == ',':
            tokens.append(Token(TokenKind.COMMA, ',', line))
            i += 1
            continue

        # Period
        if ch == '.':
            # Check it's not part of a number (handled below)
            tokens.append(Token(TokenKind.PERIOD, '.', line))
            i += 1
            continue

        # Number: digits (the word "point" handles decimals at parse level)
        if ch.isdigit():
            start = i
            while i < length and source[i].isdigit():
                i += 1
            tokens.append(Token(TokenKind.NUMBER, source[start:i], line))
            continue

        # Hex color code: #abc123
        if ch == '#':
            start = i
            i += 1
            while i < length and (source[i].isalnum()):
                i += 1
            tokens.append(Token(TokenKind.WORD, source[start:i], line))
            continue

        # Word: alphabetic characters and apostrophes (for contractions like "don't")
        if ch.isalpha() or ch == "'":
            start = i
            while i < length and (source[i].isalpha() or source[i] == "'"):
                i += 1
            end = _file_extension_end(source, i)
            if end is not None:
                i = end
            tokens.append(Token(TokenKind.WORD, source[start:i], line))
            continue

        # Illegal character
        raise EppLexError(f"unexpected character {ch!r}", line)

    tokens.append(Token(TokenKind.EOF, '', line))
    return tokens
