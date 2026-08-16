"""Shared test fixtures for E++."""

import pytest
from epp import run_source
from epp.interpreter import Interpreter
from epp.lexer import lex
from epp.parser import parse


@pytest.fixture
def run():
    """Run E++ source and return (interpreter, output_lines)."""
    def _run(source: str, inputs: list[str] | None = None):
        input_iter = iter(inputs or [])
        output: list[str] = []

        def mock_say(text):
            output.append(text)

        def mock_input(prompt=""):
            try:
                return next(input_iter)
            except StopIteration:
                return ""

        interp = run_source(source, say_fn=mock_say, input_fn=mock_input)
        return interp, output

    return _run
