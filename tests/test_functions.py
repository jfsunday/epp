"""Tests for function definition, calling, recursion, and arity."""

import pytest
from epp.errors import EppRuntimeError


class TestDefineAndCall:
    def test_simple_function(self, run):
        src = """Define greet,
    Say hello.
End define.
Call greet."""
        _, out = run(src)
        assert out == ["hello"]

    def test_function_with_params(self, run):
        src = """Define say number that takes n,
    Say the value of n.
End define.
Call say number with 42."""
        _, out = run(src)
        assert out == ["42"]

    def test_store_result(self, run):
        src = """Define double that takes n,
    Return the value of n times 2.
End define.
Call double with 5 and store the result in answer.
Say the value of answer."""
        _, out = run(src)
        assert out == ["10"]


class TestRecursion:
    def test_factorial(self, run):
        src = """Define factorial that takes n,
    If the value of n is less than or equal to 1,
        Return 1.
    End if.
    Call factorial with the value of n minus 1 and store the result in sub.
    Return the value of n times sub.
End define.
Call factorial with 5 and store the result in r.
Say the value of r."""
        _, out = run(src)
        assert out == ["120"]


class TestArityErrors:
    def test_too_many_args(self, run):
        src = """Define one that takes a,
    Say the value of a.
End define.
Call one with 1, 2."""
        with pytest.raises(EppRuntimeError, match="expects 1"):
            run(src)

    def test_undefined_function(self, run):
        with pytest.raises(EppRuntimeError, match="has not been defined"):
            run("Call nonexistent.")


class TestFunctionScope:
    def test_local_doesnt_leak(self, run):
        src = """Define make local,
    Let inner be 99.
End define.
Call make local.
Say the value of inner."""
        with pytest.raises(EppRuntimeError, match="has not been created"):
            run(src)

    def test_function_sees_globals(self, run):
        src = """Let x be 42.
Define show,
    Say the value of x.
End define.
Call show."""
        _, out = run(src)
        assert out == ["42"]
