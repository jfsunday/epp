"""Lazy-initialized Tkinter + turtle wrapper for E++ §14 visual statements.

Only imports tkinter/turtle when actually used, so headless tests work fine.
"""

from __future__ import annotations
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .interpreter import Interpreter


class Visuals:
    def __init__(self, interpreter: Interpreter):
        self._interpreter = interpreter
        self._root = None
        self._canvas = None
        self._turtle = None
        self._frame = None

    def _ensure_tk(self):
        if self._root is not None:
            return
        if os.environ.get("EPP_HEADLESS"):
            from .errors import EppRuntimeError
            raise EppRuntimeError("visual statements are disabled in headless mode", 0)
        import tkinter as tk
        self._root = tk.Tk()
        self._root.title("E++")
        self._frame = tk.Frame(self._root)
        self._frame.pack(fill="both", expand=True)

    def _ensure_turtle(self):
        if self._turtle is not None:
            return
        self._ensure_tk()
        import tkinter as tk
        import turtle
        self._canvas = tk.Canvas(self._frame, width=400, height=400)
        self._canvas.pack()
        screen = turtle.TurtleScreen(self._canvas)
        self._turtle = turtle.RawTurtle(screen)
        self._turtle.speed(3)

    def open_window(self, title: str) -> None:
        self._ensure_tk()
        self._root.title(title)

    def set_window_size(self, width: int, height: int) -> None:
        self._ensure_tk()
        self._root.geometry(f"{width}x{height}")

    def add_label(self, text: str) -> None:
        self._ensure_tk()
        import tkinter as tk
        label = tk.Label(self._frame, text=text)
        label.pack(pady=5)

    def add_button(self, text: str, fn_name: str) -> None:
        self._ensure_tk()
        import tkinter as tk
        btn = tk.Button(
            self._frame,
            text=text,
            command=lambda: self._interpreter.call_function_by_name(fn_name)
        )
        btn.pack(pady=5)

    def add_text_box(self, name: str) -> None:
        self._ensure_tk()
        import tkinter as tk
        entry = tk.Entry(self._frame)
        entry.pack(pady=5)
        # Store a reference so __textbox_<name> can read it
        self._interpreter.globals.define(f"__textbox_{name}", entry)

    def wait_for_close(self) -> None:
        self._ensure_tk()
        self._root.mainloop()

    # ── Turtle commands ──────────────────────────────────────────────

    def turtle_forward(self, steps: int) -> None:
        self._ensure_turtle()
        self._turtle.forward(steps)

    def turtle_backward(self, steps: int) -> None:
        self._ensure_turtle()
        self._turtle.backward(steps)

    def turtle_left(self, degrees: int) -> None:
        self._ensure_turtle()
        self._turtle.left(degrees)

    def turtle_right(self, degrees: int) -> None:
        self._ensure_turtle()
        self._turtle.right(degrees)

    def turtle_pen_up(self) -> None:
        self._ensure_turtle()
        self._turtle.penup()

    def turtle_pen_down(self) -> None:
        self._ensure_turtle()
        self._turtle.pendown()

    def turtle_set_color(self, color: str) -> None:
        self._ensure_turtle()
        self._turtle.pencolor(color)

    def turtle_circle(self, radius: int) -> None:
        self._ensure_turtle()
        self._turtle.circle(radius)
