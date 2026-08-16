"""Tests for core interpreter features: arithmetic, strings, booleans, comparisons."""

import pytest


class TestArithmetic:
    def test_addition(self, run):
        _, out = run("Let x be 10.\nAdd 5 to x.\nSay the value of x.")
        assert out == ["15"]

    def test_subtraction(self, run):
        _, out = run("Let x be 10.\nSubtract 3 from x.\nSay the value of x.")
        assert out == ["7"]

    def test_multiplication(self, run):
        _, out = run("Let x be 4.\nMultiply x by 3.\nSay the value of x.")
        assert out == ["12"]

    def test_division(self, run):
        _, out = run("Let x be 10.\nDivide x by 4.\nSay the value of x.")
        assert out == ["2.5"]

    def test_remainder(self, run):
        _, out = run("Say the value of 10 remainder 3.")
        assert out == ["1"]

    def test_chain_arithmetic(self, run):
        _, out = run("Say the value of 2 plus 3 times 2.")
        # Left-to-right: (2+3)*2 = 10
        assert out == ["10"]

    def test_negative_number(self, run):
        _, out = run("Let x be negative 5.\nSay the value of x.")
        assert out == ["-5"]

    def test_decimal_number(self, run):
        _, out = run("Let x be 3 point 14.\nSay the value of x.")
        assert out == ["3.14"]


class TestStrings:
    def test_say_free_text(self, run):
        _, out = run("Say hello world.")
        assert out == ["hello world"]

    def test_string_plus_string(self, run):
        _, out = run('Let a be hello.\nLet b be world.\nSay the value of a plus b.')
        assert out == ["hello world"]

    def test_number_plus_string(self, run):
        _, out = run('Let a be 42.\nLet b be things.\nSay the value of a plus b.')
        assert out == ["42 things"]


class TestBooleans:
    def test_say_yes(self, run):
        _, out = run("Let flag be yes.\nSay the value of flag.")
        assert out == ["yes"]

    def test_say_no(self, run):
        _, out = run("Let flag be no.\nSay the value of flag.")
        assert out == ["no"]

    def test_not_operator(self, run):
        _, out = run("Let flag be yes.\nSay not the value of flag.")
        assert out == ["no"]


class TestComparisons:
    def test_equal(self, run):
        _, out = run("Let x be 5.\nIf the value of x is equal to 5,\n    Say yes.\nEnd if.")
        assert out == ["yes"]

    def test_not_equal(self, run):
        _, out = run("Let x be 5.\nIf the value of x is not equal to 3,\n    Say different.\nEnd if.")
        assert out == ["different"]

    def test_greater_than(self, run):
        _, out = run("Let x be 10.\nIf the value of x is greater than 5,\n    Say big.\nEnd if.")
        assert out == ["big"]

    def test_less_than(self, run):
        _, out = run("Let x be 2.\nIf the value of x is less than 5,\n    Say small.\nEnd if.")
        assert out == ["small"]

    def test_greater_or_equal(self, run):
        _, out = run("Let x be 5.\nIf the value of x is greater than or equal to 5,\n    Say ok.\nEnd if.")
        assert out == ["ok"]

    def test_less_or_equal(self, run):
        _, out = run("Let x be 5.\nIf the value of x is less than or equal to 5,\n    Say ok.\nEnd if.")
        assert out == ["ok"]


class TestRandom:
    def test_random_in_range(self, run):
        import random
        random.seed(42)
        _, out = run("Let x be a random number between 1 and 10.\nSay the value of x.")
        val = int(out[0])
        assert 1 <= val <= 10
