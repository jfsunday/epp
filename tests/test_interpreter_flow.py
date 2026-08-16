"""Tests for control flow: if/otherwise, while, repeat, scoping."""

import pytest


class TestIfStatements:
    def test_if_true(self, run):
        _, out = run("If yes,\n    Say true.\nEnd if.")
        assert out == ["true"]

    def test_if_false(self, run):
        _, out = run("If no,\n    Say true.\nEnd if.")
        assert out == []

    def test_if_else(self, run):
        _, out = run("If no,\n    Say a.\nOtherwise,\n    Say b.\nEnd if.")
        assert out == ["b"]

    def test_if_otherwise_if(self, run):
        src = """Let x be 2.
If the value of x is equal to 1,
    Say one.
Otherwise if the value of x is equal to 2,
    Say two.
Otherwise,
    Say other.
End if."""
        _, out = run(src)
        assert out == ["two"]

    def test_nested_if(self, run):
        src = """If yes,
    If yes,
        Say inner.
    End if.
End if."""
        _, out = run(src)
        assert out == ["inner"]


class TestWhileLoop:
    def test_basic_while(self, run):
        src = """Let i be 0.
While the value of i is less than 3,
    Say the value of i.
    Add 1 to i.
End while."""
        _, out = run(src)
        assert out == ["0", "1", "2"]

    def test_while_false(self, run):
        _, out = run("While no,\n    Say never.\nEnd while.")
        assert out == []


class TestRepeatLoop:
    def test_repeat(self, run):
        src = """Repeat 3 times,
    Say hi.
End repeat."""
        _, out = run(src)
        assert out == ["hi", "hi", "hi"]

    def test_repeat_zero(self, run):
        _, out = run("Repeat 0 times,\n    Say nope.\nEnd repeat.")
        assert out == []


class TestScoping:
    def test_block_shares_scope(self, run):
        src = """Let x be 1.
If yes,
    Set x to 2.
End if.
Say the value of x."""
        _, out = run(src)
        assert out == ["2"]

    def test_while_shares_scope(self, run):
        src = """Let count be 0.
Repeat 5 times,
    Add 1 to count.
End repeat.
Say the value of count."""
        _, out = run(src)
        assert out == ["5"]
