"""Real-time engine for E++: tick loops, key and mouse events, sprites, shapes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .errors import EppError, EppRuntimeError

if TYPE_CHECKING:
    from .interpreter import Interpreter
    from .visuals import Visuals


# Catppuccin Mocha palette — used for sprite placeholders
_PLACEHOLDER_COLORS = (
    "#89b4fa", "#a6e3a1", "#f38ba8", "#fab387",
    "#cba6f7", "#f5c2e7", "#94e2d5", "#f9e2af",
)

_PLACEHOLDER_SIZE = 32

# keysym aliases so that E++ programs can say `key spacebar`, `key arrow left`, ...
_KEY_ALIASES = {
    "spacebar": "space",
    "space bar": "space",
    "enter": "return",
    "esc": "escape",
    "arrow left": "left",
    "left arrow": "left",
    "arrow right": "right",
    "right arrow": "right",
    "arrow up": "up",
    "up arrow": "up",
    "arrow down": "down",
    "down arrow": "down",
    "ctrl": "control",
    "control left": "control_l",
    "control right": "control_r",
    "shift left": "shift_l",
    "shift right": "shift_r",
    "alt": "alt_l",
    "backspace": "backspace",
    "del": "delete",
    "page up": "prior",
    "page down": "next",
}


def _normalize_key(keysym: str) -> str:
    """Fold a Tk keysym or an E++ key name onto one canonical lowercase name."""
    name = " ".join(str(keysym).split()).lower()
    return _KEY_ALIASES.get(name, name)


class Realtime:
    def __init__(self, interpreter: Interpreter, visuals: Visuals):
        self._interpreter = interpreter
        self._visuals = visuals
        self._ticks: list[dict] = []
        self._keys_bound = False
        self._mouse_bound = False
        self._pressed: set[str] = set()
        self._key_handlers: dict[str, list[dict]] = {}
        self._mouse_handlers: dict[str, list[dict]] = {}
        self._mouse_x = 0.0
        self._mouse_y = 0.0
        self._sprites: dict[str, dict] = {}
        self._image_refs: list = []
        self._shapes: list = []
        self._placeholder_index = 0
        self._mainloop_entered = False

    # ── Internals ────────────────────────────────────────────────────

    def _root(self):
        return self._visuals.ensure_root()

    def _canvas(self):
        return self._visuals.get_game_canvas()

    def _report(self, message: str) -> None:
        try:
            self._interpreter._say_fn(message)
        except Exception:
            pass

    def _run_body(self, state: dict, body: list, env) -> bool:
        """Run one callback body. Returns False when the handler must stop."""
        import tkinter as tk
        try:
            self._interpreter.exec_block(body, env)
        except EppError as err:
            state["stopped"] = True
            self._report(getattr(err, "message", str(err)))
            return False
        except tk.TclError:
            state["stopped"] = True
            return False
        except Exception as err:
            state["stopped"] = True
            self._report(f"Problem while running: {err}")
            return False
        return True

    # ── Ticks ────────────────────────────────────────────────────────

    def add_tick(self, interval_ms: int, body: list, env) -> None:
        root = self._root()
        interval = max(1, int(interval_ms))
        state = {"stopped": False, "after_id": None}
        self._ticks.append(state)

        def _tick():
            state["after_id"] = None
            if state["stopped"]:
                return
            # the body may contain `Stop ticking.`, so re-check afterwards
            if not self._run_body(state, body, env):
                return
            if state["stopped"]:
                return
            state["after_id"] = root.after(interval, _tick)

        state["after_id"] = root.after(interval, _tick)

    def stop_ticking(self) -> None:
        import tkinter as tk
        root = self._visuals._root
        for state in self._ticks:
            state["stopped"] = True
            after_id = state.get("after_id")
            state["after_id"] = None
            if after_id is not None and root is not None:
                try:
                    root.after_cancel(after_id)
                except (tk.TclError, ValueError):
                    pass

    # ── Keyboard ─────────────────────────────────────────────────────

    def _bind_keys(self) -> None:
        if self._keys_bound:
            return
        root = self._root()

        def _on_press(event):
            key = _normalize_key(event.keysym)
            was_down = key in self._pressed
            self._pressed.add(key)
            if was_down:
                return  # ignore the system's auto-repeat
            for state in list(self._key_handlers.get(key, ())):
                if state["stopped"]:
                    continue
                self._run_body(state, state["body"], state["env"])

        def _on_release(event):
            self._pressed.discard(_normalize_key(event.keysym))

        root.bind_all("<KeyPress>", _on_press, add="+")
        root.bind_all("<KeyRelease>", _on_release, add="+")
        self._keys_bound = True

    def is_key_pressed(self, key: str) -> bool:
        self._bind_keys()
        return _normalize_key(key) in self._pressed

    def add_key_handler(self, key: str, body: list, env) -> None:
        self._bind_keys()
        name = _normalize_key(key)
        state = {"stopped": False, "body": body, "env": env}
        self._key_handlers.setdefault(name, []).append(state)

    # ── Mouse ────────────────────────────────────────────────────────

    def _bind_mouse(self) -> None:
        if self._mouse_bound:
            return
        root = self._root()

        def _track(event):
            self._mouse_x, self._mouse_y = self._to_canvas_coords(event)

        def _on_click(event):
            _track(event)
            for state in list(self._mouse_handlers.get("clicked", ())):
                if state["stopped"]:
                    continue
                self._run_body(state, state["body"], state["env"])

        root.bind_all("<Motion>", _track, add="+")
        root.bind_all("<Button-1>", _on_click, add="+")
        self._mouse_bound = True

    def _to_canvas_coords(self, event) -> tuple[float, float]:
        import tkinter as tk
        canvas = self._visuals._game_canvas
        if canvas is None:
            return float(event.x), float(event.y)
        if event.widget is canvas:
            return float(event.x), float(event.y)
        try:
            root = self._visuals._root
            x = root.winfo_pointerx() - canvas.winfo_rootx()
            y = root.winfo_pointery() - canvas.winfo_rooty()
            return float(x), float(y)
        except (tk.TclError, AttributeError):
            return float(event.x), float(event.y)

    def add_mouse_handler(self, event: str, body: list, env) -> None:
        self._bind_mouse()
        state = {"stopped": False, "body": body, "env": env}
        self._mouse_handlers.setdefault(event, []).append(state)

    def mouse_coord(self, axis: str) -> float:
        self._bind_mouse()
        return float(self._mouse_y if axis == "y" else self._mouse_x)

    # ── Sprites ──────────────────────────────────────────────────────

    def _get_sprite(self, name: str, line: int) -> dict:
        sprite = self._sprites.get(name)
        if sprite is None:
            raise EppRuntimeError(f"the sprite {name!r} does not exist", line)
        return sprite

    def _next_placeholder_color(self) -> str:
        color = _PLACEHOLDER_COLORS[self._placeholder_index % len(_PLACEHOLDER_COLORS)]
        self._placeholder_index += 1
        return color

    def add_sprite(self, name: str, image_path: str | None, line: int) -> None:
        import tkinter as tk
        canvas = self._canvas()
        photo = None
        if image_path:
            try:
                photo = tk.PhotoImage(file=image_path)
            except Exception:
                photo = None
        if photo is not None:
            item = canvas.create_image(0, 0, image=photo, anchor="nw")
            self._image_refs.append(photo)
            width = photo.width()
            height = photo.height()
        else:
            item = canvas.create_rectangle(
                0, 0, _PLACEHOLDER_SIZE, _PLACEHOLDER_SIZE,
                fill=self._next_placeholder_color(), outline="",
            )
            width = height = _PLACEHOLDER_SIZE
        self._sprites[name] = {
            "item": item, "image": photo,
            "x": 0.0, "y": 0.0, "w": width, "h": height,
        }

    def set_sprite_position(self, name: str, x: float, y: float, line: int) -> None:
        import tkinter as tk
        sprite = self._get_sprite(name, line)
        canvas = self._canvas()
        sprite["x"] = float(x)
        sprite["y"] = float(y)
        try:
            if sprite["image"] is not None:
                canvas.coords(sprite["item"], float(x), float(y))
            else:
                canvas.coords(sprite["item"], float(x), float(y),
                              float(x) + sprite["w"], float(y) + sprite["h"])
        except tk.TclError:
            pass

    def move_sprite(self, name: str, dx: float, dy: float, line: int) -> None:
        import tkinter as tk
        sprite = self._get_sprite(name, line)
        canvas = self._canvas()
        sprite["x"] += float(dx)
        sprite["y"] += float(dy)
        try:
            canvas.move(sprite["item"], float(dx), float(dy))
        except tk.TclError:
            pass

    def sprite_coord(self, name: str, axis: str, line: int) -> float:
        sprite = self._get_sprite(name, line)
        return float(sprite["y"] if axis == "y" else sprite["x"])

    def sprites_collide(self, a: str, b: str, line: int) -> bool:
        import tkinter as tk
        first = self._get_sprite(a, line)
        second = self._get_sprite(b, line)
        canvas = self._canvas()
        try:
            box_a = canvas.bbox(first["item"])
            box_b = canvas.bbox(second["item"])
        except tk.TclError:
            return False
        if not box_a or not box_b:
            return False
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        return ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2

    def remove_sprite(self, name: str, line: int) -> None:
        import tkinter as tk
        sprite = self._get_sprite(name, line)
        canvas = self._canvas()
        try:
            canvas.delete(sprite["item"])
        except tk.TclError:
            pass
        del self._sprites[name]

    # ── Shapes ───────────────────────────────────────────────────────

    def draw_rectangle(self, x, y, width, height, color: str) -> None:
        canvas = self._canvas()
        item = canvas.create_rectangle(
            float(x), float(y), float(x) + float(width), float(y) + float(height),
            fill=color, outline="",
        )
        self._shapes.append(item)

    def draw_circle(self, x, y, radius, color: str) -> None:
        canvas = self._canvas()
        item = canvas.create_oval(
            float(x) - float(radius), float(y) - float(radius),
            float(x) + float(radius), float(y) + float(radius),
            fill=color, outline="",
        )
        self._shapes.append(item)

    def draw_text(self, text: str, x, y, color: str) -> None:
        canvas = self._canvas()
        item = canvas.create_text(
            float(x), float(y), text=text, fill=color,
            font=("TkDefaultFont", 16, "bold"), anchor="center",
        )
        self._shapes.append(item)

    def clear_canvas(self) -> None:
        import tkinter as tk
        canvas = self._canvas()
        for item in self._shapes:
            try:
                canvas.delete(item)
            except tk.TclError:
                pass
        self._shapes.clear()

    # ── Mainloop ─────────────────────────────────────────────────────

    def needs_mainloop(self) -> bool:
        if self._mainloop_entered:
            return False
        if not (self._ticks or self._key_handlers or self._mouse_handlers):
            return False
        self._mainloop_entered = True
        return True
