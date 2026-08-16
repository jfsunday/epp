"""Lexer for E++. Turns source code into a flat list of tokens.

Only produces WORD, NUMBER, COMMA, PERIOD, and EOF tokens.
All alphabetic runs become WORD tokens; the parser decides keyword-ness.
"""

from .tokens import Token, TokenKind
from .errors import EppLexError


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
            tokens.append(Token(TokenKind.WORD, source[start:i], line))
            continue

        # Illegal character
        raise EppLexError(f"unexpected character {ch!r}", line)

    tokens.append(Token(TokenKind.EOF, '', line))
    return tokens
