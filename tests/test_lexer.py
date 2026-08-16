"""Tests for the E++ lexer."""

import pytest
from epp.lexer import lex
from epp.tokens import TokenKind
from epp.errors import EppLexError


def kinds(tokens):
    return [t.kind for t in tokens if t.kind != TokenKind.EOF]


def values(tokens):
    return [t.value for t in tokens if t.kind != TokenKind.EOF]


class TestLexerBasics:
    def test_empty_source(self):
        tokens = lex("")
        assert len(tokens) == 1
        assert tokens[0].kind == TokenKind.EOF

    def test_single_word(self):
        tokens = lex("Hello")
        assert kinds(tokens) == [TokenKind.WORD]
        assert values(tokens) == ["Hello"]

    def test_multiple_words(self):
        tokens = lex("Let x be 5")
        assert kinds(tokens) == [TokenKind.WORD, TokenKind.WORD, TokenKind.WORD, TokenKind.NUMBER]

    def test_comma_and_period(self):
        tokens = lex("If yes, Say hello.")
        assert kinds(tokens) == [
            TokenKind.WORD, TokenKind.WORD, TokenKind.COMMA,
            TokenKind.WORD, TokenKind.WORD, TokenKind.PERIOD,
        ]

    def test_numbers(self):
        tokens = lex("42 100 7")
        assert values(tokens) == ["42", "100", "7"]
        assert all(t.kind == TokenKind.NUMBER for t in tokens[:-1])

    def test_line_tracking(self):
        tokens = lex("Hello\nWorld")
        assert tokens[0].line == 1
        assert tokens[1].line == 2

    def test_multiline(self):
        tokens = lex("Let x be 5.\nSay hello.")
        lines = [t.line for t in tokens if t.kind != TokenKind.EOF]
        assert lines == [1, 1, 1, 1, 1, 2, 2, 2]


class TestLexerEdgeCases:
    def test_apostrophe_in_word(self):
        tokens = lex("don't")
        assert kinds(tokens) == [TokenKind.WORD]
        assert values(tokens) == ["don't"]

    def test_tabs_and_spaces_ignored(self):
        tokens = lex("  Let\t x  ")
        assert kinds(tokens) == [TokenKind.WORD, TokenKind.WORD]

    def test_illegal_character(self):
        with pytest.raises(EppLexError) as exc_info:
            lex("Let x = 5")
        assert "unexpected character" in str(exc_info.value)
        assert "line 1" in str(exc_info.value)

    def test_illegal_character_various(self):
        for ch in ['@', '$', '!', '{', '}', '(', ')', '+', '-', '=', '"']:
            with pytest.raises(EppLexError):
                lex(f"Hello {ch} world")
