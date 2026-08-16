"""AST node definitions for E++."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


# ── Value / Expression Nodes ──────────────────────────────────────────

@dataclass
class NumberLit:
    value: float
    line: int


@dataclass
class BoolLit:
    value: bool
    line: int


@dataclass
class StringLit:
    value: str
    line: int


@dataclass
class VarRef:
    name: str
    line: int


@dataclass
class RandomBetween:
    low: Any  # expression node
    high: Any  # expression node
    line: int


@dataclass
class BinaryOp:
    op: str  # plus, minus, times, divided_by, remainder
    left: Any
    right: Any
    line: int


@dataclass
class Compare:
    op: str  # eq, ne, gt, lt, ge, le
    left: Any
    right: Any
    line: int


@dataclass
class LogicOp:
    op: str  # and, or
    left: Any
    right: Any
    line: int


@dataclass
class NotOp:
    operand: Any
    line: int


# ── Statement Nodes ──────────────────────────────────────────────────

@dataclass
class LetStmt:
    name: str
    value: Any
    line: int


@dataclass
class SetStmt:
    name: str
    value: Any
    line: int


@dataclass
class AddStmt:
    name: str
    value: Any
    line: int


@dataclass
class SubtractStmt:
    name: str
    value: Any
    line: int


@dataclass
class MultiplyStmt:
    name: str
    value: Any
    line: int


@dataclass
class DivideStmt:
    name: str
    value: Any
    line: int


@dataclass
class IfStmt:
    branches: list[tuple[Any, list[Any]]]  # list of (condition, body)
    else_body: list[Any] | None
    line: int


@dataclass
class WhileStmt:
    condition: Any
    body: list[Any]
    line: int


@dataclass
class RepeatStmt:
    count: Any
    body: list[Any]
    line: int


@dataclass
class SayStmt:
    value: Any
    line: int


@dataclass
class AskStmt:
    var_name: str
    prompt: Any  # expression for the message
    line: int


@dataclass
class DefineStmt:
    name: str
    params: list[str]
    body: list[Any]
    line: int


@dataclass
class CallStmt:
    name: str
    args: list[Any]
    store_in: str | None  # variable name to store result, or None
    line: int


@dataclass
class ReturnStmt:
    value: Any
    line: int


@dataclass
class NoteStmt:
    text: str
    line: int


# ── §14 Visual Statements ───────────────────────────────────────────

@dataclass
class OpenWindowStmt:
    title: Any
    line: int


@dataclass
class SetWindowSizeStmt:
    width: Any
    height: Any
    line: int


@dataclass
class AddLabelStmt:
    text: Any
    line: int


@dataclass
class AddButtonStmt:
    text: Any
    fn_name: str
    line: int


@dataclass
class AddTextBoxStmt:
    name: str
    line: int


@dataclass
class WaitForCloseStmt:
    line: int


@dataclass
class MoveStmt:
    direction: str  # forward, backward
    amount: Any
    line: int


@dataclass
class TurnStmt:
    direction: str  # left, right
    degrees: Any
    line: int


@dataclass
class PenStmt:
    action: str  # up, down
    line: int


@dataclass
class SetPenColorStmt:
    color: Any
    line: int


@dataclass
class DrawCircleStmt:
    radius: Any
    line: int
