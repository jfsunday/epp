"""Recursive-descent parser for E++.

Turns a list of Tokens into a list of AST nodes.
Multi-word identifiers are handled by a caller-supplied stop-word set.
"""

from __future__ import annotations
from .tokens import Token, TokenKind
from .errors import EppParseError
from . import ast_nodes as ast


# Top-level statement keywords (lowercase)
STMT_KEYWORDS = {
    "let", "set", "add", "subtract", "multiply", "divide",
    "if", "otherwise", "end", "while", "repeat",
    "say", "ask", "define", "call", "return", "note",
    "open", "move", "turn", "pen", "draw", "wait",
}


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    # ── Helpers ───────────────────────────────────────────────────────

    def current(self) -> Token:
        return self.tokens[self.pos]

    def peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]  # EOF

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def expect_word(self, word: str) -> Token:
        tok = self.current()
        if tok.kind != TokenKind.WORD or tok.value.lower() != word:
            raise EppParseError(f"expected '{word}' but found '{tok.value}'", tok.line)
        return self.advance()

    def expect_kind(self, kind: TokenKind) -> Token:
        tok = self.current()
        if tok.kind != kind:
            raise EppParseError(
                f"expected {kind.name} but found '{tok.value}'", tok.line
            )
        return self.advance()

    def at_word(self, word: str) -> bool:
        tok = self.current()
        return tok.kind == TokenKind.WORD and tok.value.lower() == word

    def at_any_word(self, *words: str) -> bool:
        tok = self.current()
        return tok.kind == TokenKind.WORD and tok.value.lower() in words

    def at_kind(self, kind: TokenKind) -> bool:
        return self.current().kind == kind

    def skip_period(self) -> None:
        if self.at_kind(TokenKind.PERIOD):
            self.advance()

    def consume_rest_of_line_as_text(self) -> str:
        """Consume tokens until PERIOD or EOF, return joined text."""
        parts: list[str] = []
        while not self.at_kind(TokenKind.PERIOD) and not self.at_kind(TokenKind.EOF):
            parts.append(self.advance().value)
        self.skip_period()
        return " ".join(parts)

    # ── Identifier Reader ────────────────────────────────────────────

    def read_identifier(self, stop_words: set[str], allow_keywords: bool = False) -> str:
        """Read a multi-word identifier, stopping at stop_words, COMMA, PERIOD, or EOF.

        If allow_keywords is True, statement keywords are allowed in the identifier
        (needed for function/variable names like 'add numbers', 'say hello').
        """
        tok = self.current()
        if tok.kind != TokenKind.WORD:
            raise EppParseError(f"expected a name but found '{tok.value}'", tok.line)
        if tok.value.lower() in stop_words:
            raise EppParseError(f"expected a name but found '{tok.value}'", tok.line)
        if not allow_keywords and tok.value.lower() in STMT_KEYWORDS:
            raise EppParseError(f"expected a name but found keyword '{tok.value}'", tok.line)

        block_keywords = stop_words if allow_keywords else stop_words | STMT_KEYWORDS
        parts: list[str] = []
        while (
            self.current().kind == TokenKind.WORD
            and self.current().value.lower() not in block_keywords
            and not self.at_kind(TokenKind.EOF)
        ):
            parts.append(self.advance().value.lower())

        return " ".join(parts)

    # ── Value / Expression Parsing ───────────────────────────────────

    def parse_value(self, stop_words: set[str] | None = None) -> object:
        """Parse a value expression. Dispatches based on leading tokens."""
        if stop_words is None:
            stop_words = set()

        tok = self.current()
        line = tok.line

        # "negative" prefix for numbers
        if self.at_word("negative"):
            self.advance()
            num = self._parse_number(line)
            num.value = -num.value
            return self._maybe_chain_ops(num, stop_words)

        # Pure number
        if tok.kind == TokenKind.NUMBER:
            node = self._parse_number(line)
            return self._maybe_chain_ops(node, stop_words)

        # Boolean literals
        if self.at_word("yes"):
            self.advance()
            return ast.BoolLit(True, line)
        if self.at_word("no"):
            self.advance()
            return ast.BoolLit(False, line)

        # "not" prefix
        if self.at_word("not"):
            self.advance()
            operand = self.parse_value(stop_words)
            return ast.NotOp(operand, line)

        # "a random number between X and Y"
        if self.at_word("a") and self.peek(1).value.lower() == "random":
            self.advance()  # a
            self.expect_word("random")
            self.expect_word("number")
            self.expect_word("between")
            low = self.parse_value({"and"})
            self.expect_word("and")
            high = self.parse_value(stop_words)
            return ast.RandomBetween(low, high, line)

        # "the value of <expr>"
        if self.at_word("the") and self.peek(1).value.lower() == "value":
            self.advance()  # the
            self.advance()  # value
            self.expect_word("of")
            return self._parse_expression(stop_words)

        # "the text box <name>" - for reading textbox values
        if self.at_word("the") and self.peek(1).value.lower() == "text":
            self.advance()  # the
            self.advance()  # text
            self.expect_word("box")
            name = self.read_identifier(stop_words)
            return ast.VarRef(f"__textbox_{name}", line)

        # Free text (string literal) — greedy until PERIOD/COMMA/EOF or stop_word
        return self._parse_free_text(stop_words)

    def _parse_number(self, line: int) -> ast.NumberLit:
        """Parse a number, handling 'point' for decimals."""
        tok = self.expect_kind(TokenKind.NUMBER)
        int_part = tok.value

        if self.at_word("point") and self.peek(1).kind == TokenKind.NUMBER:
            self.advance()  # point
            frac_tok = self.expect_kind(TokenKind.NUMBER)
            return ast.NumberLit(float(f"{int_part}.{frac_tok.value}"), line)

        val = int(int_part)
        return ast.NumberLit(float(val), line)

    def _parse_expression(self, stop_words: set[str]) -> object:
        """Parse an expression: variable reference possibly chained with operators."""
        line = self.current().line

        # Could start with a number
        if self.current().kind == TokenKind.NUMBER:
            left = self._parse_number(line)
        elif self.at_word("negative"):
            self.advance()
            left = self._parse_number(line)
            left.value = -left.value
        else:
            # Variable reference — read identifier stopping at operators and stop_words
            expr_stops = stop_words | {"plus", "minus", "times", "divided", "remainder",
                                        "is", "and", "or"}
            name = self.read_identifier(expr_stops)
            left = ast.VarRef(name, line)

        return self._maybe_chain_ops(left, stop_words)

    def _maybe_chain_ops(self, left: object, stop_words: set[str]) -> object:
        """Chain arithmetic and comparison operators."""
        while True:
            line = self.current().line
            cur = self.current().value.lower() if self.current().kind == TokenKind.WORD else ""

            # Stop if current word is in stop_words
            if cur and cur in stop_words:
                break

            # Arithmetic operators
            if self.at_word("plus"):
                self.advance()
                right = self._parse_operand(stop_words)
                left = ast.BinaryOp("plus", left, right, line)
            elif self.at_word("minus"):
                self.advance()
                right = self._parse_operand(stop_words)
                left = ast.BinaryOp("minus", left, right, line)
            elif self.at_word("times"):
                self.advance()
                right = self._parse_operand(stop_words)
                left = ast.BinaryOp("times", left, right, line)
            elif self.at_word("divided"):
                self.advance()
                self.expect_word("by")
                right = self._parse_operand(stop_words)
                left = ast.BinaryOp("divided_by", left, right, line)
            elif self.at_word("remainder"):
                self.advance()
                right = self._parse_operand(stop_words)
                left = ast.BinaryOp("remainder", left, right, line)

            # Comparison operators: "is equal to", "is greater than", etc.
            elif self.at_word("is"):
                saved = self.pos
                self.advance()  # is

                if self.at_word("equal"):
                    self.advance()
                    self.expect_word("to")
                    right = self._parse_operand(stop_words)
                    left = ast.Compare("eq", left, right, line)
                elif self.at_word("not"):
                    self.advance()
                    self.expect_word("equal")
                    self.expect_word("to")
                    right = self._parse_operand(stop_words)
                    left = ast.Compare("ne", left, right, line)
                elif self.at_word("greater"):
                    self.advance()
                    self.expect_word("than")
                    if self.at_word("or"):
                        self.advance()
                        self.expect_word("equal")
                        self.expect_word("to")
                        right = self._parse_operand(stop_words)
                        left = ast.Compare("ge", left, right, line)
                    else:
                        right = self._parse_operand(stop_words)
                        left = ast.Compare("gt", left, right, line)
                elif self.at_word("less"):
                    self.advance()
                    self.expect_word("than")
                    if self.at_word("or"):
                        self.advance()
                        self.expect_word("equal")
                        self.expect_word("to")
                        right = self._parse_operand(stop_words)
                        left = ast.Compare("le", left, right, line)
                    else:
                        right = self._parse_operand(stop_words)
                        left = ast.Compare("lt", left, right, line)
                else:
                    # Not a comparison — backtrack
                    self.pos = saved
                    break

            # Logic operators
            elif self.at_word("and"):
                self.advance()
                right = self.parse_value(stop_words)
                left = ast.LogicOp("and", left, right, line)
            elif self.at_word("or"):
                self.advance()
                right = self.parse_value(stop_words)
                left = ast.LogicOp("or", left, right, line)
            else:
                break

        return left

    def _parse_operand(self, stop_words: set[str]) -> object:
        """Parse a single operand (number, variable ref, or nested expression)."""
        line = self.current().line

        if self.current().kind == TokenKind.NUMBER:
            return self._parse_number(line)
        if self.at_word("negative"):
            self.advance()
            n = self._parse_number(line)
            n.value = -n.value
            return n
        if self.at_word("a") and self.peek(1).value.lower() == "random":
            return self.parse_value(stop_words)

        # Variable reference
        expr_stops = stop_words | {"plus", "minus", "times", "divided", "remainder",
                                    "is", "and", "or"}
        name = self.read_identifier(expr_stops)
        return ast.VarRef(name, line)

    def _parse_free_text(self, stop_words: set[str]) -> ast.StringLit:
        """Parse free text as a string literal until PERIOD/COMMA/EOF/stop_word."""
        line = self.current().line
        parts: list[str] = []

        while (
            not self.at_kind(TokenKind.PERIOD)
            and not self.at_kind(TokenKind.COMMA)
            and not self.at_kind(TokenKind.EOF)
        ):
            tok = self.current()
            if tok.kind == TokenKind.WORD and tok.value.lower() in stop_words:
                break
            parts.append(self.advance().value)

        if not parts:
            raise EppParseError("expected a value but found nothing", line)

        return ast.StringLit(" ".join(parts), line)

    # ── Condition Parsing ────────────────────────────────────────────

    def parse_condition(self) -> object:
        """Parse a condition for If/While statements."""
        return self.parse_value()

    # ── Statement Parsing ────────────────────────────────────────────

    def parse_program(self) -> list[object]:
        """Parse the entire program into a list of statements."""
        stmts: list[object] = []
        while not self.at_kind(TokenKind.EOF):
            stmt = self.parse_statement()
            if stmt is not None:
                stmts.append(stmt)
        return stmts

    def parse_statement(self) -> object | None:
        """Parse a single statement."""
        tok = self.current()
        line = tok.line

        if tok.kind != TokenKind.WORD:
            if tok.kind == TokenKind.PERIOD:
                self.advance()
                return None
            raise EppParseError(f"expected a statement but found '{tok.value}'", line)

        word = tok.value.lower()

        if word == "let":
            return self._parse_let(line)
        elif word == "set":
            return self._parse_set(line)
        elif word == "add":
            return self._parse_add(line)
        elif word == "subtract":
            return self._parse_subtract(line)
        elif word == "multiply":
            return self._parse_multiply(line)
        elif word == "divide":
            return self._parse_divide(line)
        elif word == "if":
            return self._parse_if(line)
        elif word == "while":
            return self._parse_while(line)
        elif word == "repeat":
            return self._parse_repeat(line)
        elif word == "say":
            return self._parse_say(line)
        elif word == "ask":
            return self._parse_ask(line)
        elif word == "define":
            return self._parse_define(line)
        elif word == "call":
            return self._parse_call(line)
        elif word == "return":
            return self._parse_return(line)
        elif word == "note":
            return self._parse_note(line)
        elif word == "open":
            return self._parse_open_window(line)
        elif word == "move":
            return self._parse_move(line)
        elif word == "turn":
            return self._parse_turn(line)
        elif word == "pen":
            return self._parse_pen(line)
        elif word == "draw":
            return self._parse_draw(line)
        elif word == "wait":
            return self._parse_wait(line)
        else:
            raise EppParseError(f"unknown statement '{tok.value}'", line)

    def _parse_block(self, end_words: set[str]) -> list[object]:
        """Parse statements until we encounter a line starting with one of end_words."""
        stmts: list[object] = []
        while not self.at_kind(TokenKind.EOF):
            if self.current().kind == TokenKind.WORD and self.current().value.lower() in end_words:
                break
            stmt = self.parse_statement()
            if stmt is not None:
                stmts.append(stmt)
        return stmts

    # ── Individual Statement Parsers ─────────────────────────────────

    def _parse_let(self, line: int) -> ast.LetStmt:
        """Let <name> be <value>."""
        self.advance()  # let
        name = self.read_identifier({"be"})
        self.expect_word("be")
        value = self.parse_value()
        self.skip_period()
        return ast.LetStmt(name, value, line)

    def _parse_set(self, line: int) -> object:
        """Set <name> to <value>.  OR  Set window size to <w> by <h>."""
        self.advance()  # set

        # Check for "Set window size to W by H"
        if self.at_word("window"):
            self.advance()  # window
            self.expect_word("size")
            self.expect_word("to")
            width = self.parse_value({"by"})
            self.expect_word("by")
            height = self.parse_value()
            self.skip_period()
            return ast.SetWindowSizeStmt(width, height, line)

        # Check for "Set pen color to <color>"
        if self.at_word("pen"):
            self.advance()  # pen
            self.expect_word("color")
            self.expect_word("to")
            color = self.parse_value()
            self.skip_period()
            return ast.SetPenColorStmt(color, line)

        name = self.read_identifier({"to"})
        self.expect_word("to")
        value = self.parse_value()
        self.skip_period()
        return ast.SetStmt(name, value, line)

    def _parse_add(self, line: int) -> object:
        """Add <value> to <name>.  OR  Add button/label/text box (§14)."""
        self.advance()  # add

        # §14: Add button with text <text> that calls <fn>.
        if self.at_word("button"):
            self.advance()  # button
            self.expect_word("with")
            self.expect_word("text")
            text = self.parse_value({"that"})
            self.expect_word("that")
            self.expect_word("calls")
            fn_name = self.read_identifier(set(), allow_keywords=True)
            self.skip_period()
            return ast.AddButtonStmt(text, fn_name, line)

        # §14: Add label <text>.
        if self.at_word("label"):
            self.advance()  # label
            text = self.parse_value()
            self.skip_period()
            return ast.AddLabelStmt(text, line)

        # §14: Add text box <name>.
        if self.at_word("text"):
            self.advance()  # text
            self.expect_word("box")
            name = self.read_identifier(set(), allow_keywords=True)
            self.skip_period()
            return ast.AddTextBoxStmt(name, line)

        # Arithmetic: Add <value> to <name>.
        value = self.parse_value({"to"})
        self.expect_word("to")
        name = self.read_identifier(set())
        self.skip_period()
        return ast.AddStmt(name, value, line)

    def _parse_subtract(self, line: int) -> ast.SubtractStmt:
        """Subtract <value> from <name>."""
        self.advance()  # subtract
        value = self.parse_value({"from"})
        self.expect_word("from")
        name = self.read_identifier(set())
        self.skip_period()
        return ast.SubtractStmt(name, value, line)

    def _parse_multiply(self, line: int) -> ast.MultiplyStmt:
        """Multiply <name> by <value>."""
        self.advance()  # multiply
        name = self.read_identifier({"by"})
        self.expect_word("by")
        value = self.parse_value()
        self.skip_period()
        return ast.MultiplyStmt(name, value, line)

    def _parse_divide(self, line: int) -> ast.DivideStmt:
        """Divide <name> by <value>."""
        self.advance()  # divide
        name = self.read_identifier({"by"})
        self.expect_word("by")
        value = self.parse_value()
        self.skip_period()
        return ast.DivideStmt(name, value, line)

    def _parse_if(self, line: int) -> ast.IfStmt:
        """If <cond>, <body> [Otherwise if <cond>, <body>]* [Otherwise, <body>] End if."""
        self.advance()  # if
        cond = self.parse_condition()
        self.expect_kind(TokenKind.COMMA)

        branches: list[tuple[object, list[object]]] = []
        body = self._parse_block({"otherwise", "end"})
        branches.append((cond, body))

        else_body: list[object] | None = None

        while self.at_word("otherwise"):
            self.advance()  # otherwise
            if self.at_word("if"):
                self.advance()  # if
                cond = self.parse_condition()
                self.expect_kind(TokenKind.COMMA)
                body = self._parse_block({"otherwise", "end"})
                branches.append((cond, body))
            else:
                self.expect_kind(TokenKind.COMMA)
                else_body = self._parse_block({"end"})
                break

        if not self.at_word("end"):
            raise EppParseError("expected 'End if' to close the if block", self.current().line)
        self.advance()  # end
        self.expect_word("if")
        self.skip_period()

        return ast.IfStmt(branches, else_body, line)

    def _parse_while(self, line: int) -> ast.WhileStmt:
        """While <cond>, <body> End while."""
        self.advance()  # while
        cond = self.parse_condition()
        self.expect_kind(TokenKind.COMMA)

        body = self._parse_block({"end"})

        if not self.at_word("end"):
            raise EppParseError("expected 'End while' to close the while block", self.current().line)
        self.advance()  # end
        self.expect_word("while")
        self.skip_period()

        return ast.WhileStmt(cond, body, line)

    def _parse_repeat(self, line: int) -> ast.RepeatStmt:
        """Repeat <n> times, <body> End repeat."""
        self.advance()  # repeat
        count = self.parse_value({"times"})
        self.expect_word("times")
        self.expect_kind(TokenKind.COMMA)

        body = self._parse_block({"end"})

        if not self.at_word("end"):
            raise EppParseError("expected 'End repeat' to close the repeat block", self.current().line)
        self.advance()  # end
        self.expect_word("repeat")
        self.skip_period()

        return ast.RepeatStmt(count, body, line)

    def _parse_say(self, line: int) -> ast.SayStmt:
        """Say <value>."""
        self.advance()  # say
        value = self.parse_value()
        self.skip_period()
        return ast.SayStmt(value, line)

    def _parse_ask(self, line: int) -> ast.AskStmt:
        """Ask for <var> with the message <prompt>."""
        self.advance()  # ask
        self.expect_word("for")
        name = self.read_identifier({"with"})
        self.expect_word("with")
        self.expect_word("the")
        self.expect_word("message")
        prompt = self.parse_value()
        self.skip_period()
        return ast.AskStmt(name, prompt, line)

    def _parse_define(self, line: int) -> ast.DefineStmt:
        """Define <name> that takes <params>, <body> End define.
        OR: Define <name>, <body> End define."""
        self.advance()  # define

        name = self.read_identifier({"that"}, allow_keywords=True)

        params: list[str] = []
        if self.at_word("that"):
            self.advance()  # that
            self.expect_word("takes")
            # Parse parameter list: param1, param2, and param3
            params = self._parse_param_list()

        self.expect_kind(TokenKind.COMMA)
        body = self._parse_block({"end"})

        if not self.at_word("end"):
            raise EppParseError("expected 'End define' to close the function", self.current().line)
        self.advance()  # end
        self.expect_word("define")
        self.skip_period()

        return ast.DefineStmt(name, params, body, line)

    def _parse_param_list(self) -> list[str]:
        """Parse a parameter list like: X, Y, and Z or just X.

        The final comma after all params belongs to _parse_define (body start),
        so we only consume a comma if we can see another parameter name after it
        (on the same line or preceded by 'and').
        """
        params: list[str] = []

        # Read first param
        param = self.read_identifier({"and"}, allow_keywords=True)
        params.append(param)

        while self.at_kind(TokenKind.COMMA):
            # Peek: is the token after the comma 'and' or a param name on the same line?
            # If not, this comma is the body-start comma — don't consume it.
            comma_tok = self.current()
            next_tok = self.peek(1)

            # If next token is on a different line and not 'and', it's the body comma
            if next_tok.line != comma_tok.line and not (next_tok.kind == TokenKind.WORD and next_tok.value.lower() == "and"):
                break

            # If next token is 'and' followed by something, it's a param separator
            if next_tok.kind == TokenKind.WORD and next_tok.value.lower() == "and":
                self.advance()  # comma
                self.advance()  # and
                param = self.read_identifier({"and"}, allow_keywords=True)
                params.append(param)
                continue

            # Otherwise consume comma and next param
            self.advance()  # comma
            param = self.read_identifier({"and"}, allow_keywords=True)
            params.append(param)

        # Handle "and" without preceding comma
        if self.at_word("and"):
            self.advance()
            param = self.read_identifier(set(), allow_keywords=True)
            params.append(param)

        return params

    def _parse_call(self, line: int) -> ast.CallStmt:
        """Call <name> [with <args>] [and store the result in <var>]."""
        self.advance()  # call

        name = self.read_identifier({"with", "and"}, allow_keywords=True)

        args: list[object] = []
        if self.at_word("with"):
            self.advance()  # with
            args = self._parse_arg_list()

        store_in: str | None = None
        if self.at_word("and"):
            self.advance()  # and
            self.expect_word("store")
            self.expect_word("the")
            self.expect_word("result")
            self.expect_word("in")
            store_in = self.read_identifier(set())

        self.skip_period()
        return ast.CallStmt(name, args, store_in, line)

    def _parse_arg_list(self) -> list[object]:
        """Parse argument list: val1, val2, and val3."""
        args: list[object] = []

        arg = self.parse_value({"and", ","})
        args.append(arg)

        while self.at_kind(TokenKind.COMMA):
            self.advance()  # comma
            if self.at_word("and"):
                self.advance()
            # Check for "store" pattern
            if self.at_word("and") or (self.current().kind == TokenKind.WORD and self.current().value.lower() == "store"):
                break
            arg = self.parse_value({"and", ","})
            args.append(arg)

        if self.at_word("and"):
            saved = self.pos
            self.advance()  # and
            if self.at_word("store"):
                self.pos = saved  # backtrack, let caller handle "and store..."
            else:
                arg = self.parse_value({"and", ","})
                args.append(arg)

        return args

    def _parse_return(self, line: int) -> ast.ReturnStmt:
        """Return <value>."""
        self.advance()  # return
        value = self.parse_value()
        self.skip_period()
        return ast.ReturnStmt(value, line)

    def _parse_note(self, line: int) -> ast.NoteStmt:
        """Note <text>. (comment, ignored at runtime)"""
        self.advance()  # note
        text = self.consume_rest_of_line_as_text()
        return ast.NoteStmt(text, line)

    # ── §14 Visual Statement Parsers ─────────────────────────────────

    def _parse_open_window(self, line: int) -> ast.OpenWindowStmt:
        """Open window with title <text>."""
        self.advance()  # open
        self.expect_word("window")
        self.expect_word("with")
        self.expect_word("title")
        title = self.parse_value()
        self.skip_period()
        return ast.OpenWindowStmt(title, line)

    def _parse_move(self, line: int) -> ast.MoveStmt:
        """Move forward/backward <n> steps."""
        self.advance()  # move
        if self.at_word("forward"):
            direction = "forward"
        elif self.at_word("backward"):
            direction = "backward"
        else:
            raise EppParseError("expected 'forward' or 'backward' after Move", line)
        self.advance()
        amount = self.parse_value({"steps"})
        if self.at_word("steps"):
            self.advance()
        self.skip_period()
        return ast.MoveStmt(direction, amount, line)

    def _parse_turn(self, line: int) -> ast.TurnStmt:
        """Turn left/right <n> degrees."""
        self.advance()  # turn
        if self.at_word("left"):
            direction = "left"
        elif self.at_word("right"):
            direction = "right"
        else:
            raise EppParseError("expected 'left' or 'right' after Turn", line)
        self.advance()
        degrees = self.parse_value({"degrees"})
        if self.at_word("degrees"):
            self.advance()
        self.skip_period()
        return ast.TurnStmt(direction, degrees, line)

    def _parse_pen(self, line: int) -> ast.PenStmt:
        """Pen up / Pen down."""
        self.advance()  # pen
        if self.at_word("up"):
            action = "up"
        elif self.at_word("down"):
            action = "down"
        else:
            raise EppParseError("expected 'up' or 'down' after Pen", line)
        self.advance()
        self.skip_period()
        return ast.PenStmt(action, line)

    def _parse_draw(self, line: int) -> ast.DrawCircleStmt:
        """Draw circle with radius <n>."""
        self.advance()  # draw
        self.expect_word("circle")
        self.expect_word("with")
        self.expect_word("radius")
        radius = self.parse_value()
        self.skip_period()
        return ast.DrawCircleStmt(radius, line)

    def _parse_wait(self, line: int) -> ast.WaitForCloseStmt:
        """Wait for close."""
        self.advance()  # wait
        self.expect_word("for")
        self.expect_word("close")
        self.skip_period()
        return ast.WaitForCloseStmt(line)


def parse(tokens: list[Token]) -> list[object]:
    """Parse a token list into a list of AST nodes."""
    parser = Parser(tokens)
    return parser.parse_program()
