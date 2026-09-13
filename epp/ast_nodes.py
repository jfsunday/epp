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
class RandomDecimalBetween:
    low: Any
    high: Any
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
class ClearWindowStmt:
    line: int


@dataclass
class SetTitleStmt:
    title: Any
    line: int


@dataclass
class ShuffleButtonsStmt:
    line: int


@dataclass
class MoveStmt:
    direction: str  # forward, backward
    amount: Any
    line: int


@dataclass
class MoveToStmt:
    x: Any
    y: Any
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
class SetPenSpeedStmt:
    speed: Any
    line: int


@dataclass
class SetPenSizeStmt:
    size: Any
    line: int


@dataclass
class DrawCircleStmt:
    radius: Any
    line: int


@dataclass
class SetBackgroundColorStmt:
    color: Any
    line: int


@dataclass
class SetTextColorStmt:
    color: Any
    line: int


@dataclass
class SetFontSizeStmt:
    size: Any
    line: int


# ── Data Structure Statements ────────────────────────────────────────

@dataclass
class CreateListStmt:
    name: str
    line: int


@dataclass
class CreateDictStmt:
    name: str
    line: int


@dataclass
class RemoveItemStmt:
    list_name: str
    index: Any
    line: int


@dataclass
class RemoveValueStmt:
    list_name: str
    value: Any
    line: int


@dataclass
class RemoveEntryStmt:
    dict_name: str
    key: Any
    line: int


@dataclass
class SetEntryStmt:
    dict_name: str
    key: Any
    value: Any
    line: int


@dataclass
class SetItemStmt:
    list_name: str
    index: Any
    value: Any
    line: int


@dataclass
class ForEachStmt:
    var_name: str
    iterable_name: str
    body: list[Any]
    line: int
    value_name: str | None = None


# ── Data Structure Expressions ──────────────────────────────────────

@dataclass
class ItemOfExpr:
    index: Any
    list_name: str
    line: int


@dataclass
class LengthOfExpr:
    name: str
    line: int


@dataclass
class KeysOfExpr:
    name: str
    line: int


@dataclass
class EntryInExpr:
    key: Any
    dict_name: str
    line: int


@dataclass
class ContainsExpr:
    collection: Any
    value: Any
    line: int


@dataclass
class HasEntryExpr:
    collection: Any
    key: Any
    line: int


# ── Webserver Statements ─────────────────────────────────────────────

@dataclass
class StartWebserverStmt:
    port: Any
    line: int


@dataclass
class AddRouteStmt:
    method: str
    path: str
    handler_name: str
    line: int
    params: list[str] = field(default_factory=list)


@dataclass
class RespondWithStmt:
    value: Any
    status_code: Any | None
    line: int


@dataclass
class WaitForConnectionsStmt:
    line: int


# ── Database Statements ─────────────────────────────────────────────

@dataclass
class OpenDatabaseStmt:
    name: Any
    line: int


@dataclass
class CloseDatabaseStmt:
    line: int


@dataclass
class CreateTableStmt:
    table_name: str
    columns: list[str]
    line: int


@dataclass
class InsertRowStmt:
    table_name: str
    values: list[Any]
    line: int


@dataclass
class SelectStmt:
    table_name: str
    where_column: str | None
    where_op: str | None
    where_value: Any | None
    store_in: str
    line: int


@dataclass
class UpdateRowStmt:
    table_name: str
    set_column: str
    set_value: Any
    where_column: str
    where_op: str
    where_value: Any
    line: int


@dataclass
class DeleteRowStmt:
    table_name: str
    where_column: str
    where_op: str
    where_value: Any
    line: int


# ── ML Expressions ──────────────────────────────────────────────────

@dataclass
class MeanOfExpr:
    name: str
    line: int


@dataclass
class SumOfExpr:
    name: str
    line: int


@dataclass
class MinOfExpr:
    name: str
    line: int


@dataclass
class MaxOfExpr:
    name: str
    line: int


@dataclass
class DotProductExpr:
    left_name: str
    right_name: str
    line: int


@dataclass
class ExponentialOfExpr:
    value: Any
    line: int


@dataclass
class LogarithmOfExpr:
    value: Any
    line: int


# ── Game Statements ───────────────────────────────────────────────────

@dataclass
class StartGameStmt:
    game_type: str  # "jump and run"
    line: int


# ── File I/O Statements ────────────────────────────────────────────

@dataclass
class ReadFileStmt:
    file_path: Any
    store_in: str
    line: int


@dataclass
class WriteFileStmt:
    value: Any
    file_path: Any
    line: int


# ── Webserver Extension Statements ─────────────────────────────────

@dataclass
class SetContentTypeStmt:
    content_type: str
    line: int


@dataclass
class EnableCORSStmt:
    line: int


@dataclass
class ServeStaticStmt:
    folder: Any
    line: int


# ── String Operation Expressions ───────────────────────────────────

@dataclass
class LowercaseOfExpr:
    value: Any
    line: int


@dataclass
class UppercaseOfExpr:
    value: Any
    line: int


@dataclass
class SplitByExpr:
    value: Any
    delimiter: Any
    line: int


@dataclass
class SubstringOfExpr:
    value: Any
    start: Any
    end: Any
    line: int


@dataclass
class PositionOfExpr:
    needle: Any
    haystack: Any
    line: int


@dataclass
class ReplaceExpr:
    text: Any
    old: Any
    new: Any
    line: int


# ── Timestamp Expressions ──────────────────────────────────────────

@dataclass
class CurrentTimestampExpr:
    line: int


@dataclass
class CurrentDateExpr:
    line: int


@dataclass
class CurrentTimeExpr:
    line: int


# ── Random Item Expression ─────────────────────────────────────────

@dataclass
class RandomItemExpr:
    list_name: str
    line: int


# ── Type Conversion Expressions ────────────────────────────────────

@dataclass
class NumberOfExpr:
    value: Any
    line: int


@dataclass
class TextOfExpr:
    value: Any
    line: int


# ── Request Access Expressions ─────────────────────────────────────

@dataclass
class BodyOfExpr:
    var_name: str
    line: int


@dataclass
class PathParamExpr:
    param_name: str
    var_name: str
    line: int


@dataclass
class QueryParamExpr:
    param_name: str
    var_name: str
    line: int


# ── GUI Extension Statements ──────────────────────────────────────

@dataclass
class AddDropdownStmt:
    name: str
    options: list[str]
    line: int


@dataclass
class DropdownValueExpr:
    name: str
    line: int


@dataclass
class AddTableStmt:
    name: str
    columns: list[str]
    line: int


@dataclass
class AddRowStmt:
    table_name: str
    values: list[Any]
    line: int


@dataclass
class ClearTableStmt:
    name: str
    line: int


@dataclass
class WaitSecondsStmt:
    seconds: Any
    line: int


@dataclass
class ClearTextBoxStmt:
    name: str
    line: int


@dataclass
class ShowMessageStmt:
    text: Any
    line: int


@dataclass
class ShowErrorStmt:
    text: Any
    line: int


# ── Background Execution ─────────────────────────────────────────

@dataclass
class RunInBackgroundStmt:
    name: str
    line: int


@dataclass
class RunCommandStmt:
    command: Any
    background: bool
    line: int
