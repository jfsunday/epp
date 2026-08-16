"""Tree-walking interpreter for E++."""

from __future__ import annotations
import random as _random
from . import ast_nodes as ast
from .environment import Environment
from .errors import EppRuntimeError
from .builtins import format_value, ask_auto_detect, random_between


class _ReturnSignal(Exception):
    """Internal signal for Return statements."""
    def __init__(self, value: object):
        self.value = value


class Interpreter:
    def __init__(self):
        self.globals = Environment()
        self.functions: dict[str, ast.DefineStmt] = {}
        self.output: list[str] = []
        self._say_fn = print
        self._input_fn = input
        self._visuals = None  # lazy-init

    def run(self, statements: list[object]) -> None:
        """Execute a list of top-level statements."""
        for stmt in statements:
            self._exec(stmt, self.globals)

    def _exec(self, node: object, env: Environment) -> None:
        method_name = f"_exec_{type(node).__name__}"
        method = getattr(self, method_name, None)
        if method is None:
            raise EppRuntimeError(
                f"unknown statement type {type(node).__name__}",
                getattr(node, 'line', None)
            )
        method(node, env)

    def _eval(self, node: object, env: Environment) -> object:
        method_name = f"_eval_{type(node).__name__}"
        method = getattr(self, method_name, None)
        if method is None:
            raise EppRuntimeError(
                f"unknown expression type {type(node).__name__}",
                getattr(node, 'line', None)
            )
        return method(node, env)

    # ── Expression Evaluators ────────────────────────────────────────

    def _eval_NumberLit(self, node: ast.NumberLit, env: Environment) -> float:
        return node.value

    def _eval_BoolLit(self, node: ast.BoolLit, env: Environment) -> bool:
        return node.value

    def _eval_StringLit(self, node: ast.StringLit, env: Environment) -> str:
        return node.value

    def _eval_VarRef(self, node: ast.VarRef, env: Environment) -> object:
        return env.get(node.name, node.line)

    def _eval_RandomBetween(self, node: ast.RandomBetween, env: Environment) -> float:
        low = self._eval(node.low, env)
        high = self._eval(node.high, env)
        self._check_number(low, "random lower bound", node.line)
        self._check_number(high, "random upper bound", node.line)
        return random_between(low, high)

    def _eval_BinaryOp(self, node: ast.BinaryOp, env: Environment) -> object:
        left = self._eval(node.left, env)
        right = self._eval(node.right, env)

        if node.op == "plus":
            # Number + Number = Number; anything with str = concatenation
            if isinstance(left, str) or isinstance(right, str):
                return format_value(left) + " " + format_value(right) if not isinstance(left, str) else str(left) + " " + format_value(right) if not isinstance(right, str) else str(left) + " " + str(right)
            self._check_number(left, "left side of plus", node.line)
            self._check_number(right, "right side of plus", node.line)
            return left + right

        self._check_number(left, f"left side of {node.op}", node.line)
        self._check_number(right, f"right side of {node.op}", node.line)

        if node.op == "minus":
            return left - right
        elif node.op == "times":
            return left * right
        elif node.op == "divided_by":
            if right == 0:
                raise EppRuntimeError("cannot divide by zero", node.line)
            return left / right
        elif node.op == "remainder":
            if right == 0:
                raise EppRuntimeError("cannot divide by zero", node.line)
            return left % right
        else:
            raise EppRuntimeError(f"unknown operator {node.op}", node.line)

    def _eval_Compare(self, node: ast.Compare, env: Environment) -> bool:
        left = self._eval(node.left, env)
        right = self._eval(node.right, env)

        if node.op == "eq":
            return left == right
        elif node.op == "ne":
            return left != right
        elif node.op == "gt":
            return left > right
        elif node.op == "lt":
            return left < right
        elif node.op == "ge":
            return left >= right
        elif node.op == "le":
            return left <= right
        else:
            raise EppRuntimeError(f"unknown comparison {node.op}", node.line)

    def _eval_LogicOp(self, node: ast.LogicOp, env: Environment) -> bool:
        left = self._eval(node.left, env)
        if node.op == "and":
            if not left:
                return False
            return bool(self._eval(node.right, env))
        elif node.op == "or":
            if left:
                return True
            return bool(self._eval(node.right, env))
        raise EppRuntimeError(f"unknown logic op {node.op}", node.line)

    def _eval_NotOp(self, node: ast.NotOp, env: Environment) -> bool:
        return not self._eval(node.operand, env)

    # ── Statement Executors ──────────────────────────────────────────

    def _exec_LetStmt(self, node: ast.LetStmt, env: Environment) -> None:
        value = self._eval(node.value, env)
        env.define(node.name, value)

    def _exec_SetStmt(self, node: ast.SetStmt, env: Environment) -> None:
        value = self._eval(node.value, env)
        env.set(node.name, value, node.line)

    def _exec_AddStmt(self, node: ast.AddStmt, env: Environment) -> None:
        current = env.get(node.name, node.line)
        amount = self._eval(node.value, env)
        self._check_number(current, f"variable '{node.name}'", node.line)
        self._check_number(amount, "value to add", node.line)
        env.set(node.name, current + amount, node.line)

    def _exec_SubtractStmt(self, node: ast.SubtractStmt, env: Environment) -> None:
        current = env.get(node.name, node.line)
        amount = self._eval(node.value, env)
        self._check_number(current, f"variable '{node.name}'", node.line)
        self._check_number(amount, "value to subtract", node.line)
        env.set(node.name, current - amount, node.line)

    def _exec_MultiplyStmt(self, node: ast.MultiplyStmt, env: Environment) -> None:
        current = env.get(node.name, node.line)
        amount = self._eval(node.value, env)
        self._check_number(current, f"variable '{node.name}'", node.line)
        self._check_number(amount, "value to multiply by", node.line)
        env.set(node.name, current * amount, node.line)

    def _exec_DivideStmt(self, node: ast.DivideStmt, env: Environment) -> None:
        current = env.get(node.name, node.line)
        amount = self._eval(node.value, env)
        self._check_number(current, f"variable '{node.name}'", node.line)
        self._check_number(amount, "value to divide by", node.line)
        if amount == 0:
            raise EppRuntimeError("cannot divide by zero", node.line)
        env.set(node.name, current / amount, node.line)

    def _exec_IfStmt(self, node: ast.IfStmt, env: Environment) -> None:
        for condition, body in node.branches:
            if self._eval(condition, env):
                for stmt in body:
                    self._exec(stmt, env)
                return
        if node.else_body is not None:
            for stmt in node.else_body:
                self._exec(stmt, env)

    def _exec_WhileStmt(self, node: ast.WhileStmt, env: Environment) -> None:
        while self._eval(node.condition, env):
            for stmt in node.body:
                self._exec(stmt, env)

    def _exec_RepeatStmt(self, node: ast.RepeatStmt, env: Environment) -> None:
        count = self._eval(node.count, env)
        self._check_number(count, "repeat count", node.line)
        for _ in range(int(count)):
            for stmt in node.body:
                self._exec(stmt, env)

    def _exec_SayStmt(self, node: ast.SayStmt, env: Environment) -> None:
        value = self._eval(node.value, env)
        text = format_value(value)
        self.output.append(text)
        self._say_fn(text)

    def _exec_AskStmt(self, node: ast.AskStmt, env: Environment) -> None:
        prompt = self._eval(node.prompt, env)
        prompt_str = format_value(prompt) + " "
        value = ask_auto_detect(prompt_str, input_fn=self._input_fn)
        if env.has(node.var_name):
            env.set(node.var_name, value, node.line)
        else:
            env.define(node.var_name, value)

    def _exec_DefineStmt(self, node: ast.DefineStmt, env: Environment) -> None:
        self.functions[node.name] = node

    def _exec_CallStmt(self, node: ast.CallStmt, env: Environment) -> None:
        result = self.call_function(node.name, node.args, env, node.line)
        if node.store_in is not None:
            if env.has(node.store_in):
                env.set(node.store_in, result, node.line)
            else:
                env.define(node.store_in, result)

    def _exec_ReturnStmt(self, node: ast.ReturnStmt, env: Environment) -> None:
        value = self._eval(node.value, env)
        raise _ReturnSignal(value)

    def _exec_NoteStmt(self, node: ast.NoteStmt, env: Environment) -> None:
        pass  # Comments are ignored

    # ── §14 Visual Executors ─────────────────────────────────────────

    def _get_visuals(self, line: int):
        if self._visuals is None:
            from .visuals import Visuals
            self._visuals = Visuals(self)
        return self._visuals

    def _exec_OpenWindowStmt(self, node: ast.OpenWindowStmt, env: Environment) -> None:
        title = format_value(self._eval(node.title, env))
        self._get_visuals(node.line).open_window(title)

    def _exec_SetWindowSizeStmt(self, node: ast.SetWindowSizeStmt, env: Environment) -> None:
        w = self._eval(node.width, env)
        h = self._eval(node.height, env)
        self._get_visuals(node.line).set_window_size(int(w), int(h))

    def _exec_AddLabelStmt(self, node: ast.AddLabelStmt, env: Environment) -> None:
        text = format_value(self._eval(node.text, env))
        self._get_visuals(node.line).add_label(text)

    def _exec_AddButtonStmt(self, node: ast.AddButtonStmt, env: Environment) -> None:
        text = format_value(self._eval(node.text, env))
        self._get_visuals(node.line).add_button(text, node.fn_name)

    def _exec_AddTextBoxStmt(self, node: ast.AddTextBoxStmt, env: Environment) -> None:
        self._get_visuals(node.line).add_text_box(node.name)

    def _exec_WaitForCloseStmt(self, node: ast.WaitForCloseStmt, env: Environment) -> None:
        self._get_visuals(node.line).wait_for_close()

    def _exec_ClearWindowStmt(self, node: ast.ClearWindowStmt, env: Environment) -> None:
        self._get_visuals(node.line).clear_window()

    def _exec_SetTitleStmt(self, node: ast.SetTitleStmt, env: Environment) -> None:
        title = format_value(self._eval(node.title, env))
        self._get_visuals(node.line).set_title(title)

    def _exec_ShuffleButtonsStmt(self, node: ast.ShuffleButtonsStmt, env: Environment) -> None:
        self._get_visuals(node.line).shuffle_buttons()

    def _exec_SetBackgroundColorStmt(self, node: ast.SetBackgroundColorStmt, env: Environment) -> None:
        color = format_value(self._eval(node.color, env))
        self._get_visuals(node.line).set_background_color(color)

    def _exec_SetTextColorStmt(self, node: ast.SetTextColorStmt, env: Environment) -> None:
        color = format_value(self._eval(node.color, env))
        self._get_visuals(node.line).set_text_color(color)

    def _exec_SetFontSizeStmt(self, node: ast.SetFontSizeStmt, env: Environment) -> None:
        size = self._eval(node.size, env)
        self._check_number(size, "font size", node.line)
        self._get_visuals(node.line).set_font_size(int(size))

    def _exec_MoveStmt(self, node: ast.MoveStmt, env: Environment) -> None:
        amount = self._eval(node.amount, env)
        self._check_number(amount, "move distance", node.line)
        v = self._get_visuals(node.line)
        if node.direction == "forward":
            v.turtle_forward(int(amount))
        else:
            v.turtle_backward(int(amount))

    def _exec_TurnStmt(self, node: ast.TurnStmt, env: Environment) -> None:
        degrees = self._eval(node.degrees, env)
        self._check_number(degrees, "turn degrees", node.line)
        v = self._get_visuals(node.line)
        if node.direction == "left":
            v.turtle_left(int(degrees))
        else:
            v.turtle_right(int(degrees))

    def _exec_PenStmt(self, node: ast.PenStmt, env: Environment) -> None:
        v = self._get_visuals(node.line)
        if node.action == "up":
            v.turtle_pen_up()
        else:
            v.turtle_pen_down()

    def _exec_SetPenColorStmt(self, node: ast.SetPenColorStmt, env: Environment) -> None:
        color = format_value(self._eval(node.color, env))
        self._get_visuals(node.line).turtle_set_color(color)

    def _exec_DrawCircleStmt(self, node: ast.DrawCircleStmt, env: Environment) -> None:
        radius = self._eval(node.radius, env)
        self._check_number(radius, "circle radius", node.line)
        self._get_visuals(node.line).turtle_circle(int(radius))

    # ── Game Statements ───────────────────────────────────────────────

    def _exec_StartGameStmt(self, node: ast.StartGameStmt, env: Environment) -> None:
        from .game import launch_game
        root = None
        if self._visuals and self._visuals._root:
            root = self._visuals._root
        launch_game(interpreter=self, root=root)

    # ── Function Calling ─────────────────────────────────────────────

    def call_function(self, name: str, arg_nodes: list[object], env: Environment, line: int) -> object:
        """Call a user-defined function and return its result."""
        if name not in self.functions:
            raise EppRuntimeError(f"the function '{name}' has not been defined", line)

        func = self.functions[name]
        if len(arg_nodes) != len(func.params):
            raise EppRuntimeError(
                f"'{name}' expects {len(func.params)} argument(s) but got {len(arg_nodes)}",
                line
            )

        # Evaluate arguments in caller's scope
        arg_values = [self._eval(a, env) for a in arg_nodes]

        # Create new scope parented to globals
        local_env = Environment(parent=self.globals)
        for param_name, val in zip(func.params, arg_values):
            local_env.define(param_name, val)

        # Execute body, catch ReturnSignal
        try:
            for stmt in func.body:
                self._exec(stmt, local_env)
        except _ReturnSignal as ret:
            return ret.value

        return 0.0  # default return value

    def call_function_by_name(self, name: str) -> None:
        """Call a zero-arg function by name (used by button callbacks)."""
        self.call_function(name, [], self.globals, 0)

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _check_number(value: object, context: str, line: int) -> None:
        if not isinstance(value, (int, float)):
            raise EppRuntimeError(f"{context} must be a number, but got {type(value).__name__}", line)
