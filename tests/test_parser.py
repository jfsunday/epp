"""Tests for the E++ parser."""

import pytest
from epp.lexer import lex
from epp.parser import parse
from epp import ast_nodes as ast
from epp.errors import EppParseError


def parse_source(source: str):
    return parse(lex(source))


class TestLetStatement:
    def test_let_number(self):
        stmts = parse_source("Let x be 5.")
        assert len(stmts) == 1
        assert isinstance(stmts[0], ast.LetStmt)
        assert stmts[0].name == "x"
        assert isinstance(stmts[0].value, ast.NumberLit)
        assert stmts[0].value.value == 5.0

    def test_let_boolean(self):
        stmts = parse_source("Let is ready be yes.")
        assert isinstance(stmts[0], ast.LetStmt)
        assert stmts[0].name == "is ready"
        assert isinstance(stmts[0].value, ast.BoolLit)
        assert stmts[0].value.value is True

    def test_let_string(self):
        stmts = parse_source("Let greeting be hello world.")
        assert stmts[0].name == "greeting"
        assert isinstance(stmts[0].value, ast.StringLit)
        assert stmts[0].value.value == "hello world"

    def test_let_decimal(self):
        stmts = parse_source("Let pi be 3 point 14.")
        assert isinstance(stmts[0].value, ast.NumberLit)
        assert stmts[0].value.value == 3.14

    def test_let_negative(self):
        stmts = parse_source("Let temp be negative 5.")
        assert isinstance(stmts[0].value, ast.NumberLit)
        assert stmts[0].value.value == -5.0


class TestMultiWordIdentifiers:
    def test_multi_word_let(self):
        stmts = parse_source("Let my counter be 0.")
        assert stmts[0].name == "my counter"

    def test_multi_word_set(self):
        stmts = parse_source("Let total price be 0.\nSet total price to 99.")
        assert stmts[1].name == "total price"

    def test_multi_word_add(self):
        stmts = parse_source("Let total score be 0.\nAdd 10 to total score.")
        assert isinstance(stmts[1], ast.AddStmt)
        assert stmts[1].name == "total score"


class TestExpressions:
    def test_value_of_variable(self):
        stmts = parse_source("Say the value of counter.")
        assert isinstance(stmts[0], ast.SayStmt)
        assert isinstance(stmts[0].value, ast.VarRef)
        assert stmts[0].value.name == "counter"

    def test_arithmetic_chain(self):
        stmts = parse_source("Say the value of x plus 1.")
        say = stmts[0]
        assert isinstance(say.value, ast.BinaryOp)
        assert say.value.op == "plus"

    def test_comparison(self):
        stmts = parse_source("If the value of x is equal to 5,\nEnd if.")
        assert isinstance(stmts[0], ast.IfStmt)
        cond = stmts[0].branches[0][0]
        assert isinstance(cond, ast.Compare)
        assert cond.op == "eq"

    def test_remainder_operator(self):
        stmts = parse_source("Say the value of x remainder 3.")
        assert isinstance(stmts[0].value, ast.BinaryOp)
        assert stmts[0].value.op == "remainder"


class TestControlFlow:
    def test_if_else(self):
        src = """If the value of x is equal to 1,
    Say one.
Otherwise,
    Say other.
End if."""
        stmts = parse_source(src)
        assert isinstance(stmts[0], ast.IfStmt)
        assert len(stmts[0].branches) == 1
        assert stmts[0].else_body is not None

    def test_if_otherwise_if(self):
        src = """If the value of x is equal to 1,
    Say one.
Otherwise if the value of x is equal to 2,
    Say two.
Otherwise,
    Say other.
End if."""
        stmts = parse_source(src)
        assert len(stmts[0].branches) == 2
        assert stmts[0].else_body is not None

    def test_while_loop(self):
        src = """While the value of x is less than 10,
    Add 1 to x.
End while."""
        stmts = parse_source(src)
        assert isinstance(stmts[0], ast.WhileStmt)

    def test_repeat_loop(self):
        src = """Repeat 5 times,
    Say hello.
End repeat."""
        stmts = parse_source(src)
        assert isinstance(stmts[0], ast.RepeatStmt)
        assert isinstance(stmts[0].count, ast.NumberLit)
        assert stmts[0].count.value == 5.0

    def test_nested_if(self):
        src = """If yes,
    If no,
        Say inner.
    End if.
End if."""
        stmts = parse_source(src)
        outer = stmts[0]
        inner = outer.branches[0][1][0]
        assert isinstance(inner, ast.IfStmt)


class TestFunctions:
    def test_define_no_params(self):
        src = """Define greet,
    Say hello.
End define."""
        stmts = parse_source(src)
        assert isinstance(stmts[0], ast.DefineStmt)
        assert stmts[0].name == "greet"
        assert stmts[0].params == []

    def test_define_with_params(self):
        src = """Define add numbers that takes a and b,
    Return the value of a plus b.
End define."""
        stmts = parse_source(src)
        assert stmts[0].name == "add numbers"
        assert stmts[0].params == ["a", "b"]

    def test_call_with_store(self):
        src = """Call factorial with 5 and store the result in answer."""
        stmts = parse_source(src)
        assert isinstance(stmts[0], ast.CallStmt)
        assert stmts[0].name == "factorial"
        assert stmts[0].store_in == "answer"

    def test_call_no_args(self):
        src = """Call greet."""
        stmts = parse_source(src)
        assert isinstance(stmts[0], ast.CallStmt)
        assert stmts[0].name == "greet"
        assert stmts[0].args == []


class TestMissingEnd:
    def test_missing_end_if(self):
        with pytest.raises(EppParseError):
            parse_source("If yes,\n    Say hello.")

    def test_missing_end_while(self):
        with pytest.raises(EppParseError):
            parse_source("While yes,\n    Say hello.")

    def test_missing_end_repeat(self):
        with pytest.raises(EppParseError):
            parse_source("Repeat 3 times,\n    Say hello.")
