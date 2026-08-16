"""Tests for plain-English error messages with line numbers."""

import pytest
from epp.errors import EppLexError, EppParseError, EppRuntimeError


class TestLexErrors:
    def test_illegal_char_message(self, run):
        with pytest.raises(EppLexError) as exc_info:
            run("Let x = 5.")
        assert "line 1" in str(exc_info.value)
        assert "unexpected character" in str(exc_info.value)


class TestParseErrors:
    def test_missing_end_if(self, run):
        with pytest.raises(EppParseError) as exc_info:
            run("If yes,\n    Say hello.")
        assert "End if" in str(exc_info.value) or "end" in str(exc_info.value).lower()

    def test_unknown_statement(self, run):
        with pytest.raises(EppParseError) as exc_info:
            run("Foobar something.")
        assert "unknown statement" in str(exc_info.value).lower()


class TestRuntimeErrors:
    def test_undefined_variable(self, run):
        with pytest.raises(EppRuntimeError) as exc_info:
            run("Say the value of nope.")
        assert "has not been created" in str(exc_info.value)
        assert "line 1" in str(exc_info.value)

    def test_division_by_zero(self, run):
        with pytest.raises(EppRuntimeError) as exc_info:
            run("Let x be 10.\nDivide x by 0.")
        assert "divide by zero" in str(exc_info.value).lower()
        assert "line 2" in str(exc_info.value)

    def test_set_undefined(self, run):
        with pytest.raises(EppRuntimeError) as exc_info:
            run("Set ghost to 5.")
        assert "has not been created" in str(exc_info.value)
