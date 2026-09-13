"""Tree-walking interpreter for E++."""

from __future__ import annotations
import random as _random
import subprocess as _subprocess
import threading as _threading
import time as _time
from datetime import datetime as _datetime
from . import ast_nodes as ast
from .environment import Environment
from .errors import EppRuntimeError
from .builtins import format_value, ask_auto_detect, random_between, random_decimal_between


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
        self._webserver = None  # lazy-init
        self._web_response = None
        self._web_status = 200
        self._web_content_type = None
        self._database = None  # lazy-init
        self._realtime = None  # lazy-init
        self._web_cookies: list[tuple[str, str]] = []
        self._middleware = None

    def run(self, statements: list[object]) -> None:
        """Execute a list of top-level statements."""
        for stmt in statements:
            self._exec(stmt, self.globals)
        # Programs that only register ticks or event handlers still need the
        # window to stay open, so enter the Tk mainloop for them.
        if self._realtime is not None and self._realtime.needs_mainloop():
            self._visuals.wait_for_close()

    def exec_block(self, body: list[object], env: Environment) -> None:
        """Execute a list of statements (used by callbacks in realtime.py)."""
        for stmt in body:
            self._exec(stmt, env)

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
        value = env.get(node.name, node.line)
        # If it's a tkinter Entry widget (text box), return its text content
        try:
            import tkinter as tk
            if isinstance(value, tk.Entry):
                return value.get()
        except ImportError:
            pass
        return value

    def _eval_RandomBetween(self, node: ast.RandomBetween, env: Environment) -> float:
        low = self._eval(node.low, env)
        high = self._eval(node.high, env)
        self._check_number(low, "random lower bound", node.line)
        self._check_number(high, "random upper bound", node.line)
        return random_between(low, high)

    def _eval_RandomDecimalBetween(self, node: ast.RandomDecimalBetween, env: Environment) -> float:
        low = self._eval(node.low, env)
        high = self._eval(node.high, env)
        self._check_number(low, "random lower bound", node.line)
        self._check_number(high, "random upper bound", node.line)
        return random_decimal_between(low, high)

    def _eval_BinaryOp(self, node: ast.BinaryOp, env: Environment) -> object:
        left = self._eval(node.left, env)
        right = self._eval(node.right, env)

        if node.op == "joined_with":
            left_str = format_value(left) if not isinstance(left, str) else left
            right_str = format_value(right) if not isinstance(right, str) else right
            return left_str + right_str

        if node.op == "plus":
            if isinstance(left, str) or isinstance(right, str):
                l = left if isinstance(left, str) else format_value(left)
                r = right if isinstance(right, str) else format_value(right)
                # "plus" reads as an English word, so it joins with a space;
                # "joined with" is the operator for gluing text together.
                return f"{l} {r}"
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
        if node.op == "empty":
            return left == "" or left is None
        elif node.op == "not_empty":
            return left != "" and left is not None
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
        if isinstance(current, list):
            current.append(amount)
            return
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

    def _exec_RunInBackgroundStmt(self, node: ast.RunInBackgroundStmt, env: Environment) -> None:
        """Run a zero-arg function in a background daemon thread."""
        name = node.name
        if name not in self.functions:
            raise EppRuntimeError(f"the function '{name}' has not been defined", node.line)

        def _run():
            local_env = Environment(parent=self.globals)
            try:
                for stmt in self.functions[name].body:
                    self._exec(stmt, local_env)
            except _ReturnSignal:
                pass
            except Exception as e:
                self._say_fn(f"Background error in '{name}': {e}")

        thread = _threading.Thread(target=_run, daemon=True)
        thread.start()

    def _exec_RunCommandStmt(self, node: ast.RunCommandStmt, env: Environment) -> None:
        """Run a shell command, optionally in background."""
        command = str(self._eval(node.command, env))

        if node.background:
            def _run():
                try:
                    _subprocess.run(command, shell=True, check=False)
                except Exception as e:
                    self._say_fn(f"Command error: {e}")
            thread = _threading.Thread(target=_run, daemon=True)
            thread.start()
        else:
            try:
                result = _subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
                if result.stdout.strip():
                    self._say_fn(result.stdout.strip())
                if result.returncode != 0 and result.stderr.strip():
                    self._say_fn(f"Command error: {result.stderr.strip()}")
            except Exception as e:
                raise EppRuntimeError(f"failed to run command: {e}", node.line)

    # ── Data Structure Executors ──────────────────────────────────────

    def _exec_CreateListStmt(self, node: ast.CreateListStmt, env: Environment) -> None:
        env.define(node.name, [])

    def _exec_CreateDictStmt(self, node: ast.CreateDictStmt, env: Environment) -> None:
        env.define(node.name, {})

    def _exec_RemoveItemStmt(self, node: ast.RemoveItemStmt, env: Environment) -> None:
        lst = env.get(node.list_name, node.line)
        if not isinstance(lst, list):
            raise EppRuntimeError(f"'{node.list_name}' is not a list", node.line)
        index = self._eval(node.index, env)
        self._check_number(index, "index", node.line)
        idx = int(index)
        if idx < 1 or idx > len(lst):
            raise EppRuntimeError(f"index {idx} is out of bounds (list has {len(lst)} items)", node.line)
        lst.pop(idx - 1)

    def _exec_RemoveValueStmt(self, node: ast.RemoveValueStmt, env: Environment) -> None:
        lst = env.get(node.list_name, node.line)
        if not isinstance(lst, list):
            raise EppRuntimeError(f"'{node.list_name}' is not a list", node.line)
        value = self._eval(node.value, env)
        try:
            lst.remove(value)
        except ValueError:
            raise EppRuntimeError(f"value {format_value(value)!r} not found in '{node.list_name}'", node.line)

    def _exec_RemoveEntryStmt(self, node: ast.RemoveEntryStmt, env: Environment) -> None:
        d = env.get(node.dict_name, node.line)
        if not isinstance(d, dict):
            raise EppRuntimeError(f"'{node.dict_name}' is not a dictionary", node.line)
        key = format_value(self._eval(node.key, env))
        if key not in d:
            raise EppRuntimeError(f"key {key!r} not found in '{node.dict_name}'", node.line)
        del d[key]

    def _exec_SetEntryStmt(self, node: ast.SetEntryStmt, env: Environment) -> None:
        d = env.get(node.dict_name, node.line)
        if not isinstance(d, dict):
            raise EppRuntimeError(f"'{node.dict_name}' is not a dictionary", node.line)
        key = format_value(self._eval(node.key, env))
        value = self._eval(node.value, env)
        d[key] = value

    def _exec_SetItemStmt(self, node: ast.SetItemStmt, env: Environment) -> None:
        lst = env.get(node.list_name, node.line)
        if not isinstance(lst, list):
            raise EppRuntimeError(f"'{node.list_name}' is not a list", node.line)
        index = self._eval(node.index, env)
        self._check_number(index, "index", node.line)
        idx = int(index)
        if idx < 1 or idx > len(lst):
            raise EppRuntimeError(
                f"index {idx} out of bounds (list has {len(lst)} items)", node.line
            )
        lst[idx - 1] = self._eval(node.value, env)

    def _exec_ForEachStmt(self, node: ast.ForEachStmt, env: Environment) -> None:
        collection = env.get(node.iterable_name, node.line)
        if isinstance(collection, dict):
            items = collection.items()
        elif isinstance(collection, list):
            if node.value_name:
                raise EppRuntimeError(f"cannot use 'and' destructuring on a list, only on a dictionary", node.line)
            items = ((item, None) for item in collection)
        else:
            raise EppRuntimeError(f"'{node.iterable_name}' is not a list or dictionary", node.line)
        for key, value in items:
            if env.has(node.var_name):
                env.set(node.var_name, key, node.line)
            else:
                env.define(node.var_name, key)
            if node.value_name:
                if env.has(node.value_name):
                    env.set(node.value_name, value, node.line)
                else:
                    env.define(node.value_name, value)
            for stmt in node.body:
                self._exec(stmt, env)

    # ── Data Structure Evaluators ────────────────────────────────────

    def _eval_ItemOfExpr(self, node: ast.ItemOfExpr, env: Environment) -> object:
        lst = env.get(node.list_name, node.line)
        if not isinstance(lst, list):
            raise EppRuntimeError(f"'{node.list_name}' is not a list", node.line)
        index = self._eval(node.index, env)
        self._check_number(index, "index", node.line)
        idx = int(index)
        if idx < 1 or idx > len(lst):
            raise EppRuntimeError(f"index {idx} is out of bounds (list has {len(lst)} items)", node.line)
        return lst[idx - 1]

    def _eval_LengthOfExpr(self, node: ast.LengthOfExpr, env: Environment) -> float:
        val = env.get(node.name, node.line)
        if isinstance(val, str):
            return float(len(val))
        if not isinstance(val, (list, dict)):
            raise EppRuntimeError(f"'{node.name}' is not a list, dictionary, or string", node.line)
        return float(len(val))

    def _eval_KeysOfExpr(self, node: ast.KeysOfExpr, env: Environment) -> list:
        d = env.get(node.name, node.line)
        if not isinstance(d, dict):
            raise EppRuntimeError(f"'{node.name}' is not a dictionary", node.line)
        return list(d.keys())

    def _eval_EntryInExpr(self, node: ast.EntryInExpr, env: Environment) -> object:
        d = env.get(node.dict_name, node.line)
        if not isinstance(d, dict):
            raise EppRuntimeError(f"'{node.dict_name}' is not a dictionary", node.line)
        key = format_value(self._eval(node.key, env))
        if key not in d:
            raise EppRuntimeError(f"key {key!r} not found in '{node.dict_name}'", node.line)
        return d[key]

    def _eval_ContainsExpr(self, node: ast.ContainsExpr, env: Environment) -> bool:
        collection = self._eval(node.collection, env)
        value = self._eval(node.value, env)
        if isinstance(collection, list):
            return value in collection
        if isinstance(collection, dict):
            return format_value(value) in collection
        raise EppRuntimeError("'contains' can only be used with lists or dictionaries", node.line)

    def _eval_HasEntryExpr(self, node: ast.HasEntryExpr, env: Environment) -> bool:
        collection = self._eval(node.collection, env)
        key = format_value(self._eval(node.key, env))
        if not isinstance(collection, dict):
            raise EppRuntimeError("'has the entry' can only be used with dictionaries", node.line)
        return key in collection

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

    def _exec_MoveToStmt(self, node: ast.MoveToStmt, env: Environment) -> None:
        x = self._eval(node.x, env)
        y = self._eval(node.y, env)
        self._check_number(x, "move x", node.line)
        self._check_number(y, "move y", node.line)
        self._get_visuals(node.line).turtle_goto(int(x), int(y))

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

    def _exec_SetPenSpeedStmt(self, node: ast.SetPenSpeedStmt, env: Environment) -> None:
        speed = self._eval(node.speed, env)
        self._check_number(speed, "pen speed", node.line)
        self._get_visuals(node.line).turtle_set_speed(int(speed))

    def _exec_SetPenSizeStmt(self, node: ast.SetPenSizeStmt, env: Environment) -> None:
        size = self._eval(node.size, env)
        self._check_number(size, "pen size", node.line)
        self._get_visuals(node.line).turtle_set_size(int(size))

    def _exec_DrawCircleStmt(self, node: ast.DrawCircleStmt, env: Environment) -> None:
        radius = self._eval(node.radius, env)
        self._check_number(radius, "circle radius", node.line)
        self._get_visuals(node.line).turtle_circle(int(radius))

    # ── Game Statements ───────────────────────────────────────────────

    def _exec_StartGameStmt(self, node: ast.StartGameStmt, env: Environment) -> None:
        root = None
        if self._visuals and self._visuals._root:
            root = self._visuals._root
        if node.game_type == "jump and run":
            from .game import launch_game
            launch_game(interpreter=self, root=root)
            return
        from .arcade import launch_arcade_game
        launch_arcade_game(node.game_type, interpreter=self, root=root)

    # ── Webserver Executors ────────────────────────────────────────────

    def _get_webserver(self, line: int):
        if self._webserver is None:
            from .webserver import EppWebserver
            self._webserver = EppWebserver(self)
        return self._webserver

    def _exec_StartWebserverStmt(self, node: ast.StartWebserverStmt, env: Environment) -> None:
        port = self._eval(node.port, env)
        self._check_number(port, "port", node.line)
        self._get_webserver(node.line).start(int(port))

    def _exec_AddRouteStmt(self, node: ast.AddRouteStmt, env: Environment) -> None:
        self._get_webserver(node.line).add_route(node.method, node.path, node.handler_name, node.params)

    def _exec_RespondWithStmt(self, node: ast.RespondWithStmt, env: Environment) -> None:
        self._web_response = self._eval(node.value, env)
        if node.status_code is not None:
            status = self._eval(node.status_code, env)
            self._check_number(status, "status code", node.line)
            self._web_status = int(status)

    def _exec_SetContentTypeStmt(self, node: ast.SetContentTypeStmt, env: Environment) -> None:
        self._web_content_type = node.content_type

    def _exec_EnableCORSStmt(self, node: ast.EnableCORSStmt, env: Environment) -> None:
        self._get_webserver(node.line).enable_cors()

    def _exec_ServeStaticStmt(self, node: ast.ServeStaticStmt, env: Environment) -> None:
        folder = format_value(self._eval(node.folder, env))
        self._get_webserver(node.line).set_static_folder(folder)

    def _exec_WaitForConnectionsStmt(self, node: ast.WaitForConnectionsStmt, env: Environment) -> None:
        ws = self._get_webserver(node.line)
        ws.wait()

    # ── Database Executors ──────────────────────────────────────────

    def _get_database(self, line: int):
        if self._database is None:
            from .database import EppDatabase
            self._database = EppDatabase()
        return self._database

    def _exec_OpenDatabaseStmt(self, node: ast.OpenDatabaseStmt, env: Environment) -> None:
        name = format_value(self._eval(node.name, env))
        self._get_database(node.line).open(name, node.line)

    def _exec_CloseDatabaseStmt(self, node: ast.CloseDatabaseStmt, env: Environment) -> None:
        self._get_database(node.line).close(node.line)

    def _exec_CreateTableStmt(self, node: ast.CreateTableStmt, env: Environment) -> None:
        self._get_database(node.line).create_table(node.table_name, node.columns, node.line)

    def _exec_InsertRowStmt(self, node: ast.InsertRowStmt, env: Environment) -> None:
        values = [self._eval(v, env) for v in node.values]
        self._get_database(node.line).insert(node.table_name, values, node.line)

    def _exec_SelectStmt(self, node: ast.SelectStmt, env: Environment) -> None:
        where_val = self._eval(node.where_value, env) if node.where_value is not None else None
        results = self._get_database(node.line).select(
            node.table_name, node.where_column, node.where_op, where_val, node.line
        )
        if env.has(node.store_in):
            env.set(node.store_in, results, node.line)
        else:
            env.define(node.store_in, results)

    def _exec_UpdateRowStmt(self, node: ast.UpdateRowStmt, env: Environment) -> None:
        set_val = self._eval(node.set_value, env)
        where_val = self._eval(node.where_value, env)
        self._get_database(node.line).update(
            node.table_name, node.set_column, set_val,
            node.where_column, node.where_op, where_val, node.line
        )

    def _exec_DeleteRowStmt(self, node: ast.DeleteRowStmt, env: Environment) -> None:
        where_val = self._eval(node.where_value, env)
        self._get_database(node.line).delete(
            node.table_name, node.where_column, node.where_op, where_val, node.line
        )

    # ── ML Evaluators ───────────────────────────────────────────────

    def _eval_MeanOfExpr(self, node: ast.MeanOfExpr, env: Environment) -> float:
        val = env.get(node.name, node.line)
        if not isinstance(val, list):
            raise EppRuntimeError(f"'{node.name}' is not a list", node.line)
        if not val:
            raise EppRuntimeError(f"cannot compute mean of empty list", node.line)
        nums = [self._as_number(v, node.line) for v in val]
        return sum(nums) / len(nums)

    def _eval_SumOfExpr(self, node: ast.SumOfExpr, env: Environment) -> float:
        val = env.get(node.name, node.line)
        if not isinstance(val, list):
            raise EppRuntimeError(f"'{node.name}' is not a list", node.line)
        return sum(self._as_number(v, node.line) for v in val)

    def _eval_MinOfExpr(self, node: ast.MinOfExpr, env: Environment) -> float:
        val = env.get(node.name, node.line)
        if not isinstance(val, list):
            raise EppRuntimeError(f"'{node.name}' is not a list", node.line)
        if not val:
            raise EppRuntimeError(f"cannot compute min of empty list", node.line)
        return min(self._as_number(v, node.line) for v in val)

    def _eval_MaxOfExpr(self, node: ast.MaxOfExpr, env: Environment) -> float:
        val = env.get(node.name, node.line)
        if not isinstance(val, list):
            raise EppRuntimeError(f"'{node.name}' is not a list", node.line)
        if not val:
            raise EppRuntimeError(f"cannot compute max of empty list", node.line)
        return max(self._as_number(v, node.line) for v in val)

    def _eval_DotProductExpr(self, node: ast.DotProductExpr, env: Environment) -> float:
        left = env.get(node.left_name, node.line)
        right = env.get(node.right_name, node.line)
        if not isinstance(left, list) or not isinstance(right, list):
            raise EppRuntimeError("dot product requires two lists", node.line)
        if len(left) != len(right):
            raise EppRuntimeError(
                f"dot product requires lists of equal length ({len(left)} vs {len(right)})",
                node.line,
            )
        return sum(
            self._as_number(a, node.line) * self._as_number(b, node.line)
            for a, b in zip(left, right)
        )

    def _eval_ExponentialOfExpr(self, node: ast.ExponentialOfExpr, env: Environment) -> float:
        val = self._eval(node.value, env)
        self._check_number(val, "exponential argument", node.line)
        import math
        return math.exp(val)

    def _eval_LogarithmOfExpr(self, node: ast.LogarithmOfExpr, env: Environment) -> float:
        val = self._eval(node.value, env)
        self._check_number(val, "logarithm argument", node.line)
        if val <= 0:
            raise EppRuntimeError("logarithm requires a positive number", node.line)
        import math
        return math.log(val)

    @staticmethod
    def _as_number(value: object, line: int) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        raise EppRuntimeError(f"expected a number but got {type(value).__name__}", line)

    # ── File I/O Executors ─────────────────────────────────────────

    def _exec_ReadFileStmt(self, node: ast.ReadFileStmt, env: Environment) -> None:
        file_path = format_value(self._eval(node.file_path, env))
        try:
            with open(file_path, "r") as f:
                content = f.read()
        except FileNotFoundError:
            raise EppRuntimeError(f"file '{file_path}' not found", node.line)
        except OSError as e:
            raise EppRuntimeError(f"cannot read file '{file_path}': {e}", node.line)
        if env.has(node.store_in):
            env.set(node.store_in, content, node.line)
        else:
            env.define(node.store_in, content)

    def _exec_WriteFileStmt(self, node: ast.WriteFileStmt, env: Environment) -> None:
        value = self._eval(node.value, env)
        file_path = format_value(self._eval(node.file_path, env))
        # Uploaded files arrive as raw bytes and must not be re-encoded.
        if isinstance(value, (bytes, bytearray)):
            mode, payload = "wb", bytes(value)
        else:
            mode, payload = "w", format_value(value)
        try:
            with open(file_path, mode) as f:
                f.write(payload)
        except OSError as e:
            raise EppRuntimeError(f"cannot write file '{file_path}': {e}", node.line)

    # ── String Operation Evaluators ──────────────────────────────

    def _eval_LowercaseOfExpr(self, node: ast.LowercaseOfExpr, env: Environment) -> str:
        value = self._eval(node.value, env)
        return format_value(value).lower()

    def _eval_UppercaseOfExpr(self, node: ast.UppercaseOfExpr, env: Environment) -> str:
        value = self._eval(node.value, env)
        return format_value(value).upper()

    def _eval_SplitByExpr(self, node: ast.SplitByExpr, env: Environment) -> list:
        value = format_value(self._eval(node.value, env))
        delim = format_value(self._eval(node.delimiter, env))
        return value.split(delim)

    def _eval_SubstringOfExpr(self, node: ast.SubstringOfExpr, env: Environment) -> str:
        value = format_value(self._eval(node.value, env))
        start = self._eval(node.start, env)
        end = self._eval(node.end, env)
        self._check_number(start, "substring start", node.line)
        self._check_number(end, "substring end", node.line)
        # 1-based indexing, inclusive end
        s = int(start)
        e = int(end)
        return value[s - 1:e]

    def _eval_PositionOfExpr(self, node: ast.PositionOfExpr, env: Environment) -> float:
        needle = format_value(self._eval(node.needle, env))
        haystack = format_value(self._eval(node.haystack, env))
        idx = haystack.find(needle)
        return float(idx + 1) if idx >= 0 else 0.0  # 1-based, 0 = not found

    def _eval_ReplaceExpr(self, node: ast.ReplaceExpr, env: Environment) -> str:
        text = format_value(self._eval(node.text, env))
        old = format_value(self._eval(node.old, env))
        new = format_value(self._eval(node.new, env))
        return text.replace(old, new)

    # ── Timestamp Evaluators ─────────────────────────────────────

    def _eval_CurrentTimestampExpr(self, node: ast.CurrentTimestampExpr, env: Environment) -> float:
        return float(int(_time.time()))

    def _eval_CurrentDateExpr(self, node: ast.CurrentDateExpr, env: Environment) -> str:
        return _datetime.now().strftime("%Y-%m-%d")

    def _eval_CurrentTimeExpr(self, node: ast.CurrentTimeExpr, env: Environment) -> str:
        return _datetime.now().strftime("%H:%M:%S")

    # ── Random Item Evaluator ────────────────────────────────────

    def _eval_RandomItemExpr(self, node: ast.RandomItemExpr, env: Environment) -> object:
        lst = env.get(node.list_name, node.line)
        if not isinstance(lst, list):
            raise EppRuntimeError(f"'{node.list_name}' is not a list", node.line)
        if not lst:
            raise EppRuntimeError(f"cannot pick from empty list '{node.list_name}'", node.line)
        return _random.choice(lst)

    # ── Type Conversion Evaluators ───────────────────────────────

    def _eval_NumberOfExpr(self, node: ast.NumberOfExpr, env: Environment) -> float:
        value = self._eval(node.value, env)
        if isinstance(value, (int, float)):
            return float(value)
        try:
            text = format_value(value)
            if '.' in text:
                return float(text)
            return float(int(text))
        except (ValueError, TypeError):
            return 0.0

    def _eval_TextOfExpr(self, node: ast.TextOfExpr, env: Environment) -> str:
        value = self._eval(node.value, env)
        return format_value(value)

    # ── Request Access Evaluators ────────────────────────────────

    def _eval_BodyOfExpr(self, node: ast.BodyOfExpr, env: Environment) -> object:
        request = env.get(node.var_name, node.line)
        if not isinstance(request, dict):
            raise EppRuntimeError(f"'{node.var_name}' is not a request dictionary", node.line)
        body = request.get("body", "")
        data = request.get("data")
        return data if data is not None else body

    def _eval_PathParamExpr(self, node: ast.PathParamExpr, env: Environment) -> object:
        request = env.get(node.var_name, node.line)
        if not isinstance(request, dict):
            raise EppRuntimeError(f"'{node.var_name}' is not a request dictionary", node.line)
        params = request.get("__path_params", {})
        if node.param_name not in params:
            raise EppRuntimeError(f"path parameter '{node.param_name}' not found", node.line)
        return params[node.param_name]

    def _eval_QueryParamExpr(self, node: ast.QueryParamExpr, env: Environment) -> object:
        request = env.get(node.var_name, node.line)
        if not isinstance(request, dict):
            raise EppRuntimeError(f"'{node.var_name}' is not a request dictionary", node.line)
        params = request.get("__query_params", {})
        return params.get(node.param_name, "")

    # ── GUI Extension Executors ──────────────────────────────────

    def _exec_AddDropdownStmt(self, node: ast.AddDropdownStmt, env: Environment) -> None:
        self._get_visuals(node.line).add_dropdown(node.name, node.options)

    def _eval_DropdownValueExpr(self, node: ast.DropdownValueExpr, env: Environment) -> str:
        return env.get(f"__dropdown_{node.name}", node.line)

    def _exec_AddTableStmt(self, node: ast.AddTableStmt, env: Environment) -> None:
        self._get_visuals(node.line).add_table(node.name, node.columns)

    def _exec_AddRowStmt(self, node: ast.AddRowStmt, env: Environment) -> None:
        values = [format_value(self._eval(v, env)) for v in node.values]
        self._get_visuals(node.line).add_row(node.table_name, values)

    def _exec_ClearTableStmt(self, node: ast.ClearTableStmt, env: Environment) -> None:
        self._get_visuals(node.line).clear_table(node.name)

    def _exec_WaitSecondsStmt(self, node: ast.WaitSecondsStmt, env: Environment) -> None:
        seconds = self._eval(node.seconds, env)
        self._check_number(seconds, "wait seconds", node.line)
        _time.sleep(float(seconds))

    def _exec_ClearTextBoxStmt(self, node: ast.ClearTextBoxStmt, env: Environment) -> None:
        self._get_visuals(node.line).clear_text_box(node.name)

    def _exec_ShowMessageStmt(self, node: ast.ShowMessageStmt, env: Environment) -> None:
        text = format_value(self._eval(node.text, env))
        self._get_visuals(node.line).show_message(text)

    def _exec_ShowErrorStmt(self, node: ast.ShowErrorStmt, env: Environment) -> None:
        text = format_value(self._eval(node.text, env))
        self._get_visuals(node.line).show_error(text)

    def _exec_AddCheckboxStmt(self, node: ast.AddCheckboxStmt, env: Environment) -> None:
        label = format_value(self._eval(node.label, env))
        self._get_visuals(node.line).add_checkbox(node.name, label)

    def _eval_CheckboxValueExpr(self, node: ast.CheckboxValueExpr, env: Environment) -> bool:
        return self._get_visuals(node.line).checkbox_value(node.name)

    def _exec_AddRadioGroupStmt(self, node: ast.AddRadioGroupStmt, env: Environment) -> None:
        self._get_visuals(node.line).add_radio_group(node.name, node.options)

    def _eval_RadioGroupValueExpr(self, node: ast.RadioGroupValueExpr, env: Environment) -> str:
        return self._get_visuals(node.line).radio_group_value(node.name)

    def _exec_AddSliderStmt(self, node: ast.AddSliderStmt, env: Environment) -> None:
        low = self._eval(node.low, env)
        high = self._eval(node.high, env)
        self._check_number(low, "slider start", node.line)
        self._check_number(high, "slider end", node.line)
        self._get_visuals(node.line).add_slider(node.name, float(low), float(high))

    def _eval_SliderValueExpr(self, node: ast.SliderValueExpr, env: Environment) -> float:
        return self._get_visuals(node.line).slider_value(node.name)

    def _exec_AddImageStmt(self, node: ast.AddImageStmt, env: Environment) -> None:
        file_path = format_value(self._eval(node.file_path, env))
        self._get_visuals(node.line).add_image(node.name, file_path)

    def _exec_AddMenuStmt(self, node: ast.AddMenuStmt, env: Environment) -> None:
        self._get_visuals(node.line).add_menu(node.name, node.options)

    def _exec_AddMenuItemStmt(self, node: ast.AddMenuItemStmt, env: Environment) -> None:
        self._get_visuals(node.line).add_menu_item(node.item, node.menu, node.fn_name)

    def _exec_ArrangeGridStmt(self, node: ast.ArrangeGridStmt, env: Environment) -> None:
        columns = self._eval(node.columns, env)
        self._check_number(columns, "number of columns", node.line)
        self._get_visuals(node.line).arrange_grid(int(columns))

    def _exec_AddSpacingStmt(self, node: ast.AddSpacingStmt, env: Environment) -> None:
        amount = self._eval(node.amount, env)
        self._check_number(amount, "spacing", node.line)
        self._get_visuals(node.line).add_spacing(int(amount))

    def _exec_AlignWidgetStmt(self, node: ast.AlignWidgetStmt, env: Environment) -> None:
        self._get_visuals(node.line).align_widget(node.kind, node.name, node.alignment)

    def _exec_AskYesNoStmt(self, node: ast.AskYesNoStmt, env: Environment) -> None:
        message = format_value(self._eval(node.message, env))
        answer = self._get_visuals(node.line).ask_yes_or_no(message)
        self._store(env, "answer", answer, node.line)

    def _exec_AskFileStmt(self, node: ast.AskFileStmt, env: Environment) -> None:
        chosen = self._get_visuals(node.line).ask_for_file(node.mode)
        self._store(env, "chosen file", chosen, node.line)

    # ── Realtime Executors ───────────────────────────────────────────

    def _get_realtime(self, line: int):
        if self._realtime is None:
            from .realtime import Realtime
            self._realtime = Realtime(self, self._get_visuals(line))
        return self._realtime

    def _exec_EveryStmt(self, node: ast.EveryStmt, env: Environment) -> None:
        interval = self._eval(node.interval, env)
        self._check_number(interval, "tick interval", node.line)
        self._get_realtime(node.line).add_tick(int(interval), node.body, env)

    def _exec_StopTickingStmt(self, node: ast.StopTickingStmt, env: Environment) -> None:
        self._get_realtime(node.line).stop_ticking()

    def _exec_WhenKeyStmt(self, node: ast.WhenKeyStmt, env: Environment) -> None:
        self._get_realtime(node.line).add_key_handler(node.key, node.body, env)

    def _exec_WhenMouseStmt(self, node: ast.WhenMouseStmt, env: Environment) -> None:
        self._get_realtime(node.line).add_mouse_handler(node.event, node.body, env)

    def _eval_KeyPressedExpr(self, node: ast.KeyPressedExpr, env: Environment) -> bool:
        return self._get_realtime(node.line).is_key_pressed(node.key)

    def _eval_MouseCoordExpr(self, node: ast.MouseCoordExpr, env: Environment) -> float:
        return self._get_realtime(node.line).mouse_coord(node.axis)

    def _exec_AddCanvasStmt(self, node: ast.AddCanvasStmt, env: Environment) -> None:
        width = self._eval(node.width, env)
        height = self._eval(node.height, env)
        self._check_number(width, "canvas width", node.line)
        self._check_number(height, "canvas height", node.line)
        self._get_visuals(node.line).add_canvas(node.name, int(width), int(height))

    def _exec_AddSpriteStmt(self, node: ast.AddSpriteStmt, env: Environment) -> None:
        image = None
        if node.image is not None:
            image = format_value(self._eval(node.image, env))
        self._get_realtime(node.line).add_sprite(node.name, image, node.line)

    def _exec_SetSpritePositionStmt(self, node: ast.SetSpritePositionStmt, env: Environment) -> None:
        x = self._eval(node.x, env)
        y = self._eval(node.y, env)
        self._check_number(x, "sprite x", node.line)
        self._check_number(y, "sprite y", node.line)
        self._get_realtime(node.line).set_sprite_position(node.name, float(x), float(y), node.line)

    def _exec_MoveSpriteStmt(self, node: ast.MoveSpriteStmt, env: Environment) -> None:
        dx = self._eval(node.dx, env)
        dy = self._eval(node.dy, env)
        self._check_number(dx, "sprite step sideways", node.line)
        self._check_number(dy, "sprite step downwards", node.line)
        self._get_realtime(node.line).move_sprite(node.name, float(dx), float(dy), node.line)

    def _eval_SpriteCoordExpr(self, node: ast.SpriteCoordExpr, env: Environment) -> float:
        return self._get_realtime(node.line).sprite_coord(node.name, node.axis, node.line)

    def _eval_SpriteCollidesExpr(self, node: ast.SpriteCollidesExpr, env: Environment) -> bool:
        return self._get_realtime(node.line).sprites_collide(node.left, node.right, node.line)

    def _exec_RemoveSpriteStmt(self, node: ast.RemoveSpriteStmt, env: Environment) -> None:
        self._get_realtime(node.line).remove_sprite(node.name, node.line)

    def _exec_DrawRectangleStmt(self, node: ast.DrawRectangleStmt, env: Environment) -> None:
        x = self._eval(node.x, env)
        y = self._eval(node.y, env)
        width = self._eval(node.width, env)
        height = self._eval(node.height, env)
        for value, what in ((x, "x"), (y, "y"), (width, "width"), (height, "height")):
            self._check_number(value, f"rectangle {what}", node.line)
        color = format_value(self._eval(node.color, env))
        self._get_realtime(node.line).draw_rectangle(x, y, width, height, color)

    def _exec_DrawCanvasCircleStmt(self, node: ast.DrawCanvasCircleStmt, env: Environment) -> None:
        x = self._eval(node.x, env)
        y = self._eval(node.y, env)
        radius = self._eval(node.radius, env)
        for value, what in ((x, "x"), (y, "y"), (radius, "radius")):
            self._check_number(value, f"circle {what}", node.line)
        color = format_value(self._eval(node.color, env))
        self._get_realtime(node.line).draw_circle(x, y, radius, color)

    def _exec_DrawCanvasTextStmt(self, node: ast.DrawCanvasTextStmt, env: Environment) -> None:
        text = format_value(self._eval(node.text, env))
        x = self._eval(node.x, env)
        y = self._eval(node.y, env)
        self._check_number(x, "text x", node.line)
        self._check_number(y, "text y", node.line)
        color = format_value(self._eval(node.color, env))
        self._get_realtime(node.line).draw_text(text, x, y, color)

    def _exec_ClearCanvasStmt(self, node: ast.ClearCanvasStmt, env: Environment) -> None:
        self._get_realtime(node.line).clear_canvas()

    # ── Cookie, Session, Form and Upload Support ─────────────────────

    def _request_of(self, var_name: str, env: Environment, line: int) -> dict:
        request = env.get(var_name, line)
        if not isinstance(request, dict):
            raise EppRuntimeError(f"'{var_name}' is not a request dictionary", line)
        return request

    def _exec_SetCookieStmt(self, node: ast.SetCookieStmt, env: Environment) -> None:
        request = self._request_of(node.request_var, env, node.line)
        value = format_value(self._eval(node.value, env))
        request.setdefault("__cookies", {})[node.cookie_name] = value
        self._web_cookies.append((node.cookie_name, value))

    def _eval_CookieExpr(self, node: ast.CookieExpr, env: Environment) -> str:
        request = self._request_of(node.request_var, env, node.line)
        return request.get("__cookies", {}).get(node.cookie_name, "")

    def _exec_StartSessionStmt(self, node: ast.StartSessionStmt, env: Environment) -> None:
        request = self._request_of(node.request_var, env, node.line)
        self._get_webserver(node.line).start_session(request)

    def _exec_SetSessionValueStmt(self, node: ast.SetSessionValueStmt, env: Environment) -> None:
        request = self._request_of(node.request_var, env, node.line)
        session = request.get("__session")
        if session is None:
            session = self._get_webserver(node.line).start_session(request)
        session[node.key] = format_value(self._eval(node.value, env))

    def _eval_SessionValueExpr(self, node: ast.SessionValueExpr, env: Environment) -> object:
        request = self._request_of(node.request_var, env, node.line)
        return (request.get("__session") or {}).get(node.key, "")

    def _eval_FormValueExpr(self, node: ast.FormValueExpr, env: Environment) -> object:
        request = self._request_of(node.request_var, env, node.line)
        return request.get("__form", {}).get(node.field_name, "")

    def _eval_UploadedFileExpr(self, node: ast.UploadedFileExpr, env: Environment) -> object:
        request = self._request_of(node.request_var, env, node.line)
        upload = request.get("__files", {}).get(node.field_name)
        if upload is None:
            raise EppRuntimeError(f"no uploaded file called '{node.field_name}'", node.line)
        return upload["content"]

    def _eval_ReplacePlaceholderExpr(self, node: ast.ReplacePlaceholderExpr, env: Environment) -> str:
        text = format_value(self._eval(node.text, env))
        value = format_value(self._eval(node.value, env))
        # Templates may use either {{name}} or {name}.
        text = text.replace("{{" + node.placeholder + "}}", value)
        return text.replace("{" + node.placeholder + "}", value)

    def _exec_BeforeRequestStmt(self, node: ast.BeforeRequestStmt, env: Environment) -> None:
        def _middleware(request: dict) -> None:
            local_env = Environment(parent=self.globals)
            local_env.define("request", request)
            try:
                self.exec_block(node.body, local_env)
            except _ReturnSignal:
                pass

        self._get_webserver(node.line).set_middleware(_middleware)

    # ── Websocket Executors ──────────────────────────────────────────

    def _exec_AddWebsocketRouteStmt(self, node: ast.AddWebsocketRouteStmt, env: Environment) -> None:
        self._get_webserver(node.line).add_websocket_route(node.path, node.handler_name)

    def _exec_SendToConnectionStmt(self, node: ast.SendToConnectionStmt, env: Environment) -> None:
        text = format_value(self._eval(node.value, env))
        connection = env.get(node.connection, node.line)
        self._get_webserver(node.line).get_websocket_hub().send(connection, text)

    def _exec_BroadcastStmt(self, node: ast.BroadcastStmt, env: Environment) -> None:
        text = format_value(self._eval(node.value, env))
        self._get_webserver(node.line).get_websocket_hub().broadcast(text)

    def call_websocket_handler(self, name: str, connection: object, text: str) -> None:
        """Run a websocket handler with 'connection' and 'message' in scope."""
        if name not in self.functions:
            raise EppRuntimeError(f"the function '{name}' has not been defined", 0)

        func = self.functions[name]
        local_env = Environment(parent=self.globals)
        local_env.define("connection", connection)
        local_env.define("message", text)
        # A handler may also name its own parameters: one for the connection,
        # an optional second one for the message.
        for param_name, value in zip(func.params, (connection, text)):
            local_env.define(param_name, value)

        try:
            self.exec_block(func.body, local_env)
        except _ReturnSignal:
            pass

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

    def call_function_with_values(self, name: str, values: list[object], line: int = 0) -> object:
        """Call a function with pre-evaluated values (used by webserver)."""
        if name not in self.functions:
            raise EppRuntimeError(f"the function '{name}' has not been defined", line)

        func = self.functions[name]
        local_env = Environment(parent=self.globals)
        for param_name, val in zip(func.params, values):
            local_env.define(param_name, val)

        try:
            for stmt in func.body:
                self._exec(stmt, local_env)
        except _ReturnSignal as ret:
            return ret.value

        return 0.0

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _store(env: Environment, name: str, value: object, line: int) -> None:
        """Create the variable, or overwrite it if it already exists."""
        if env.has(name):
            env.set(name, value, line)
        else:
            env.define(name, value)

    @staticmethod
    def _check_number(value: object, context: str, line: int) -> None:
        if not isinstance(value, (int, float)):
            raise EppRuntimeError(f"{context} must be a number, but got {type(value).__name__}", line)
