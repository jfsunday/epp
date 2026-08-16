"""Tests for §14 visual statements. Parsing tests always run; runtime tests skipped without DISPLAY."""

import os
import pytest


class TestVisualParsing:
    """These tests just verify parsing, not actual window creation."""

    def test_open_window_parses(self):
        from epp.lexer import lex
        from epp.parser import parse
        from epp import ast_nodes as ast

        stmts = parse(lex("Open window with title My App."))
        assert isinstance(stmts[0], ast.OpenWindowStmt)

    def test_move_forward_parses(self):
        from epp.lexer import lex
        from epp.parser import parse
        from epp import ast_nodes as ast

        stmts = parse(lex("Move forward 100 steps."))
        assert isinstance(stmts[0], ast.MoveStmt)
        assert stmts[0].direction == "forward"

    def test_pen_up_parses(self):
        from epp.lexer import lex
        from epp.parser import parse
        from epp import ast_nodes as ast

        stmts = parse(lex("Pen up."))
        assert isinstance(stmts[0], ast.PenStmt)
        assert stmts[0].action == "up"
