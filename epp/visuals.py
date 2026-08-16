"""Lazy-initialized Tkinter + turtle wrapper for E++ §14 visual statements.

Only imports tkinter/turtle when actually used, so headless tests work fine.
"""

from __future__ import annotations
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .interpreter import Interpreter

# Default theme
_DEFAULT_BG = "#1e1e2e"
_DEFAULT_FG = "#cdd6f4"
_DEFAULT_ACCENT = "#89b4fa"
_DEFAULT_BTN_BG = "#313244"
_DEFAULT_BTN_HOVER = "#45475a"
_DEFAULT_BTN_FG = "#cdd6f4"
_DEFAULT_FONT_FAMILY = "Segoe UI"
_DEFAULT_FONT_SIZE = 13
_FALLBACK_FONTS = ("Noto Sans", "DejaVu Sans", "Helvetica", "Arial", "TkDefaultFont")


class Visuals:
    def __init__(self, interpreter: Interpreter):
        self._interpreter = interpreter
        self._root = None
        self._canvas = None
        self._turtle = None
        self._frame = None
        self._bg_color = _DEFAULT_BG
        self._text_color = _DEFAULT_FG
        self._font_size = _DEFAULT_FONT_SIZE
        self._font_family = None  # resolved on first use
        self._btn_bg = _DEFAULT_BTN_BG
        self._btn_fg = _DEFAULT_BTN_FG
        self._accent = _DEFAULT_ACCENT

    def _resolve_font(self):
        """Pick the first available font family."""
        if self._font_family is not None:
            return
        import tkinter.font as tkfont
        available = set(tkfont.families())
        for fam in (_DEFAULT_FONT_FAMILY, *_FALLBACK_FONTS):
            if fam in available:
                self._font_family = fam
                return
        self._font_family = "TkDefaultFont"

    def _font(self, size: int | None = None, bold: bool = False):
        self._resolve_font()
        sz = size or self._font_size
        weight = "bold" if bold else "normal"
        return (self._font_family, sz, weight)

    def _ensure_tk(self):
        if self._root is not None:
            return
        if os.environ.get("EPP_HEADLESS"):
            from .errors import EppRuntimeError
            raise EppRuntimeError("visual statements are disabled in headless mode", 0)
        import tkinter as tk
        self._root = tk.Tk()
        self._root.title("E++")
        self._root.configure(bg=self._bg_color)
        self._frame = tk.Frame(self._root, bg=self._bg_color)
        self._frame.pack(fill="both", expand=True, padx=20, pady=15)

    def _ensure_turtle(self):
        if self._turtle is not None:
            return
        self._ensure_tk()
        import tkinter as tk
        import turtle
        self._canvas = tk.Canvas(
            self._frame, width=400, height=400,
            bg="#181825", highlightthickness=1, highlightbackground="#45475a",
        )
        self._canvas.pack(pady=10)
        screen = turtle.TurtleScreen(self._canvas)
        screen.bgcolor("#181825")
        self._turtle = turtle.RawTurtle(screen)
        self._turtle.speed(3)
        self._turtle.pencolor(_DEFAULT_ACCENT)

    def open_window(self, title: str) -> None:
        self._ensure_tk()
        self._root.title(title)

    def set_window_size(self, width: int, height: int) -> None:
        self._ensure_tk()
        self._root.geometry(f"{width}x{height}")
        # Center on screen
        self._root.update_idletasks()
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2
        self._root.geometry(f"{width}x{height}+{x}+{y}")

    def add_label(self, text: str) -> None:
        self._ensure_tk()
        import tkinter as tk
        fg = self._text_color
        bg = self._bg_color
        label = tk.Label(
            self._frame, text=text,
            fg=fg, bg=bg,
            font=self._font(),
            wraplength=450, justify="center",
        )
        label.pack(pady=4, anchor="center")

    def add_button(self, text: str, fn_name: str) -> None:
        self._ensure_tk()
        import tkinter as tk

        def _on_click():
            try:
                self._interpreter.call_function_by_name(fn_name)
            except tk.TclError:
                pass

        btn_bg = self._btn_bg
        btn_fg = self._btn_fg
        hover_bg = _DEFAULT_BTN_HOVER

        btn = tk.Button(
            self._frame, text=text, command=_on_click,
            fg=btn_fg, bg=btn_bg,
            activeforeground=btn_fg, activebackground=hover_bg,
            font=self._font(),
            relief="flat", cursor="hand2",
            padx=16, pady=6,
            borderwidth=0, highlightthickness=0,
        )
        btn.pack(pady=4, fill="x", padx=30)

        def _on_enter(e):
            btn.configure(bg=hover_bg)
        def _on_leave(e):
            btn.configure(bg=btn_bg)
        btn.bind("<Enter>", _on_enter)
        btn.bind("<Leave>", _on_leave)

    def add_text_box(self, name: str) -> None:
        self._ensure_tk()
        import tkinter as tk
        entry = tk.Entry(
            self._frame,
            fg=self._text_color, bg=_DEFAULT_BTN_BG,
            insertbackground=self._text_color,
            font=self._font(),
            relief="flat", borderwidth=0,
            highlightthickness=1, highlightcolor=_DEFAULT_ACCENT,
            highlightbackground="#45475a",
        )
        entry.pack(pady=6, fill="x", padx=30)
        self._interpreter.globals.define(f"__textbox_{name}", entry)

    def shuffle_buttons(self) -> None:
        self._ensure_tk()
        import tkinter as tk
        import random
        buttons = [w for w in self._frame.winfo_children() if isinstance(w, tk.Button)]
        if not buttons:
            return
        configs = [(b.cget("text"), b.cget("command")) for b in buttons]
        random.shuffle(configs)
        for btn, (text, cmd) in zip(buttons, configs):
            btn.configure(text=text, command=cmd)

    def clear_window(self) -> None:
        self._ensure_tk()
        for widget in self._frame.winfo_children():
            widget.destroy()
        self._turtle = None
        self._canvas = None

    def set_title(self, title: str) -> None:
        self._ensure_tk()
        self._root.title(title)

    def wait_for_close(self) -> None:
        self._ensure_tk()
        try:
            self._root.mainloop()
        except Exception:
            pass

    def set_background_color(self, color: str) -> None:
        self._ensure_tk()
        self._bg_color = color
        self._root.configure(bg=color)
        self._frame.configure(bg=color)

    def set_text_color(self, color: str) -> None:
        self._ensure_tk()
        self._text_color = color

    def set_font_size(self, size: int) -> None:
        self._ensure_tk()
        self._font_size = size

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
