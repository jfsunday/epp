"""Tests for Say formatting and Ask auto-detection."""

import pytest


class TestSayFormatting:
    def test_integer_no_decimal(self, run):
        _, out = run("Say 42.")
        assert out == ["42"]

    def test_float_shows_decimal(self, run):
        _, out = run("Let x be 3 point 5.\nSay the value of x.")
        assert out == ["3.5"]

    def test_boolean_yes(self, run):
        _, out = run("Say yes.")
        assert out == ["yes"]

    def test_boolean_no(self, run):
        _, out = run("Say no.")
        assert out == ["no"]


class TestAskAutoDetect:
    def test_ask_integer(self, run):
        src = """Ask for x with the message Enter number.
Say the value of x plus 1."""
        _, out = run(src, inputs=["5"])
        assert out == ["6"]

    def test_ask_float(self, run):
        src = """Ask for x with the message Enter number.
Say the value of x."""
        _, out = run(src, inputs=["3.14"])
        assert out == ["3.14"]

    def test_ask_text(self, run):
        src = """Ask for name with the message Your name.
Say the value of name."""
        _, out = run(src, inputs=["Alice"])
        assert out == ["Alice"]
