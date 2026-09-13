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
    "open", "move", "turn", "pen", "draw", "wait", "clear", "shuffle",
    "start", "create", "remove", "for",
    "respond", "insert", "select", "update", "delete", "close",
    "read", "write", "enable", "serve", "show", "run",
    "every", "stop", "when", "before", "send", "broadcast", "arrange", "align",
}

# Words that may follow "the" to introduce a built-in expression.
THE_EXPRESSIONS = {
    "length", "keys", "entry", "mean", "sum", "min", "max", "dot",
    "exponential", "logarithm",
    "lowercase", "uppercase", "split", "substring", "position",
    "number", "text", "current", "body", "path", "query", "dropdown",
    "cookie", "session", "form", "uploaded",
    "checkbox", "radio", "slider", "mouse", "x", "y",
}

# Ready-made games that "Start a ... game." can launch.
_GAME_TYPES = {"jump and run", "flappy bird", "snake", "pong", "memory"}


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

    def read_identifier(self, stop_words: set[str], allow_keywords: bool = False,
                        keep_case: bool = False) -> str:
        """Read a multi-word identifier, stopping at stop_words, COMMA, PERIOD, or EOF.

        If allow_keywords is True, statement keywords are allowed in the identifier
        (needed for function/variable names like 'add numbers', 'say hello').
        If keep_case is True, the original spelling is preserved (used for labels
        that end up on screen, such as menu titles).
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
            value = self.advance().value
            parts.append(value if keep_case else value.lower())

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

        # Special word literals
        if tok.kind == TokenKind.WORD and tok.value.lower() in self._SPECIAL_WORDS:
            val = self._SPECIAL_WORDS[tok.value.lower()]
            self.advance()
            return self._maybe_chain_ops(ast.StringLit(val, line), stop_words)

        # "not" prefix
        if self.at_word("not"):
            self.advance()
            operand = self.parse_value(stop_words)
            return ast.NotOp(operand, line)

        # "a random number between X and Y" or "a random item from LIST"
        if self.at_word("a") and self.peek(1).value.lower() == "random":
            self.advance()  # a
            self.advance()  # random
            if self.at_word("item"):
                self.advance()  # item
                self.expect_word("from")
                name = self.read_identifier(stop_words)
                return ast.RandomItemExpr(name, line)
            if self.at_word("decimal"):
                self.advance()  # decimal
                self.expect_word("between")
                low = self.parse_value({"and"})
                self.expect_word("and")
                high = self.parse_value(stop_words)
                return ast.RandomDecimalBetween(low, high, line)
            self.expect_word("number")
            self.expect_word("between")
            low = self.parse_value({"and"})
            self.expect_word("and")
            high = self.parse_value(stop_words)
            return ast.RandomBetween(low, high, line)

        # "key left is pressed"
        if self.at_word("key"):
            saved = self.pos
            self.advance()  # key
            try:
                key = self.read_identifier({"is"})
            except EppParseError:
                self.pos = saved
            else:
                if self.at_word("is") and self.peek(1).value.lower() == "pressed":
                    self.advance()  # is
                    self.advance()  # pressed
                    return ast.KeyPressedExpr(key, line)
                self.pos = saved

        # "sprite bird collides with sprite pipe"
        if self.at_word("sprite"):
            saved = self.pos
            self.advance()  # sprite
            try:
                left_name = self.read_identifier({"collides"})
            except EppParseError:
                self.pos = saved
            else:
                if self.at_word("collides"):
                    self.advance()  # collides
                    self.expect_word("with")
                    self.expect_word("sprite")
                    right_name = self.read_identifier(stop_words)
                    return ast.SpriteCollidesExpr(left_name, right_name, line)
                self.pos = saved

        # "item N of LIST"
        if self.at_word("item"):
            self.advance()  # item
            index = self._parse_operand({"of"} | stop_words)
            self.expect_word("of")
            name = self.read_identifier(stop_words)
            return self._maybe_chain_ops(ast.ItemOfExpr(index, name, line), stop_words)

        # Unified "the ..." handler
        if self.at_word("the"):
            peek_val = self.peek(1).value.lower()

            if peek_val == "value":
                self.advance()  # the
                self.advance()  # value
                self.expect_word("of")
                return self._parse_expression(stop_words)

            elif peek_val == "text":
                peek2 = self.peek(2).value.lower()
                if peek2 == "box":
                    self.advance()  # the
                    self.advance()  # text
                    self.advance()  # box
                    name = self.read_identifier(stop_words)
                    return ast.VarRef(f"__textbox_{name}", line)
                elif peek2 == "of":
                    self.advance()  # the
                    self.advance()  # text
                    self.advance()  # of
                    name = self.read_identifier(stop_words)
                    return self._maybe_chain_ops(ast.TextOfExpr(ast.VarRef(name, line), line), stop_words)

            elif peek_val == "length":
                self.advance()  # the
                self.advance()  # length
                self.expect_word("of")
                name = self.read_identifier(stop_words)
                return self._maybe_chain_ops(ast.LengthOfExpr(name, line), stop_words)
            elif peek_val == "keys":
                self.advance()  # the
                self.advance()  # keys
                self.expect_word("of")
                name = self.read_identifier(stop_words)
                return ast.KeysOfExpr(name, line)
            elif peek_val == "entry":
                self.advance()  # the
                self.advance()  # entry
                key = self.parse_value({"in"} | stop_words)
                self.expect_word("in")
                name = self.read_identifier(stop_words)
                return self._maybe_chain_ops(ast.EntryInExpr(key, name, line), stop_words)
            elif peek_val == "mean":
                self.advance()  # the
                self.advance()  # mean
                self.expect_word("of")
                name = self.read_identifier(stop_words)
                return self._maybe_chain_ops(ast.MeanOfExpr(name, line), stop_words)
            elif peek_val == "sum":
                self.advance()  # the
                self.advance()  # sum
                self.expect_word("of")
                name = self.read_identifier(stop_words)
                return self._maybe_chain_ops(ast.SumOfExpr(name, line), stop_words)
            elif peek_val == "min":
                self.advance()  # the
                self.advance()  # min
                self.expect_word("of")
                name = self.read_identifier(stop_words)
                return self._maybe_chain_ops(ast.MinOfExpr(name, line), stop_words)
            elif peek_val == "max":
                self.advance()  # the
                self.advance()  # max
                self.expect_word("of")
                name = self.read_identifier(stop_words)
                return self._maybe_chain_ops(ast.MaxOfExpr(name, line), stop_words)
            elif peek_val == "dot":
                self.advance()  # the
                self.advance()  # dot
                self.expect_word("product")
                self.expect_word("of")
                left = self.read_identifier({"and"} | stop_words)
                self.expect_word("and")
                right = self.read_identifier(stop_words)
                return ast.DotProductExpr(left, right, line)

            # ── Math function expressions ──
            elif peek_val == "exponential":
                self.advance()  # the
                self.advance()  # exponential
                self.expect_word("of")
                val = self.parse_value(stop_words)
                return self._maybe_chain_ops(ast.ExponentialOfExpr(val, line), stop_words)
            elif peek_val == "logarithm":
                self.advance()  # the
                self.advance()  # logarithm
                self.expect_word("of")
                val = self.parse_value(stop_words)
                return self._maybe_chain_ops(ast.LogarithmOfExpr(val, line), stop_words)

            # ── String operation expressions ──
            elif peek_val == "lowercase":
                self.advance()  # the
                self.advance()  # lowercase
                self.expect_word("of")
                name = self.read_identifier(stop_words)
                return self._maybe_chain_ops(ast.LowercaseOfExpr(ast.VarRef(name, line), line), stop_words)
            elif peek_val == "uppercase":
                self.advance()  # the
                self.advance()  # uppercase
                self.expect_word("of")
                name = self.read_identifier(stop_words)
                return self._maybe_chain_ops(ast.UppercaseOfExpr(ast.VarRef(name, line), line), stop_words)
            elif peek_val == "split":
                self.advance()  # the
                self.advance()  # split
                self.expect_word("of")
                name = self.read_identifier({"by"} | stop_words)
                self.expect_word("by")
                delim = self.parse_value(stop_words)
                return ast.SplitByExpr(ast.VarRef(name, line), delim, line)
            elif peek_val == "substring":
                self.advance()  # the
                self.advance()  # substring
                self.expect_word("of")
                name = self.read_identifier({"from"} | stop_words)
                self.expect_word("from")
                start = self.parse_value({"to"} | stop_words)
                self.expect_word("to")
                end = self.parse_value(stop_words)
                return ast.SubstringOfExpr(ast.VarRef(name, line), start, end, line)
            elif peek_val == "position":
                self.advance()  # the
                self.advance()  # position
                self.expect_word("of")
                needle = self.parse_value({"in"} | stop_words)
                self.expect_word("in")
                name = self.read_identifier(stop_words)
                return ast.PositionOfExpr(needle, ast.VarRef(name, line), line)
            elif peek_val == "number":
                self.advance()  # the
                self.advance()  # number
                self.expect_word("of")
                name = self.read_identifier(stop_words)
                return self._maybe_chain_ops(ast.NumberOfExpr(ast.VarRef(name, line), line), stop_words)

            # ── Timestamp expressions ──
            elif peek_val == "current":
                peek2 = self.peek(2).value.lower()
                if peek2 == "timestamp":
                    self.advance()  # the
                    self.advance()  # current
                    self.advance()  # timestamp
                    return self._maybe_chain_ops(ast.CurrentTimestampExpr(line), stop_words)
                elif peek2 == "date":
                    self.advance()  # the
                    self.advance()  # current
                    self.advance()  # date
                    return self._maybe_chain_ops(ast.CurrentDateExpr(line), stop_words)
                elif peek2 == "time":
                    self.advance()  # the
                    self.advance()  # current
                    self.advance()  # time
                    return self._maybe_chain_ops(ast.CurrentTimeExpr(line), stop_words)

            # ── Request access expressions ──
            elif peek_val == "body":
                self.advance()  # the
                self.advance()  # body
                self.expect_word("of")
                name = self.read_identifier(stop_words)
                return ast.BodyOfExpr(name, line)
            elif peek_val == "path":
                self.advance()  # the
                self.advance()  # path
                self.expect_word("parameter")
                param = self.read_identifier({"of"} | stop_words)
                self.expect_word("of")
                name = self.read_identifier(stop_words)
                return ast.PathParamExpr(param, name, line)
            elif peek_val == "query":
                self.advance()  # the
                self.advance()  # query
                self.expect_word("parameter")
                param = self.read_identifier({"of"} | stop_words)
                self.expect_word("of")
                name = self.read_identifier(stop_words)
                return ast.QueryParamExpr(param, name, line)

            # ── Cookies, sessions, forms, uploads ──
            elif peek_val == "cookie":
                self.advance()  # the
                self.advance()  # cookie
                cookie_name = self.read_identifier({"of"} | stop_words)
                self.expect_word("of")
                request_var = self.read_identifier(stop_words)
                return ast.CookieExpr(cookie_name, request_var, line)
            elif peek_val == "session":
                self.advance()  # the
                self.advance()  # session
                self.expect_word("value")
                key = self.read_identifier({"of"} | stop_words)
                self.expect_word("of")
                request_var = self.read_identifier(stop_words)
                return ast.SessionValueExpr(key, request_var, line)
            elif peek_val == "form":
                self.advance()  # the
                self.advance()  # form
                self.expect_word("value")
                field_name = self.read_identifier({"of"} | stop_words)
                self.expect_word("of")
                request_var = self.read_identifier(stop_words)
                return ast.FormValueExpr(field_name, request_var, line)
            elif peek_val == "uploaded":
                self.advance()  # the
                self.advance()  # uploaded
                self.expect_word("file")
                field_name = self.read_identifier({"of"} | stop_words)
                self.expect_word("of")
                request_var = self.read_identifier(stop_words)
                return ast.UploadedFileExpr(field_name, request_var, line)

            # ── Realtime value expressions ──
            elif peek_val == "mouse":
                self.advance()  # the
                self.advance()  # mouse
                axis = self.advance().value.lower()
                return self._maybe_chain_ops(ast.MouseCoordExpr(axis, line), stop_words)
            elif peek_val in ("x", "y") and self.peek(2).value.lower() == "of":
                self.advance()  # the
                axis = self.advance().value.lower()  # x / y
                self.advance()  # of
                name = self.read_identifier(stop_words)
                return self._maybe_chain_ops(ast.SpriteCoordExpr(name, axis, line), stop_words)

            # ── GUI value expressions ──
            elif peek_val == "dropdown":
                self.advance()  # the
                self.advance()  # dropdown
                name = self.read_identifier(stop_words)
                return ast.DropdownValueExpr(name, line)
            elif peek_val == "checkbox":
                self.advance()  # the
                self.advance()  # checkbox
                name = self.read_identifier(stop_words)
                return ast.CheckboxValueExpr(name, line)
            elif peek_val == "radio":
                self.advance()  # the
                self.advance()  # radio
                self.expect_word("group")
                name = self.read_identifier(stop_words)
                return ast.RadioGroupValueExpr(name, line)
            elif peek_val == "slider":
                self.advance()  # the
                self.advance()  # slider
                name = self.read_identifier(stop_words)
                return self._maybe_chain_ops(ast.SliderValueExpr(name, line), stop_words)

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

    _EXPR_OPS = {"plus", "minus", "times", "divided", "remainder",
                  "is", "and", "or", "contains", "has", "joined", "with", "replaced"}

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
        elif self.at_word("the"):
            peek_val = self.peek(1).value.lower()
            if peek_val == "value" or peek_val in THE_EXPRESSIONS:
                return self.parse_value(stop_words)
            else:
                expr_stops = stop_words | self._EXPR_OPS
                name = self.read_identifier(expr_stops)
                left = ast.VarRef(name, line)
        else:
            # Variable reference — read identifier stopping at operators and stop_words
            expr_stops = stop_words | self._EXPR_OPS
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
                    if self.at_word("empty"):
                        self.advance()  # empty
                        left = ast.Compare("not_empty", left, None, line)
                    else:
                        self.expect_word("equal")
                        self.expect_word("to")
                        right = self._parse_operand(stop_words)
                        left = ast.Compare("ne", left, right, line)
                elif self.at_word("empty"):
                    self.advance()  # empty
                    left = ast.Compare("empty", left, None, line)
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

            # String operators
            elif self.at_word("joined"):
                self.advance()  # joined
                self.expect_word("with")
                right = self._parse_operand(stop_words)
                left = ast.BinaryOp("joined_with", left, right, line)
            elif self.at_word("with"):
                saved_with = self.pos
                self.advance()  # with
                if self.at_word("placeholder"):
                    self.advance()  # placeholder
                    placeholder = self.read_identifier({"replaced"} | stop_words)
                    self.expect_word("replaced")
                    self.expect_word("by")
                    new_val = self._parse_operand(stop_words)
                    left = ast.ReplacePlaceholderExpr(left, placeholder, new_val, line)
                    continue
                old_val = self._parse_operand({"replaced"} | stop_words)
                if self.at_word("replaced"):
                    self.advance()  # replaced
                    self.expect_word("by")
                    new_val = self._parse_operand(stop_words)
                    left = ast.ReplaceExpr(left, old_val, new_val, line)
                else:
                    self.pos = saved_with
                    break

            # Collection operators
            elif self.at_word("contains"):
                self.advance()
                right = self.parse_value(stop_words)
                left = ast.ContainsExpr(left, right, line)
            elif self.at_word("has"):
                saved_has = self.pos
                self.advance()  # has
                if self.at_word("the") and self.peek(1).value.lower() == "entry":
                    self.advance()  # the
                    self.advance()  # entry
                    key = self.parse_value(stop_words)
                    left = ast.HasEntryExpr(left, key, line)
                else:
                    self.pos = saved_has
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

    # Special word literals for characters that cannot appear in source
    _SPECIAL_WORDS = {"underscore": "_", "colon": ":", "space": " ", "dash": "-",
                      "exclamation": "!", "question": "?", "semicolon": ";",
                      "at": "@", "ampersand": "&", "newline": "\n", "tab": "\t",
                      "comma": ",", "period": "."}

    def _parse_operand(self, stop_words: set[str]) -> object:
        """Parse a single operand (number, bool, variable ref, or nested expression)."""
        line = self.current().line

        if self.current().kind == TokenKind.NUMBER:
            return self._parse_number(line)
        if self.at_word("negative"):
            self.advance()
            n = self._parse_number(line)
            n.value = -n.value
            return n
        if self.at_word("yes"):
            self.advance()
            return ast.BoolLit(True, line)
        if self.at_word("no"):
            self.advance()
            return ast.BoolLit(False, line)
        if self.current().kind == TokenKind.WORD and self.current().value.lower() in self._SPECIAL_WORDS:
            val = self._SPECIAL_WORDS[self.current().value.lower()]
            self.advance()
            return ast.StringLit(val, line)
        if self.at_word("a") and self.peek(1).value.lower() == "random":
            return self.parse_value(stop_words)
        if self.at_word("the") and self.peek(1).value.lower() == "value":
            self.advance()  # the
            self.advance()  # value
            self.expect_word("of")
            return self._parse_expression(stop_words)
        if self.at_word("the") and self.peek(1).value.lower() in THE_EXPRESSIONS:
            return self.parse_value(stop_words)

        # Variable reference
        expr_stops = stop_words | self._EXPR_OPS
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
        elif word == "clear":
            return self._parse_clear(line)
        elif word == "shuffle":
            self.advance()
            self.expect_word("buttons")
            self.skip_period()
            return ast.ShuffleButtonsStmt(line)
        elif word == "start":
            return self._parse_start(line)
        elif word == "create":
            return self._parse_create(line)
        elif word == "remove":
            return self._parse_remove(line)
        elif word == "for":
            return self._parse_for_each(line)
        elif word == "respond":
            return self._parse_respond(line)
        elif word == "insert":
            return self._parse_insert(line)
        elif word == "select":
            return self._parse_select(line)
        elif word == "update":
            return self._parse_update(line)
        elif word == "delete":
            return self._parse_delete(line)
        elif word == "close":
            return self._parse_close(line)
        elif word == "read":
            return self._parse_read_file(line)
        elif word == "write":
            return self._parse_write_file(line)
        elif word == "enable":
            return self._parse_enable(line)
        elif word == "serve":
            return self._parse_serve(line)
        elif word == "show":
            return self._parse_show(line)
        elif word == "run":
            return self._parse_run(line)
        elif word == "every":
            return self._parse_every(line)
        elif word == "stop":
            return self._parse_stop(line)
        elif word == "when":
            return self._parse_when(line)
        elif word == "before":
            return self._parse_before(line)
        elif word == "send":
            return self._parse_send(line)
        elif word == "broadcast":
            return self._parse_broadcast(line)
        elif word == "arrange":
            return self._parse_arrange(line)
        elif word == "align":
            return self._parse_align(line)
        else:
            raise EppParseError(f"unknown statement '{tok.value}'", line)

    def _open_block(self) -> None:
        """Consume the comma and the optional 'do the following.' that opens a block."""
        self.expect_kind(TokenKind.COMMA)
        if (
            self.at_word("do")
            and self.peek(1).value.lower() == "the"
            and self.peek(2).value.lower() == "following"
        ):
            self.advance()  # do
            self.advance()  # the
            self.advance()  # following
            self.skip_period()

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
        """Let <name> be <value>.  OR  Let <name> be empty."""
        self.advance()  # let
        name = self.read_identifier({"be"})
        self.expect_word("be")
        if self.at_word("empty"):
            self.advance()  # empty
            self.skip_period()
            return ast.LetStmt(name, ast.StringLit("", line), line)
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

        # Check for "Set title to <text>"
        if self.at_word("title"):
            self.advance()  # title
            self.expect_word("to")
            title = self.parse_value()
            self.skip_period()
            return ast.SetTitleStmt(title, line)

        # Check for "Set background color to <color>"
        if self.at_word("background"):
            self.advance()  # background
            self.expect_word("color")
            self.expect_word("to")
            color = self.parse_value()
            self.skip_period()
            return ast.SetBackgroundColorStmt(color, line)

        # Check for "Set text color to <color>"
        if self.at_word("text"):
            self.advance()  # text
            self.expect_word("color")
            self.expect_word("to")
            color = self.parse_value()
            self.skip_period()
            return ast.SetTextColorStmt(color, line)

        # Check for "Set font size to <number>"
        if self.at_word("font"):
            self.advance()  # font
            self.expect_word("size")
            self.expect_word("to")
            size = self.parse_value()
            self.skip_period()
            return ast.SetFontSizeStmt(size, line)

        # Check for "Set content type to <type>"
        if self.at_word("content"):
            self.advance()  # content
            self.expect_word("type")
            self.expect_word("to")
            # Parse content type, replacing "slash" with "/"
            parts: list[str] = []
            while not self.at_kind(TokenKind.PERIOD) and not self.at_kind(TokenKind.EOF):
                word_val = self.advance().value
                if word_val.lower() == "slash":
                    parts.append("/")
                else:
                    parts.append(word_val.lower())
            self.skip_period()
            return ast.SetContentTypeStmt("".join(parts), line)

        # Check for "Set pen color/speed/size to <value>"
        if self.at_word("pen"):
            self.advance()  # pen
            if self.at_word("color"):
                self.advance()  # color
                self.expect_word("to")
                color = self.parse_value()
                self.skip_period()
                return ast.SetPenColorStmt(color, line)
            elif self.at_word("speed"):
                self.advance()  # speed
                self.expect_word("to")
                speed = self.parse_value()
                self.skip_period()
                return ast.SetPenSpeedStmt(speed, line)
            elif self.at_word("size"):
                self.advance()  # size
                self.expect_word("to")
                size = self.parse_value()
                self.skip_period()
                return ast.SetPenSizeStmt(size, line)

        # Check for "Set position of SPRITE to X by Y."
        if self.at_word("position"):
            self.advance()  # position
            self.expect_word("of")
            name = self.read_identifier({"to"})
            self.expect_word("to")
            x = self.parse_value({"by"})
            self.expect_word("by")
            y = self.parse_value()
            self.skip_period()
            return ast.SetSpritePositionStmt(name, x, y, line)

        # Check for "Set the cookie NAME of REQUEST to VALUE."
        if self.at_word("the") and self.peek(1).value.lower() == "cookie":
            self.advance()  # the
            self.advance()  # cookie
            cookie_name = self.read_identifier({"of"})
            self.expect_word("of")
            request_var = self.read_identifier({"to"})
            self.expect_word("to")
            value = self.parse_value()
            self.skip_period()
            return ast.SetCookieStmt(cookie_name, request_var, value, line)

        # Check for "Set the session value KEY in REQUEST to VALUE."
        if self.at_word("the") and self.peek(1).value.lower() == "session":
            self.advance()  # the
            self.advance()  # session
            self.expect_word("value")
            key = self.read_identifier({"in"})
            self.expect_word("in")
            request_var = self.read_identifier({"to"})
            self.expect_word("to")
            value = self.parse_value()
            self.skip_period()
            return ast.SetSessionValueStmt(key, request_var, value, line)

        # Check for "Set item X of LIST to VALUE."
        if self.at_word("item"):
            self.advance()  # item
            index = self._parse_operand({"of"})
            self.expect_word("of")
            list_name = self.read_identifier({"to"})
            self.expect_word("to")
            value = self.parse_value()
            self.skip_period()
            return ast.SetItemStmt(list_name, index, value, line)

        # Check for "Set the entry KEY in DICT to VALUE."
        if self.at_word("the") and self.peek(1).value.lower() == "entry":
            self.advance()  # the
            self.advance()  # entry
            key = self.parse_value({"in"})
            self.expect_word("in")
            dict_name = self.read_identifier({"to"})
            self.expect_word("to")
            value = self.parse_value()
            self.skip_period()
            return ast.SetEntryStmt(dict_name, key, value, line)

        name = self.read_identifier({"to"})
        self.expect_word("to")
        if self.at_word("empty"):
            self.advance()  # empty
            self.skip_period()
            return ast.SetStmt(name, ast.StringLit("", line), line)
        value = self.parse_value()
        self.skip_period()
        return ast.SetStmt(name, value, line)

    def _parse_add(self, line: int) -> object:
        """Add <value> to <name>.  OR  Add button/label/text box (§14). OR Add route."""
        self.advance()  # add

        # Webserver: Add route METHOD PATH to HANDLER.
        if self.at_word("route"):
            self.advance()  # route
            method = self.advance().value.upper()  # GET, POST, etc.
            # Parse path: words until "to", "slash" becomes "/", "param X" becomes ":X"
            path = ""
            params = []
            while not self.at_word("to") and not self.at_kind(TokenKind.PERIOD) and not self.at_kind(TokenKind.EOF):
                word = self.advance().value.lower()
                if word == "slash":
                    path += "/"
                elif word == "param":
                    param_name = self.advance().value.lower()
                    params.append(param_name)
                    path += ":" + param_name
                else:
                    path += word
            if not path:
                path = "/"
            self.expect_word("to")
            handler = self.read_identifier(set(), allow_keywords=True)
            self.skip_period()
            return ast.AddRouteStmt(method, path, handler, line, params)

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

        # GUI: Add dropdown NAME with options A, B, C.
        if self.at_word("dropdown"):
            self.advance()  # dropdown
            name = self.read_identifier({"with"}, allow_keywords=True)
            self.expect_word("with")
            self.expect_word("options")
            options = self._parse_name_list()
            self.skip_period()
            return ast.AddDropdownStmt(name, options, line)

        # GUI: Add table NAME with columns A, B, C.
        if self.at_word("table"):
            self.advance()  # table
            name = self.read_identifier({"with"}, allow_keywords=True)
            self.expect_word("with")
            self.expect_word("columns")
            columns = self._parse_name_list()
            self.skip_period()
            return ast.AddTableStmt(name, columns, line)

        # GUI: Add row to TABLE with values A, B, C.
        if self.at_word("row"):
            self.advance()  # row
            self.expect_word("to")
            table_name = self.read_identifier({"with"}, allow_keywords=True)
            self.expect_word("with")
            self.expect_word("values")
            values = self._parse_arg_list()
            self.skip_period()
            return ast.AddRowStmt(table_name, values, line)

        # GUI: Add checkbox NAME with label TEXT.
        if self.at_word("checkbox"):
            self.advance()  # checkbox
            name = self.read_identifier({"with"}, allow_keywords=True)
            self.expect_word("with")
            self.expect_word("label")
            label = self.parse_value()
            self.skip_period()
            return ast.AddCheckboxStmt(name, label, line)

        # GUI: Add radio group NAME with options A, B, C.
        if self.at_word("radio"):
            self.advance()  # radio
            self.expect_word("group")
            name = self.read_identifier({"with"}, allow_keywords=True)
            self.expect_word("with")
            self.expect_word("options")
            options = self._parse_name_list(keep_case=True)
            self.skip_period()
            return ast.AddRadioGroupStmt(name, options, line)

        # GUI: Add slider NAME from LOW to HIGH.
        if self.at_word("slider"):
            self.advance()  # slider
            name = self.read_identifier({"from"}, allow_keywords=True)
            self.expect_word("from")
            low = self.parse_value({"to"})
            self.expect_word("to")
            high = self.parse_value()
            self.skip_period()
            return ast.AddSliderStmt(name, low, high, line)

        # GUI: Add image NAME from the file PATH.
        if self.at_word("image"):
            self.advance()  # image
            name = self.read_identifier({"from"}, allow_keywords=True)
            self.expect_word("from")
            self.expect_word("the")
            self.expect_word("file")
            file_path = self.parse_value()
            self.skip_period()
            return ast.AddImageStmt(name, file_path, line)

        # GUI: Add menu item ITEM in MENU that calls FN.
        #      Add menu NAME with options A, B, C.
        if self.at_word("menu"):
            self.advance()  # menu
            if self.at_word("item"):
                self.advance()  # item
                item = self.read_identifier({"in"}, allow_keywords=True, keep_case=True)
                self.expect_word("in")
                menu_name = self.read_identifier({"that"}, allow_keywords=True, keep_case=True)
                self.expect_word("that")
                self.expect_word("calls")
                fn_name = self.read_identifier(set(), allow_keywords=True)
                self.skip_period()
                return ast.AddMenuItemStmt(item, menu_name, fn_name, line)
            name = self.read_identifier({"with"}, allow_keywords=True, keep_case=True)
            self.expect_word("with")
            self.expect_word("options")
            options = self._parse_name_list(keep_case=True)
            self.skip_period()
            return ast.AddMenuStmt(name, options, line)

        # GUI: Add spacing N around all widgets.
        if self.at_word("spacing"):
            self.advance()  # spacing
            amount = self.parse_value({"around"})
            self.expect_word("around")
            self.expect_word("all")
            self.expect_word("widgets")
            self.skip_period()
            return ast.AddSpacingStmt(amount, line)

        # Realtime: Add sprite NAME [with image PATH].
        if self.at_word("sprite"):
            self.advance()  # sprite
            name = self.read_identifier({"with"}, allow_keywords=True)
            image = None
            if self.at_word("with"):
                self.advance()  # with
                self.expect_word("image")
                image = self.parse_value()
            self.skip_period()
            return ast.AddSpriteStmt(name, image, line)

        # Realtime: Add canvas NAME with width W and height H.
        if self.at_word("canvas"):
            self.advance()  # canvas
            name = self.read_identifier({"with"}, allow_keywords=True)
            self.expect_word("with")
            self.expect_word("width")
            width = self.parse_value({"and"})
            self.expect_word("and")
            self.expect_word("height")
            height = self.parse_value()
            self.skip_period()
            return ast.AddCanvasStmt(name, width, height, line)

        # Webserver: Add websocket route PATH to HANDLER.
        if self.at_word("websocket"):
            self.advance()  # websocket
            self.expect_word("route")
            path = self._parse_route_path()
            self.expect_word("to")
            handler = self.read_identifier(set(), allow_keywords=True)
            self.skip_period()
            return ast.AddWebsocketRouteStmt(path, handler, line)

        # Arithmetic: Add <value> to <name>.
        value = self.parse_value({"to"})
        self.expect_word("to")
        name = self.read_identifier(set())
        self.skip_period()
        return ast.AddStmt(name, value, line)

    def _parse_route_path(self) -> str:
        """Parse a route path: 'slash' becomes '/', words are joined."""
        path = ""
        while (
            not self.at_word("to")
            and not self.at_kind(TokenKind.PERIOD)
            and not self.at_kind(TokenKind.EOF)
        ):
            word = self.advance().value.lower()
            path += "/" if word == "slash" else word
        return path or "/"

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
        self._open_block()

        branches: list[tuple[object, list[object]]] = []
        body = self._parse_block({"otherwise", "end"})
        branches.append((cond, body))

        else_body: list[object] | None = None

        while self.at_word("otherwise"):
            self.advance()  # otherwise
            if self.at_word("if"):
                self.advance()  # if
                cond = self.parse_condition()
                self._open_block()
                body = self._parse_block({"otherwise", "end"})
                branches.append((cond, body))
            else:
                self._open_block()
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
        self._open_block()

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
        self._open_block()

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

    def _parse_ask(self, line: int) -> object:
        """Ask for <var> with the message <prompt>.
        OR Ask yes or no with the message <prompt>.
        OR Ask for a file to open / to save as."""
        self.advance()  # ask

        # Ask yes or no with the message TEXT.
        if self.at_word("yes"):
            self.advance()  # yes
            self.expect_word("or")
            self.expect_word("no")
            self.expect_word("with")
            self.expect_word("the")
            self.expect_word("message")
            message = self.parse_value()
            self.skip_period()
            return ast.AskYesNoStmt(message, line)

        self.expect_word("for")

        # Ask for a file to open. / Ask for a file to save as.
        if self.at_word("a") and self.peek(1).value.lower() == "file":
            self.advance()  # a
            self.advance()  # file
            self.expect_word("to")
            if self.at_word("save"):
                self.advance()  # save
                if self.at_word("as"):
                    self.advance()  # as
                mode = "save"
            else:
                self.expect_word("open")
                mode = "open"
            self.skip_period()
            return ast.AskFileStmt(mode, line)

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

        self._open_block()
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

    def _parse_open_window(self, line: int) -> object:
        """Open window with title <text>. OR Open a database called NAME."""
        self.advance()  # open

        # Open a database called NAME.
        if self.at_word("a"):
            self.advance()  # a
            self.expect_word("database")
            self.expect_word("called")
            name = self.parse_value()
            self.skip_period()
            return ast.OpenDatabaseStmt(name, line)

        self.expect_word("window")
        self.expect_word("with")
        self.expect_word("title")
        title = self.parse_value()
        self.skip_period()
        return ast.OpenWindowStmt(title, line)

    def _parse_move(self, line: int) -> ast.MoveStmt:
        """Move forward/backward <n> steps  OR  Move to <x> and <y>
        OR  Move sprite <name> by <dx> by <dy>."""
        self.advance()  # move
        if self.at_word("sprite"):
            self.advance()  # sprite
            name = self.read_identifier({"by"}, allow_keywords=True)
            self.expect_word("by")
            dx = self.parse_value({"by"})
            self.expect_word("by")
            dy = self.parse_value()
            self.skip_period()
            return ast.MoveSpriteStmt(name, dx, dy, line)
        if self.at_word("to"):
            self.advance()  # to
            x = self.parse_value({"and"})
            self.expect_word("and")
            y = self.parse_value()
            self.skip_period()
            return ast.MoveToStmt(x, y, line)
        if self.at_word("forward"):
            direction = "forward"
        elif self.at_word("backward"):
            direction = "backward"
        else:
            raise EppParseError("expected 'forward', 'backward', or 'to' after Move", line)
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
        """Draw circle with radius <n>  (turtle)
        OR  Draw rectangle/circle/text ... at <x> by <y> ...  (canvas)."""
        self.advance()  # draw

        # Draw rectangle at X by Y with width W and height H and color C.
        if self.at_word("rectangle"):
            self.advance()  # rectangle
            self.expect_word("at")
            x = self.parse_value({"by"})
            self.expect_word("by")
            y = self.parse_value({"with"})
            self.expect_word("with")
            self.expect_word("width")
            width = self.parse_value({"and"})
            self.expect_word("and")
            self.expect_word("height")
            height = self.parse_value({"and"})
            self.expect_word("and")
            self.expect_word("color")
            color = self.parse_value()
            self.skip_period()
            return ast.DrawRectangleStmt(x, y, width, height, color, line)

        # Draw text TEXT at X by Y with color C.
        if self.at_word("text"):
            self.advance()  # text
            text = self.parse_value({"at"})
            self.expect_word("at")
            x = self.parse_value({"by"})
            self.expect_word("by")
            y = self.parse_value({"with"})
            self.expect_word("with")
            self.expect_word("color")
            color = self.parse_value()
            self.skip_period()
            return ast.DrawCanvasTextStmt(text, x, y, color, line)

        self.expect_word("circle")

        # Draw circle at X by Y with radius R and color C.
        if self.at_word("at"):
            self.advance()  # at
            x = self.parse_value({"by"})
            self.expect_word("by")
            y = self.parse_value({"with"})
            self.expect_word("with")
            self.expect_word("radius")
            radius = self.parse_value({"and"})
            self.expect_word("and")
            self.expect_word("color")
            color = self.parse_value()
            self.skip_period()
            return ast.DrawCanvasCircleStmt(x, y, radius, color, line)

        self.expect_word("with")
        self.expect_word("radius")
        radius = self.parse_value()
        self.skip_period()
        return ast.DrawCircleStmt(radius, line)

    def _parse_wait(self, line: int) -> object:
        """Wait for close. OR Wait for connections. OR Wait N seconds."""
        self.advance()  # wait

        # Wait N seconds.
        if self.current().kind == TokenKind.NUMBER:
            seconds = self.parse_value({"seconds"})
            self.expect_word("seconds")
            self.skip_period()
            return ast.WaitSecondsStmt(seconds, line)

        self.expect_word("for")
        if self.at_word("connections"):
            self.advance()
            self.skip_period()
            return ast.WaitForConnectionsStmt(line)
        self.expect_word("close")
        self.skip_period()
        return ast.WaitForCloseStmt(line)


    def _parse_clear(self, line: int) -> object:
        """Clear window. OR Clear text box NAME. OR Clear table NAME."""
        self.advance()  # clear

        if self.at_word("text"):
            self.advance()  # text
            self.expect_word("box")
            name = self.read_identifier(set(), allow_keywords=True)
            self.skip_period()
            return ast.ClearTextBoxStmt(name, line)

        if self.at_word("table"):
            self.advance()  # table
            name = self.read_identifier(set(), allow_keywords=True)
            self.skip_period()
            return ast.ClearTableStmt(name, line)

        if self.at_word("canvas"):
            self.advance()  # canvas
            self.skip_period()
            return ast.ClearCanvasStmt(line)

        self.expect_word("window")
        self.skip_period()
        return ast.ClearWindowStmt(line)


    def _parse_start(self, line: int) -> object:
        """Start a <kind> game. OR Start a webserver on port N.
        OR Start a session for REQUEST."""
        self.advance()  # start
        self.expect_word("a")

        if self.at_word("webserver"):
            self.advance()  # webserver
            self.expect_word("on")
            self.expect_word("port")
            port = self.parse_value()
            self.skip_period()
            return ast.StartWebserverStmt(port, line)

        if self.at_word("session"):
            self.advance()  # session
            self.expect_word("for")
            request_var = self.read_identifier(set())
            self.skip_period()
            return ast.StartSessionStmt(request_var, line)

        # Start a <kind> game.
        words: list[str] = []
        while (
            not self.at_word("game")
            and not self.at_kind(TokenKind.PERIOD)
            and not self.at_kind(TokenKind.EOF)
        ):
            words.append(self.advance().value.lower())
        self.expect_word("game")
        self.skip_period()
        game_type = " ".join(words)
        if game_type not in _GAME_TYPES:
            known = ", ".join(sorted(_GAME_TYPES))
            raise EppParseError(f"unknown game {game_type!r}, expected one of {known}", line)
        return ast.StartGameStmt(game_type, line)

    # ── Data Structure Parsers ──────────────────────────────────────

    def _parse_create(self, line: int) -> object:
        """Create a list/dictionary/table called <name>."""
        self.advance()  # create
        self.expect_word("a")
        if self.at_word("list"):
            self.advance()  # list
            self.expect_word("called")
            name = self.read_identifier(set())
            self.skip_period()
            return ast.CreateListStmt(name, line)
        elif self.at_word("dictionary"):
            self.advance()  # dictionary
            self.expect_word("called")
            name = self.read_identifier(set())
            self.skip_period()
            return ast.CreateDictStmt(name, line)
        elif self.at_word("table"):
            self.advance()  # table
            self.expect_word("called")
            table_name = self.read_identifier({"with"})
            self.expect_word("with")
            self.expect_word("columns")
            columns = self._parse_name_list()
            self.skip_period()
            return ast.CreateTableStmt(table_name, columns, line)
        else:
            raise EppParseError("expected 'list', 'dictionary', or 'table' after 'Create a'", line)

    def _parse_remove(self, line: int) -> object:
        """Remove item/value/entry from list/dict."""
        self.advance()  # remove

        if self.at_word("sprite"):
            self.advance()  # sprite
            name = self.read_identifier(set(), allow_keywords=True)
            self.skip_period()
            return ast.RemoveSpriteStmt(name, line)

        if self.at_word("item"):
            self.advance()  # item
            index = self._parse_operand({"from"})
            self.expect_word("from")
            name = self.read_identifier(set())
            self.skip_period()
            return ast.RemoveItemStmt(name, index, line)

        if self.at_word("the") and self.peek(1).value.lower() == "entry":
            self.advance()  # the
            self.advance()  # entry
            key = self.parse_value({"from"})
            self.expect_word("from")
            name = self.read_identifier(set())
            self.skip_period()
            return ast.RemoveEntryStmt(name, key, line)

        # Remove VALUE from LIST
        value = self.parse_value({"from"})
        self.expect_word("from")
        name = self.read_identifier(set())
        self.skip_period()
        return ast.RemoveValueStmt(name, value, line)

    def _parse_for_each(self, line: int) -> ast.ForEachStmt:
        """For each VAR in LIST, ... End for each.
        For each KEY and VALUE in DICT, ... End for each."""
        self.advance()  # for
        self.expect_word("each")
        var_name = self.read_identifier({"in", "and"}, allow_keywords=True)
        value_name = None
        if self.at_word("and"):
            self.advance()  # and
            value_name = self.read_identifier({"in"}, allow_keywords=True)
        self.expect_word("in")
        list_name = self.read_identifier(set(), allow_keywords=True)
        self._open_block()

        body = self._parse_block({"end"})

        if not self.at_word("end"):
            raise EppParseError("expected 'End for each' to close the for each block", self.current().line)
        self.advance()  # end
        self.expect_word("for")
        self.expect_word("each")
        self.skip_period()

        return ast.ForEachStmt(var_name, list_name, body, line, value_name)

    # ── Webserver Parsers ───────────────────────────────────────────

    def _parse_respond(self, line: int) -> ast.RespondWithStmt:
        """Respond with VALUE. OR Respond with VALUE and status CODE."""
        self.advance()  # respond
        self.expect_word("with")
        value = self.parse_value({"and"})
        status_code = None
        if self.at_word("and"):
            self.advance()  # and
            self.expect_word("status")
            status_code = self.parse_value()
        self.skip_period()
        return ast.RespondWithStmt(value, status_code, line)

    # ── Database Parsers ────────────────────────────────────────────

    def _parse_name_list(self, keep_case: bool = False) -> list[str]:
        """Parse a name list like: col1, col2, and col3 or just col1."""
        names: list[str] = []
        name = self.read_identifier({"and"}, allow_keywords=True, keep_case=keep_case)
        names.append(name)

        while self.at_kind(TokenKind.COMMA):
            next_tok = self.peek(1)
            if next_tok.kind == TokenKind.WORD and next_tok.value.lower() == "and":
                self.advance()  # comma
                self.advance()  # and
                name = self.read_identifier(set(), allow_keywords=True, keep_case=keep_case)
                names.append(name)
                break
            self.advance()  # comma
            name = self.read_identifier({"and"}, allow_keywords=True, keep_case=keep_case)
            names.append(name)

        if self.at_word("and"):
            self.advance()
            name = self.read_identifier(set(), allow_keywords=True, keep_case=keep_case)
            names.append(name)

        return names

    def _parse_insert(self, line: int) -> ast.InsertRowStmt:
        """Insert into TABLE the values VAL1, VAL2, and VAL3."""
        self.advance()  # insert
        self.expect_word("into")
        table_name = self.read_identifier({"the"})
        self.expect_word("the")
        self.expect_word("values")
        values = self._parse_arg_list()
        self.skip_period()
        return ast.InsertRowStmt(table_name, values, line)

    def _parse_where_clause(self) -> tuple[str, str, object]:
        """Parse: where COLUMN is equal to / is greater than / etc. VALUE"""
        self.expect_word("where")
        column = self.read_identifier({"is"})
        self.expect_word("is")

        if self.at_word("equal"):
            self.advance()
            self.expect_word("to")
            op = "eq"
        elif self.at_word("not"):
            self.advance()
            self.expect_word("equal")
            self.expect_word("to")
            op = "ne"
        elif self.at_word("greater"):
            self.advance()
            self.expect_word("than")
            if self.at_word("or"):
                self.advance()
                self.expect_word("equal")
                self.expect_word("to")
                op = "ge"
            else:
                op = "gt"
        elif self.at_word("less"):
            self.advance()
            self.expect_word("than")
            if self.at_word("or"):
                self.advance()
                self.expect_word("equal")
                self.expect_word("to")
                op = "le"
            else:
                op = "lt"
        else:
            raise EppParseError("expected comparison operator after 'is'", self.current().line)

        value = self.parse_value({"and"})
        return column, op, value

    def _parse_select(self, line: int) -> ast.SelectStmt:
        """Select from TABLE [where ...] and store in VAR."""
        self.advance()  # select
        self.expect_word("from")
        table_name = self.read_identifier({"where", "and"})

        where_col = where_op = where_val = None
        if self.at_word("where"):
            where_col, where_op, where_val = self._parse_where_clause()

        self.expect_word("and")
        self.expect_word("store")
        self.expect_word("in")
        store_in = self.read_identifier(set())
        self.skip_period()
        return ast.SelectStmt(table_name, where_col, where_op, where_val, store_in, line)

    def _parse_update(self, line: int) -> ast.UpdateRowStmt:
        """Update TABLE set COLUMN to VALUE where COLUMN is equal to VALUE."""
        self.advance()  # update
        table_name = self.read_identifier({"set"})
        self.expect_word("set")
        set_column = self.read_identifier({"to"})
        self.expect_word("to")
        set_value = self.parse_value({"where"})
        where_col, where_op, where_val = self._parse_where_clause()
        self.skip_period()
        return ast.UpdateRowStmt(table_name, set_column, set_value, where_col, where_op, where_val, line)

    def _parse_delete(self, line: int) -> ast.DeleteRowStmt:
        """Delete from TABLE where COLUMN is equal to VALUE."""
        self.advance()  # delete
        self.expect_word("from")
        table_name = self.read_identifier({"where"})
        where_col, where_op, where_val = self._parse_where_clause()
        self.skip_period()
        return ast.DeleteRowStmt(table_name, where_col, where_op, where_val, line)

    def _parse_close(self, line: int) -> ast.CloseDatabaseStmt:
        """Close the database."""
        self.advance()  # close
        self.expect_word("the")
        self.expect_word("database")
        self.skip_period()
        return ast.CloseDatabaseStmt(line)


    # ── File I/O Parsers ─────────────────────────────────────────────

    def _parse_read_file(self, line: int) -> ast.ReadFileStmt:
        """Read the file PATH and store it in VAR."""
        self.advance()  # read
        self.expect_word("the")
        self.expect_word("file")
        file_path = self.parse_value({"and"})
        self.expect_word("and")
        self.expect_word("store")
        self.expect_word("it")
        self.expect_word("in")
        store_in = self.read_identifier(set())
        self.skip_period()
        return ast.ReadFileStmt(file_path, store_in, line)

    def _parse_write_file(self, line: int) -> ast.WriteFileStmt:
        """Write VALUE to the file PATH."""
        self.advance()  # write
        value = self.parse_value({"to"})
        self.expect_word("to")
        self.expect_word("the")
        self.expect_word("file")
        file_path = self.parse_value()
        self.skip_period()
        return ast.WriteFileStmt(value, file_path, line)

    # ── Webserver Extension Parsers ────────────────────────────────

    def _parse_enable(self, line: int) -> ast.EnableCORSStmt:
        """Enable CORS."""
        self.advance()  # enable
        self.expect_word("cors")
        self.skip_period()
        return ast.EnableCORSStmt(line)

    def _parse_serve(self, line: int) -> ast.ServeStaticStmt:
        """Serve static files from the folder FOLDER."""
        self.advance()  # serve
        self.expect_word("static")
        self.expect_word("files")
        self.expect_word("from")
        self.expect_word("the")
        self.expect_word("folder")
        folder = self.parse_value()
        self.skip_period()
        return ast.ServeStaticStmt(folder, line)

    # ── GUI Extension Parsers ──────────────────────────────────────

    def _parse_show(self, line: int) -> object:
        """Show message TEXT. OR Show error TEXT."""
        self.advance()  # show
        if self.at_word("message"):
            self.advance()  # message
            text = self.parse_value()
            self.skip_period()
            return ast.ShowMessageStmt(text, line)
        elif self.at_word("error"):
            self.advance()  # error
            text = self.parse_value()
            self.skip_period()
            return ast.ShowErrorStmt(text, line)
        raise EppParseError("expected 'message' or 'error' after 'Show'", line)

    def _parse_run(self, line: int) -> object:
        """Run <function> in background. OR Run the command VALUE [in background]."""
        self.advance()  # run
        if self.at_word("the"):
            saved = self.pos
            self.advance()  # the
            if self.at_word("command"):
                self.advance()  # command
                command = self.parse_value({"in"})
                background = False
                if self.at_word("in"):
                    self.advance()  # in
                    self.expect_word("background")
                    background = True
                self.skip_period()
                return ast.RunCommandStmt(command, background, line)
            self.pos = saved  # backtrack
        name = self.read_identifier({"in"}, allow_keywords=True)
        self.expect_word("in")
        self.expect_word("background")
        self.skip_period()
        return ast.RunInBackgroundStmt(name, line)


    # ── Realtime Parsers ───────────────────────────────────────────

    def _parse_every(self, line: int) -> ast.EveryStmt:
        """Every N milliseconds, do the following. ... End every."""
        self.advance()  # every
        interval = self.parse_value({"milliseconds", "seconds"})
        if self.at_word("seconds"):
            self.advance()  # seconds
            interval = ast.BinaryOp("times", interval, ast.NumberLit(1000.0, line), line)
        else:
            self.expect_word("milliseconds")
        self._open_block()

        body = self._parse_block({"end"})

        if not self.at_word("end"):
            raise EppParseError("expected 'End every' to close the every block", self.current().line)
        self.advance()  # end
        self.expect_word("every")
        self.skip_period()
        return ast.EveryStmt(interval, body, line)

    def _parse_stop(self, line: int) -> ast.StopTickingStmt:
        """Stop ticking."""
        self.advance()  # stop
        self.expect_word("ticking")
        self.skip_period()
        return ast.StopTickingStmt(line)

    def _parse_when(self, line: int) -> object:
        """When key K is pressed, ... End when.  OR  When the mouse is clicked, ... End when."""
        self.advance()  # when

        if self.at_word("key"):
            self.advance()  # key
            key = self.read_identifier({"is"})
            self.expect_word("is")
            self.expect_word("pressed")
            body = self._parse_when_body()
            return ast.WhenKeyStmt(key, body, line)

        self.expect_word("the")
        self.expect_word("mouse")
        self.expect_word("is")
        if self.at_word("moved"):
            event = "moved"
        elif self.at_word("clicked"):
            event = "clicked"
        else:
            raise EppParseError("expected 'clicked' or 'moved' after 'the mouse is'", line)
        self.advance()
        body = self._parse_when_body()
        return ast.WhenMouseStmt(event, body, line)

    def _parse_when_body(self) -> list[object]:
        """Parse the block of a When statement, closed by 'End when.'."""
        self._open_block()
        body = self._parse_block({"end"})
        if not self.at_word("end"):
            raise EppParseError("expected 'End when' to close the when block", self.current().line)
        self.advance()  # end
        self.expect_word("when")
        self.skip_period()
        return body

    # ── Web Parsers ────────────────────────────────────────────────

    def _parse_before(self, line: int) -> ast.BeforeRequestStmt:
        """Before every request, do the following. ... End before."""
        self.advance()  # before
        self.expect_word("every")
        self.expect_word("request")
        self._open_block()

        body = self._parse_block({"end"})

        if not self.at_word("end"):
            raise EppParseError("expected 'End before' to close the before block", self.current().line)
        self.advance()  # end
        self.expect_word("before")
        self.skip_period()
        return ast.BeforeRequestStmt(body, line)

    def _parse_send(self, line: int) -> ast.SendToConnectionStmt:
        """Send VALUE to CONNECTION."""
        self.advance()  # send
        value = self.parse_value({"to"})
        self.expect_word("to")
        connection = self.read_identifier(set())
        self.skip_period()
        return ast.SendToConnectionStmt(value, connection, line)

    def _parse_broadcast(self, line: int) -> ast.BroadcastStmt:
        """Broadcast VALUE to all connections."""
        self.advance()  # broadcast
        value = self.parse_value({"to"})
        self.expect_word("to")
        self.expect_word("all")
        self.expect_word("connections")
        self.skip_period()
        return ast.BroadcastStmt(value, line)

    # ── Layout Parsers ─────────────────────────────────────────────

    def _parse_arrange(self, line: int) -> ast.ArrangeGridStmt:
        """Arrange widgets in a grid with N columns."""
        self.advance()  # arrange
        self.expect_word("widgets")
        self.expect_word("in")
        self.expect_word("a")
        self.expect_word("grid")
        self.expect_word("with")
        columns = self.parse_value({"columns"})
        self.expect_word("columns")
        self.skip_period()
        return ast.ArrangeGridStmt(columns, line)

    def _parse_align(self, line: int) -> ast.AlignWidgetStmt:
        """Align label NAME to the center."""
        self.advance()  # align
        if self.at_word("text"):
            self.advance()  # text
            self.expect_word("box")
            kind = "text box"
        elif self.at_word("button"):
            self.advance()  # button
            kind = "button"
        elif self.at_word("label"):
            self.advance()  # label
            kind = "label"
        else:
            raise EppParseError("expected 'label', 'button', or 'text box' after Align", line)
        name = self.read_identifier({"to"}, allow_keywords=True)
        self.expect_word("to")
        self.expect_word("the")
        alignment = self.advance().value.lower()
        self.skip_period()
        return ast.AlignWidgetStmt(kind, name, alignment, line)


def parse(tokens: list[Token]) -> list[object]:
    """Parse a token list into a list of AST nodes."""
    parser = Parser(tokens)
    return parser.parse_program()
