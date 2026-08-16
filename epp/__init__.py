"""E++ — a programming language made entirely of English words."""

from .interpreter import Interpreter
from .lexer import lex
from .parser import parse


def run_source(source: str, *, say_fn=None, input_fn=None) -> Interpreter:
    """Parse and run E++ source code. Returns the interpreter for inspection."""
    tokens = lex(source)
    statements = parse(tokens)
    interp = Interpreter()
    if say_fn is not None:
        interp._say_fn = say_fn
    if input_fn is not None:
        interp._input_fn = input_fn
    interp.run(statements)
    return interp


def run_file(path: str) -> Interpreter:
    """Read and run an E++ source file."""
    with open(path, 'r') as f:
        source = f.read()
    return run_source(source)
