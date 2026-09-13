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
        self._base_font_size = _DEFAULT_FONT_SIZE
        self._font_size = _DEFAULT_FONT_SIZE
        self._font_family = None  # resolved on first use
        self._btn_bg = _DEFAULT_BTN_BG
        self._btn_fg = _DEFAULT_BTN_FG
        self._accent = _DEFAULT_ACCENT
        self._base_width = 600  # reference width for scaling
        self._widgets: list = []  # track widgets for responsive updates
        self._flow_frame = None  # compact button flow frame
        self._flow_count = 0  # buttons in current flow row
        self._game_canvas = None  # free-drawing canvas for sprites/shapes
        self._image_refs: list = []  # keep PhotoImage alive against the GC
        self._menubar = None  # top-level menu bar
        self._menus: dict = {}  # name -> cascade tk.Menu
        self._grid_columns = None  # set once arrange_grid() was used
        self._spacing = None  # uniform padding requested via add_spacing()

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
        # Scrollable container: canvas + scrollbar wrapping the frame
        self._scroll_canvas = tk.Canvas(self._root, bg=self._bg_color,
                                        highlightthickness=0)
        self._scrollbar = tk.Scrollbar(self._root, orient="vertical",
                                        command=self._scroll_canvas.yview)
        self._scroll_canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.pack(side="right", fill="y")
        self._scroll_canvas.pack(side="left", fill="both", expand=True)
        self._frame = tk.Frame(self._scroll_canvas, bg=self._bg_color)
        self._frame_window = self._scroll_canvas.create_window(
            (0, 0), window=self._frame, anchor="nw")
        self._frame.bind("<Configure>", self._on_frame_configure)
        self._scroll_canvas.bind("<Configure>", self._on_canvas_configure)
        # Mouse wheel scrolling
        self._root.bind("<MouseWheel>", self._on_mousewheel)
        self._root.bind("<Button-4>", self._on_mousewheel)
        self._root.bind("<Button-5>", self._on_mousewheel)
        self._root.bind("<Configure>", self._on_resize)

    def _on_frame_configure(self, event):
        """Update scroll region when frame content changes."""
        self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """Stretch frame to canvas width."""
        self._scroll_canvas.itemconfig(self._frame_window, width=event.width)

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling."""
        if event.num == 4:
            self._scroll_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._scroll_canvas.yview_scroll(1, "units")
        elif event.delta:
            self._scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _ensure_turtle(self):
        if self._turtle is not None:
            return
        self._ensure_tk()
        import tkinter as tk
        import turtle
        # Mark as initializing to prevent _on_resize from resizing the canvas
        self._turtle_init = True
        self._canvas = tk.Canvas(
            self._frame, width=400, height=300,
            bg="#181825", highlightthickness=1, highlightbackground="#45475a",
        )
        self._canvas.pack(pady=5)
        screen = turtle.TurtleScreen(self._canvas)
        screen.bgcolor("#181825")
        self._turtle = turtle.RawTurtle(screen)
        self._turtle.speed(3)
        self._turtle.hideturtle()
        self._turtle.pencolor(_DEFAULT_ACCENT)
        self._turtle_init = False

    def _on_resize(self, event):
        """Scale fonts and wraplength when window is resized."""
        if event.widget != self._root:
            return
        import tkinter as tk
        w = event.width
        scale = max(0.6, min(2.0, w / self._base_width))
        self._font_size = max(9, int(self._base_font_size * scale))
        pad_x = max(10, int(30 * scale))
        for widget, kind in self._widgets:
            try:
                widget.configure(font=self._font())
                if kind == "label":
                    widget.configure(wraplength=max(200, w - 60))
                elif kind in ("button", "entry"):
                    widget.pack_configure(padx=pad_x)
            except tk.TclError:
                pass
        if (self._canvas and self._canvas is not self._game_canvas
                and not self._turtle and not getattr(self, '_turtle_init', False)):
            try:
                cw = max(200, w - 80)
                ch = max(200, int(cw * 0.75))
                self._canvas.configure(width=cw, height=ch)
            except tk.TclError:
                pass

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
        label.pack(pady=self._spacing if self._spacing is not None else 4,
                   anchor="center")
        self._widgets.append((label, "label"))

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

        # Short text buttons (1-2 chars) use compact flow layout
        compact = len(text) <= 2
        if compact:
            parent = self._get_flow_frame()
            btn = tk.Button(
                parent, text=text, command=_on_click,
                fg=btn_fg, bg=btn_bg,
                activeforeground=btn_fg, activebackground=hover_bg,
                font=self._font(),
                relief="flat", cursor="hand2",
                width=3, height=1,
                borderwidth=0, highlightthickness=0,
            )
            btn.pack(side="left", padx=2, pady=2)
        else:
            self._flow_frame = None  # break flow on normal button
            btn = tk.Button(
                self._frame, text=text, command=_on_click,
                fg=btn_fg, bg=btn_bg,
                activeforeground=btn_fg, activebackground=hover_bg,
                font=self._font(),
                relief="flat", cursor="hand2",
                padx=16, pady=6,
                borderwidth=0, highlightthickness=0,
            )
            btn.pack(pady=self._spacing if self._spacing is not None else 4,
                     fill="x", padx=30)
        self._widgets.append((btn, "button"))

        def _on_enter(e):
            btn.configure(bg=hover_bg)
        def _on_leave(e):
            btn.configure(bg=btn_bg)
        btn.bind("<Enter>", _on_enter)
        btn.bind("<Leave>", _on_leave)

    def _get_flow_frame(self):
        """Get or create a wrapping frame for compact button flow layout."""
        import tkinter as tk
        if self._flow_frame and self._flow_frame.winfo_exists() and self._flow_count < 9:
            self._flow_count += 1
            return self._flow_frame
        self._flow_frame = tk.Frame(self._frame, bg=self._bg_color)
        self._flow_frame.pack(pady=2, padx=10, anchor="center")
        self._flow_count = 1
        return self._flow_frame

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
        self._widgets.append((entry, "entry"))
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
        self._game_canvas = None
        self._flow_frame = None
        self._flow_count = 0
        self._grid_columns = None
        self._image_refs.clear()
        self._widgets.clear()

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

    # ── GUI Extensions ────────────────────────────────────────────────

    def add_dropdown(self, name: str, options: list[str]) -> None:
        self._ensure_tk()
        import tkinter as tk
        var = tk.StringVar(self._root, value=options[0] if options else "")

        def _on_change(*_):
            self._interpreter.globals.define(f"__dropdown_{name}", var.get())

        var.trace_add("write", _on_change)
        # Set initial value
        self._interpreter.globals.define(f"__dropdown_{name}", var.get())

        menu = tk.OptionMenu(self._frame, var, *options)
        menu.configure(
            fg=self._text_color, bg=_DEFAULT_BTN_BG,
            activeforeground=self._text_color, activebackground=_DEFAULT_BTN_HOVER,
            font=self._font(), relief="flat", highlightthickness=0,
        )
        menu["menu"].configure(
            fg=self._text_color, bg=_DEFAULT_BTN_BG,
            activeforeground=self._text_color, activebackground=_DEFAULT_BTN_HOVER,
            font=self._font(),
        )
        menu.pack(pady=4, fill="x", padx=30)
        self._widgets.append((menu, "dropdown"))

    def add_table(self, name: str, columns: list[str]) -> None:
        self._ensure_tk()
        import tkinter as tk
        from tkinter import ttk

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Epp.Treeview",
                         background=_DEFAULT_BTN_BG, foreground=self._text_color,
                         fieldbackground=_DEFAULT_BTN_BG, font=self._font())
        style.configure("Epp.Treeview.Heading",
                         background="#45475a", foreground=self._text_color,
                         font=self._font(bold=True))

        tree = ttk.Treeview(self._frame, columns=columns, show="headings",
                            style="Epp.Treeview")
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor="center")
        tree.pack(pady=6, fill="both", expand=True, padx=30)
        self._interpreter.globals.define(f"__table_{name}", tree)

    def add_row(self, table_name: str, values: list[str]) -> None:
        tree = self._interpreter.globals.get(f"__table_{table_name}", 0)
        tree.insert("", "end", values=values)

    def clear_table(self, name: str) -> None:
        tree = self._interpreter.globals.get(f"__table_{name}", 0)
        for item in tree.get_children():
            tree.delete(item)

    def clear_text_box(self, name: str) -> None:
        self._ensure_tk()
        entry = self._interpreter.globals.get(f"__textbox_{name}", 0)
        entry.delete(0, "end")

    def show_message(self, text: str) -> None:
        self._ensure_tk()
        from tkinter import messagebox
        messagebox.showinfo("E++", text)

    def show_error(self, text: str) -> None:
        self._ensure_tk()
        from tkinter import messagebox
        messagebox.showerror("E++", text)

    # ── Real-time canvas ─────────────────────────────────────────────

    def ensure_root(self):
        """Create the Tk root if needed and hand it out (used by realtime.py)."""
        self._ensure_tk()
        return self._root

    def add_canvas(self, name: str, width: int, height: int) -> None:
        self._ensure_tk()
        import tkinter as tk
        canvas = tk.Canvas(
            self._frame, width=width, height=height,
            bg="#181825", highlightthickness=1, highlightbackground="#45475a",
        )
        canvas.pack(pady=6)
        self._game_canvas = canvas
        self._interpreter.globals.define(f"__canvas_{name}", canvas)

    def get_game_canvas(self):
        """Return the drawing surface, creating a default 800x600 one if needed."""
        self._ensure_tk()
        if self._game_canvas is None:
            self.add_canvas("canvas", 800, 600)
        return self._game_canvas

    # ── More input widgets ───────────────────────────────────────────

    def add_checkbox(self, name: str, label: str) -> None:
        self._ensure_tk()
        import tkinter as tk
        var = tk.BooleanVar(self._root, value=False)
        box = tk.Checkbutton(
            self._frame, text=label, variable=var,
            fg=self._text_color, bg=self._bg_color,
            activeforeground=self._text_color, activebackground=self._bg_color,
            selectcolor="#313244",
            font=self._font(), relief="flat", highlightthickness=0,
            borderwidth=0, anchor="w",
        )
        box.pack(pady=4, anchor="w", padx=30)
        self._widgets.append((box, "checkbox"))
        self._interpreter.globals.define(f"__checkbox_{name}", var)

    def checkbox_value(self, name: str) -> bool:
        var = self._interpreter.globals.get(f"__checkbox_{name}", 0)
        return bool(var.get())

    def add_radio_group(self, name: str, options: list[str]) -> None:
        self._ensure_tk()
        import tkinter as tk
        var = tk.StringVar(self._root, value=options[0] if options else "")
        group = tk.Frame(self._frame, bg=self._bg_color)
        for option in options:
            btn = tk.Radiobutton(
                group, text=option, variable=var, value=option,
                fg=self._text_color, bg=self._bg_color,
                activeforeground=self._text_color, activebackground=self._bg_color,
                selectcolor="#313244",
                font=self._font(), relief="flat", highlightthickness=0,
                borderwidth=0, anchor="w",
            )
            btn.pack(anchor="w")
        group.pack(pady=4, anchor="w", padx=30)
        self._widgets.append((group, "radio"))
        self._interpreter.globals.define(f"__radio_{name}", var)

    def radio_group_value(self, name: str) -> str:
        var = self._interpreter.globals.get(f"__radio_{name}", 0)
        return str(var.get())

    def add_slider(self, name: str, low: float, high: float) -> None:
        self._ensure_tk()
        import tkinter as tk
        slider = tk.Scale(
            self._frame, from_=low, to=high, orient="horizontal",
            fg=self._text_color, bg=self._bg_color,
            activebackground=_DEFAULT_ACCENT, troughcolor="#313244",
            font=self._font(), relief="flat", highlightthickness=0,
            borderwidth=0, showvalue=True,
        )
        slider.pack(pady=4, fill="x", padx=30)
        self._widgets.append((slider, "slider"))
        self._interpreter.globals.define(f"__slider_{name}", slider)

    def slider_value(self, name: str) -> float:
        slider = self._interpreter.globals.get(f"__slider_{name}", 0)
        return float(slider.get())

    def add_image(self, name: str, file_path: str) -> None:
        self._ensure_tk()
        import tkinter as tk
        photo = None
        try:
            photo = tk.PhotoImage(file=file_path)
        except Exception:
            photo = None
        if photo is None:
            label = tk.Label(
                self._frame, text=f"[image {name} not found]",
                fg=self._text_color, bg=self._bg_color, font=self._font(),
            )
        else:
            label = tk.Label(self._frame, image=photo, bg=self._bg_color,
                             borderwidth=0, highlightthickness=0)
            label.image = photo  # extra guard against garbage collection
            self._image_refs.append(photo)
            self._interpreter.globals.define(f"__image_{name}", photo)
        label.pack(pady=6, anchor="center")
        self._widgets.append((label, "image"))

    # ── Menus ────────────────────────────────────────────────────────

    def _ensure_menubar(self):
        import tkinter as tk
        if self._menubar is None:
            self._menubar = tk.Menu(
                self._root,
                bg=_DEFAULT_BTN_BG, fg=self._text_color,
                activebackground=_DEFAULT_BTN_HOVER,
                activeforeground=self._text_color,
                relief="flat", borderwidth=0,
            )
            self._root.configure(menu=self._menubar)
        return self._menubar

    def _ensure_menu(self, name: str):
        import tkinter as tk
        menubar = self._ensure_menubar()
        menu = self._menus.get(name)
        if menu is None:
            menu = tk.Menu(
                menubar, tearoff=0,
                bg=_DEFAULT_BTN_BG, fg=self._text_color,
                activebackground=_DEFAULT_BTN_HOVER,
                activeforeground=self._text_color,
                relief="flat", borderwidth=0,
            )
            menubar.add_cascade(label=name, menu=menu)
            self._menus[name] = menu
        return menu

    def add_menu(self, name: str, options: list[str]) -> None:
        self._ensure_tk()
        menu = self._ensure_menu(name)
        for option in options:
            menu.add_command(label=option, command=lambda: None)

    def add_menu_item(self, item: str, menu: str, fn_name: str) -> None:
        self._ensure_tk()
        import tkinter as tk
        target = self._ensure_menu(menu)

        def _on_select():
            try:
                self._interpreter.call_function_by_name(fn_name)
            except tk.TclError:
                pass

        wanted = " ".join(item.split()).lower()
        try:
            last = target.index("end")
        except tk.TclError:
            last = None
        if last is not None:
            for index in range(last + 1):
                try:
                    label = target.entrycget(index, "label")
                except tk.TclError:
                    continue
                if " ".join(str(label).split()).lower() == wanted:
                    target.entryconfigure(index, command=_on_select)
                    return
        target.add_command(label=item, command=_on_select)

    # ── Layout ───────────────────────────────────────────────────────

    def arrange_grid(self, columns: int) -> None:
        self._ensure_tk()
        import tkinter as tk
        columns = max(1, int(columns))
        self._grid_columns = columns
        pad = self._spacing if self._spacing is not None else 4
        for index, (widget, _kind) in enumerate(self._widgets):
            try:
                widget.pack_forget()
                widget.grid(row=index // columns, column=index % columns,
                            sticky="nsew", padx=pad, pady=pad)
            except tk.TclError:
                pass
        for column in range(columns):
            try:
                self._frame.grid_columnconfigure(column, weight=1)
            except tk.TclError:
                pass

    def add_spacing(self, amount: int) -> None:
        self._ensure_tk()
        import tkinter as tk
        amount = max(0, int(amount))
        self._spacing = amount
        for widget, _kind in self._widgets:
            try:
                if self._grid_columns is not None:
                    widget.grid_configure(padx=amount, pady=amount)
                else:
                    widget.pack_configure(padx=amount, pady=amount)
            except tk.TclError:
                pass

    def align_widget(self, kind: str, name: str, alignment: str) -> None:
        self._ensure_tk()
        import tkinter as tk
        anchors = {"left": "w", "center": "center", "right": "e"}
        justifies = {"left": "left", "center": "center", "right": "right"}
        key = alignment.strip().lower()
        anchor = anchors.get(key, "center")
        justify = justifies.get(key, "center")

        widget = None
        if kind == "text box":
            try:
                widget = self._interpreter.globals.get(f"__textbox_{name}", 0)
            except Exception:
                widget = None
        else:
            wanted = " ".join(name.split()).lower()
            for candidate, candidate_kind in self._widgets:
                if candidate_kind != kind:
                    continue
                try:
                    text = candidate.cget("text")
                except tk.TclError:
                    continue
                if " ".join(str(text).split()).lower() == wanted:
                    widget = candidate
                    break
        if widget is None:
            return
        try:
            widget.configure(anchor=anchor)
        except tk.TclError:
            pass
        try:
            widget.configure(justify=justify)
        except tk.TclError:
            pass
        try:
            widget.pack_configure(anchor=anchor)
        except tk.TclError:
            pass

    # ── Dialogs ──────────────────────────────────────────────────────

    def ask_yes_or_no(self, message: str) -> bool:
        self._ensure_tk()
        from tkinter import messagebox
        return bool(messagebox.askyesno("E++", message))

    def ask_for_file(self, mode: str) -> str:
        self._ensure_tk()
        from tkinter import filedialog
        if mode == "save":
            path = filedialog.asksaveasfilename()
        else:
            path = filedialog.askopenfilename()
        return path or ""

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

    def turtle_goto(self, x: int, y: int) -> None:
        self._ensure_turtle()
        self._turtle.goto(x, y)

    def turtle_set_color(self, color: str) -> None:
        self._ensure_turtle()
        self._turtle.pencolor(color)

    def turtle_set_speed(self, speed: int) -> None:
        self._ensure_turtle()
        self._turtle.speed(speed)

    def turtle_set_size(self, size: int) -> None:
        self._ensure_turtle()
        self._turtle.pensize(size)

    def turtle_circle(self, radius: int) -> None:
        self._ensure_turtle()
        self._turtle.circle(radius)
