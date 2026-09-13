"""Built-in arcade games for E++.

Four standalone canvas games, each in its own Toplevel (or Tk).
Palette: Catppuccin Mocha. Tick loop via root.after, never time.sleep.
"""

from __future__ import annotations

import os
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .interpreter import Interpreter

# ── Catppuccin Mocha palette ───────────────────────────────────────────────
_BASE    = "#1e1e2e"
_MANTLE  = "#181825"
_CRUST   = "#11111b"
_SURFACE = "#313244"
_OVERLAY = "#6c7086"
_TEXT    = "#cdd6f4"
_SUBTEXT = "#bac2de"
_RED     = "#f38ba8"
_PEACH   = "#fab387"
_YELLOW  = "#f9e2af"
_GREEN   = "#a6e3a1"
_TEAL    = "#94e2d5"
_SKY     = "#89dceb"
_BLUE    = "#89b4fa"
_MAUVE   = "#cba6f7"
_PINK    = "#f5c2e7"
_LAVENDER = "#b4befe"

TICK_MS = 16  # ~60 fps


# ══════════════════════════════════════════════════════════════════════════════
# FlappyBirdGame
# ══════════════════════════════════════════════════════════════════════════════

class FlappyBirdGame:
    W = 480
    H = 640
    GRAVITY      = 0.45
    JUMP_V       = -8.5
    PIPE_SPEED   = 3.0
    PIPE_GAP     = 160
    PIPE_INTERVAL = 90   # ticks between new pipes
    BIRD_R       = 14

    def __init__(self, root=None, interpreter: Interpreter | None = None):
        import tkinter as tk
        self._interpreter = interpreter
        self._own_root = root is None
        if self._own_root:
            self._win = tk.Tk()
        else:
            self._win = tk.Toplevel(root)

        self._win.title("E++ Flappy Bird")
        self._win.configure(bg=_BASE)
        self._win.resizable(False, False)

        self._canvas = tk.Canvas(
            self._win, width=self.W, height=self.H,
            bg=_BASE, highlightthickness=0,
        )
        self._canvas.pack()

        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        self._win.geometry(f"{self.W}x{self.H}+{(sw-self.W)//2}+{(sh-self.H)//2}")

        self._running = False
        self._after_id = None
        self._win.bind("<KeyPress>", self._on_key)
        self._canvas.bind("<Button-1>", self._on_click)
        self._win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._reset()

    def _reset(self):
        self._bird_y   = self.H / 2
        self._bird_vy  = 0.0
        self._pipes: list[dict] = []   # each: {x, top_h}
        self._ticks    = 0
        self._score    = 0
        self._game_over = False
        self._started  = False          # wait for first flap

    def _on_key(self, e):
        sym = e.keysym.lower()
        if sym in ("space", "up"):
            self._flap()
        elif sym == "r" and self._game_over:
            self._reset()
        elif sym == "escape":
            self._on_close()

    def _on_click(self, _e):
        self._flap()

    def _flap(self):
        if self._game_over:
            return
        self._started = True
        self._bird_vy = self.JUMP_V

    def _on_close(self):
        self._running = False
        if self._after_id:
            try:
                self._win.after_cancel(self._after_id)
            except Exception:
                pass
        try:
            self._win.destroy()
        except Exception:
            pass

    def start(self):
        self._running = True
        self._tick()
        try:
            self._win.mainloop()
        except Exception:
            pass
        finally:
            self._running = False

    def _tick(self):
        if not self._running:
            return
        try:
            if not self._game_over:
                self._update()
            self._render()
            self._after_id = self._win.after(TICK_MS, self._tick)
        except Exception:
            self._running = False

    def _update(self):
        if not self._started:
            return

        self._ticks += 1

        # Bird physics
        self._bird_vy += self.GRAVITY
        self._bird_vy = min(self._bird_vy, 12)
        self._bird_y  += self._bird_vy

        # Spawn pipes
        if self._ticks % self.PIPE_INTERVAL == 0:
            top_h = random.randint(60, self.H - self.PIPE_GAP - 60)
            self._pipes.append({"x": float(self.W), "top_h": top_h, "scored": False})

        # Move & score pipes
        alive = []
        for p in self._pipes:
            p["x"] -= self.PIPE_SPEED
            if p["x"] + 52 < 0:
                continue
            if not p["scored"] and p["x"] + 52 < 80:
                self._score += 1
                p["scored"] = True
            alive.append(p)
        self._pipes = alive

        # Collision: ceiling / floor
        bx, by = 80, self._bird_y
        r = self.BIRD_R
        if by - r <= 0 or by + r >= self.H:
            self._game_over = True
            return

        # Collision: pipes
        for p in self._pipes:
            px, tw = p["x"], 52
            bot_y  = p["top_h"] + self.PIPE_GAP
            # bird circle vs pipe rectangles
            if bx + r > px and bx - r < px + tw:
                if by - r < p["top_h"] or by + r > bot_y:
                    self._game_over = True
                    return

    def _render(self):
        c = self._canvas
        c.delete("all")
        W, H = self.W, self.H

        # Sky gradient (two rects)
        c.create_rectangle(0, 0, W, H // 2, fill=_MANTLE, outline="")
        c.create_rectangle(0, H // 2, W, H, fill=_BASE, outline="")

        # Ground
        c.create_rectangle(0, H - 40, W, H, fill=_SURFACE, outline="")
        c.create_rectangle(0, H - 40, W, H - 37, fill=_GREEN, outline="")

        # Pipes
        pipe_color = _GREEN
        pipe_edge  = "#74b884"
        for p in self._pipes:
            px, tw = int(p["x"]), 52
            th = p["top_h"]
            bot_y = th + self.PIPE_GAP
            # top pipe body
            c.create_rectangle(px, 0, px + tw, th, fill=pipe_color, outline="")
            # top pipe cap
            c.create_rectangle(px - 4, th - 14, px + tw + 4, th, fill=pipe_edge, outline="")
            # bottom pipe body
            c.create_rectangle(px, bot_y, px + tw, H - 40, fill=pipe_color, outline="")
            # bottom pipe cap
            c.create_rectangle(px - 4, bot_y, px + tw + 4, bot_y + 14, fill=pipe_edge, outline="")

        # Bird
        bx, by = 80, int(self._bird_y)
        r = self.BIRD_R
        # body
        c.create_oval(bx - r, by - r, bx + r, by + r, fill=_YELLOW, outline=_PEACH, width=2)
        # eye
        c.create_oval(bx + 4, by - 5, bx + 10, by + 1, fill=_BASE, outline="")
        c.create_oval(bx + 5, by - 4, bx + 9, by, fill="#ffffff", outline="")
        # beak
        c.create_polygon(bx + r - 2, by, bx + r + 8, by - 3, bx + r + 8, by + 3,
                         fill=_PEACH, outline="")
        # wing
        vy_clamped = max(-1, min(1, self._bird_vy / 8))
        wing_off = int(vy_clamped * 5)
        c.create_oval(bx - 10, by + 2 + wing_off, bx + 4, by + r + 2 + wing_off,
                      fill=_PEACH, outline="")

        # Score
        c.create_text(W // 2, 40, text=str(self._score),
                      fill=_TEXT, font=("monospace", 28, "bold"))

        # Waiting hint
        if not self._started and not self._game_over:
            c.create_text(W // 2, H // 2 - 30,
                          text="Press Space or click to start",
                          fill=_SUBTEXT, font=("monospace", 14))

        # Game over
        if self._game_over:
            c.create_rectangle(0, 0, W, H, fill=_CRUST, stipple="gray50", outline="")
            c.create_text(W // 2, H // 2 - 40, text="Game Over",
                          fill=_RED, font=("monospace", 36, "bold"))
            c.create_text(W // 2, H // 2 + 10, text=f"Score  {self._score}",
                          fill=_TEXT, font=("monospace", 20))
            c.create_text(W // 2, H // 2 + 50, text="R — restart   Esc — quit",
                          fill=_OVERLAY, font=("monospace", 13))


# ══════════════════════════════════════════════════════════════════════════════
# SnakeGame
# ══════════════════════════════════════════════════════════════════════════════

class SnakeGame:
    COLS  = 20
    ROWS  = 20
    CELL  = 28
    TICK  = 110  # ms per step

    def __init__(self, root=None, interpreter: Interpreter | None = None):
        import tkinter as tk
        self._interpreter = interpreter
        W = self.COLS * self.CELL
        H = self.ROWS * self.CELL + 40   # +40 for HUD

        self._own_root = root is None
        if self._own_root:
            self._win = tk.Tk()
        else:
            self._win = tk.Toplevel(root)

        self._win.title("E++ Snake")
        self._win.configure(bg=_BASE)
        self._win.resizable(False, False)

        self._canvas = tk.Canvas(
            self._win, width=W, height=H,
            bg=_BASE, highlightthickness=0,
        )
        self._canvas.pack()

        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        self._win.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        self._running  = False
        self._after_id = None
        self._win.bind("<KeyPress>", self._on_key)
        self._win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._reset()

    def _reset(self):
        cx, cy = self.COLS // 2, self.ROWS // 2
        self._snake  = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self._dir    = (1, 0)
        self._next_dir = (1, 0)
        self._food   = self._spawn_food()
        self._score  = 0
        self._game_over = False

    def _spawn_food(self):
        occupied = set(self._snake)
        while True:
            pos = (random.randint(0, self.COLS - 1), random.randint(0, self.ROWS - 1))
            if pos not in occupied:
                return pos

    def _on_key(self, e):
        sym = e.keysym.lower()
        dirs = {
            "up": (0, -1), "w": (0, -1),
            "down": (0, 1), "s": (0, 1),
            "left": (-1, 0), "a": (-1, 0),
            "right": (1, 0), "d": (1, 0),
        }
        if sym in dirs:
            nd = dirs[sym]
            # prevent 180° reversal
            if (nd[0] != -self._dir[0] or nd[1] != -self._dir[1]):
                self._next_dir = nd
        elif sym == "r" and self._game_over:
            self._reset()
        elif sym == "escape":
            self._on_close()

    def _on_close(self):
        self._running = False
        if self._after_id:
            try:
                self._win.after_cancel(self._after_id)
            except Exception:
                pass
        try:
            self._win.destroy()
        except Exception:
            pass

    def start(self):
        self._running = True
        self._tick()
        try:
            self._win.mainloop()
        except Exception:
            pass
        finally:
            self._running = False

    def _tick(self):
        if not self._running:
            return
        try:
            if not self._game_over:
                self._update()
            self._render()
            self._after_id = self._win.after(self.TICK, self._tick)
        except Exception:
            self._running = False

    def _update(self):
        self._dir = self._next_dir
        hx, hy = self._snake[0]
        nx = (hx + self._dir[0]) % self.COLS
        ny = (hy + self._dir[1]) % self.ROWS

        # Self-collision
        if (nx, ny) in self._snake:
            self._game_over = True
            return

        self._snake.insert(0, (nx, ny))

        if (nx, ny) == self._food:
            self._score += 1
            self._food = self._spawn_food()
        else:
            self._snake.pop()

    def _render(self):
        c = self._canvas
        c.delete("all")
        W = self.COLS * self.CELL
        H = self.ROWS * self.CELL + 40
        CS = self.CELL

        # Background grid
        c.create_rectangle(0, 0, W, H - 40, fill=_MANTLE, outline="")
        for gx in range(0, W + 1, CS):
            c.create_line(gx, 0, gx, H - 40, fill=_SURFACE, width=1)
        for gy in range(0, H - 40 + 1, CS):
            c.create_line(0, gy, W, gy, fill=_SURFACE, width=1)

        # Food (red apple-ish)
        fx, fy = self._food
        mx = fx * CS + CS // 2
        my = fy * CS + CS // 2
        r  = CS // 2 - 3
        c.create_oval(mx - r, my - r, mx + r, my + r, fill=_RED, outline="")
        c.create_line(mx, my - r, mx, my - r - 5, fill=_GREEN, width=2)

        # Snake
        for i, (sx, sy) in enumerate(self._snake):
            x1 = sx * CS + 2
            y1 = sy * CS + 2
            x2 = x1 + CS - 4
            y2 = y1 + CS - 4
            if i == 0:
                # head
                c.create_rectangle(x1, y1, x2, y2, fill=_GREEN, outline="", width=0)
                # eyes
                if self._dir == (1, 0):
                    ex, ey = x2 - 4, y1 + 4
                elif self._dir == (-1, 0):
                    ex, ey = x1 + 1, y1 + 4
                elif self._dir == (0, -1):
                    ex, ey = x1 + 4, y1 + 1
                else:
                    ex, ey = x1 + 4, y2 - 6
                c.create_oval(ex, ey, ex + 4, ey + 4, fill=_BASE, outline="")
            else:
                shade = _TEAL if i % 2 == 0 else _GREEN
                c.create_rectangle(x1, y1, x2, y2, fill=shade, outline="", width=0)

        # HUD bar
        c.create_rectangle(0, H - 40, W, H, fill=_SURFACE, outline="")
        c.create_text(10, H - 20, anchor="w",
                      text=f"Score: {self._score}   Length: {len(self._snake)}",
                      fill=_TEXT, font=("monospace", 14))

        # Game over
        if self._game_over:
            c.create_rectangle(0, 0, W, H - 40, fill=_CRUST, stipple="gray50", outline="")
            mid_y = (H - 40) // 2
            c.create_text(W // 2, mid_y - 35, text="Game Over",
                          fill=_RED, font=("monospace", 32, "bold"))
            c.create_text(W // 2, mid_y + 5, text=f"Score  {self._score}",
                          fill=_TEXT, font=("monospace", 18))
            c.create_text(W // 2, mid_y + 40, text="R — restart   Esc — quit",
                          fill=_OVERLAY, font=("monospace", 12))


# ══════════════════════════════════════════════════════════════════════════════
# PongGame
# ══════════════════════════════════════════════════════════════════════════════

class PongGame:
    W  = 640
    H  = 480
    PAD_H  = 80
    PAD_W  = 12
    PAD_SPEED     = 5.0
    CPU_SPEED     = 3.5
    BALL_INIT_SPD = 4.5
    WIN_SCORE     = 7

    def __init__(self, root=None, interpreter: Interpreter | None = None):
        import tkinter as tk
        self._interpreter = interpreter
        self._own_root = root is None
        if self._own_root:
            self._win = tk.Tk()
        else:
            self._win = tk.Toplevel(root)

        self._win.title("E++ Pong")
        self._win.configure(bg=_BASE)
        self._win.resizable(False, False)

        self._canvas = tk.Canvas(
            self._win, width=self.W, height=self.H,
            bg=_BASE, highlightthickness=0,
        )
        self._canvas.pack()

        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        self._win.geometry(f"{self.W}x{self.H}+{(sw-self.W)//2}+{(sh-self.H)//2}")

        self._running  = False
        self._after_id = None
        self._keys: set[str] = set()
        self._win.bind("<KeyPress>",   self._on_key_down)
        self._win.bind("<KeyRelease>", self._on_key_up)
        self._win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._score_player = 0
        self._score_cpu    = 0
        self._game_over    = False
        self._winner       = ""
        self._reset_round()

    def _reset_round(self):
        self._ball_x  = float(self.W // 2)
        self._ball_y  = float(self.H // 2)
        angle = random.uniform(-0.6, 0.6)
        spd   = self.BALL_INIT_SPD
        import math
        dirx = random.choice([-1, 1])
        self._ball_vx = dirx * spd * math.cos(angle)
        self._ball_vy = spd * math.sin(angle)
        self._ball_spd = spd

        self._player_y = float(self.H // 2 - self.PAD_H // 2)
        self._cpu_y    = float(self.H // 2 - self.PAD_H // 2)

    def _on_key_down(self, e):
        self._keys.add(e.keysym.lower())
        if self._game_over and e.keysym.lower() == "r":
            self._score_player = 0
            self._score_cpu    = 0
            self._game_over    = False
            self._winner       = ""
            self._reset_round()
        elif e.keysym.lower() == "escape":
            self._on_close()

    def _on_key_up(self, e):
        self._keys.discard(e.keysym.lower())

    def _on_close(self):
        self._running = False
        if self._after_id:
            try:
                self._win.after_cancel(self._after_id)
            except Exception:
                pass
        try:
            self._win.destroy()
        except Exception:
            pass

    def start(self):
        self._running = True
        self._tick()
        try:
            self._win.mainloop()
        except Exception:
            pass
        finally:
            self._running = False

    def _tick(self):
        if not self._running:
            return
        try:
            if not self._game_over:
                self._update()
            self._render()
            self._after_id = self._win.after(TICK_MS, self._tick)
        except Exception:
            self._running = False

    def _update(self):
        import math
        H, W = self.H, self.W
        PAD_H, PAD_W = self.PAD_H, self.PAD_W

        # Player movement (W/S or Up/Down)
        if "up" in self._keys or "w" in self._keys:
            self._player_y -= self.PAD_SPEED
        if "down" in self._keys or "s" in self._keys:
            self._player_y += self.PAD_SPEED
        self._player_y = max(0, min(H - PAD_H, self._player_y))

        # CPU tracks ball with limited speed
        cpu_center = self._cpu_y + PAD_H / 2
        diff = self._ball_y - cpu_center
        move = max(-self.CPU_SPEED, min(self.CPU_SPEED, diff))
        self._cpu_y += move
        self._cpu_y = max(0, min(H - PAD_H, self._cpu_y))

        # Move ball
        self._ball_x += self._ball_vx
        self._ball_y += self._ball_vy

        # Bounce top / bottom
        if self._ball_y <= 6:
            self._ball_y  = 6
            self._ball_vy = abs(self._ball_vy)
        if self._ball_y >= H - 6:
            self._ball_y  = H - 6
            self._ball_vy = -abs(self._ball_vy)

        # Bounce player paddle (left side, x = PAD_W+4)
        pl_x = PAD_W + 4
        if (self._ball_vx < 0 and
                pl_x <= self._ball_x <= pl_x + 8 and
                self._player_y - 6 <= self._ball_y <= self._player_y + PAD_H + 6):
            rel = (self._ball_y - (self._player_y + PAD_H / 2)) / (PAD_H / 2)
            rel = max(-1.0, min(1.0, rel))
            angle = rel * 1.1
            self._ball_spd = min(self._ball_spd + 0.2, 12)
            spd = self._ball_spd
            self._ball_vx =  abs(math.cos(angle)) * spd
            self._ball_vy =  math.sin(angle) * spd
            self._ball_x  = pl_x + 9

        # Bounce CPU paddle (right side)
        cr_x = W - PAD_W - 12
        if (self._ball_vx > 0 and
                cr_x <= self._ball_x <= cr_x + 8 and
                self._cpu_y - 6 <= self._ball_y <= self._cpu_y + PAD_H + 6):
            rel = (self._ball_y - (self._cpu_y + PAD_H / 2)) / (PAD_H / 2)
            rel = max(-1.0, min(1.0, rel))
            angle = rel * 1.1
            self._ball_spd = min(self._ball_spd + 0.2, 12)
            spd = self._ball_spd
            self._ball_vx = -abs(math.cos(angle)) * spd
            self._ball_vy =  math.sin(angle) * spd
            self._ball_x  = cr_x - 1

        # Score
        if self._ball_x < 0:
            self._score_cpu += 1
            self._check_win("CPU")
            if not self._game_over:
                self._reset_round()
        elif self._ball_x > W:
            self._score_player += 1
            self._check_win("You")
            if not self._game_over:
                self._reset_round()

    def _check_win(self, who: str):
        if self._score_player >= self.WIN_SCORE or self._score_cpu >= self.WIN_SCORE:
            self._game_over = True
            self._winner    = who

    def _render(self):
        c = self._canvas
        c.delete("all")
        W, H = self.W, self.H
        PAD_H, PAD_W = self.PAD_H, self.PAD_W

        # Background
        c.create_rectangle(0, 0, W, H, fill=_BASE, outline="")

        # Centre dashed line
        for dy in range(0, H, 20):
            c.create_line(W // 2, dy, W // 2, dy + 10, fill=_SURFACE, width=2)

        # Scores
        c.create_text(W // 4,     30, text=str(self._score_player),
                      fill=_BLUE, font=("monospace", 36, "bold"))
        c.create_text(W * 3 // 4, 30, text=str(self._score_cpu),
                      fill=_RED,  font=("monospace", 36, "bold"))
        c.create_text(W // 4 - 40, 60, text="You",
                      fill=_OVERLAY, font=("monospace", 11))
        c.create_text(W * 3 // 4 + 20, 60, text="CPU",
                      fill=_OVERLAY, font=("monospace", 11))

        # Player paddle
        px = 4
        c.create_rectangle(px, self._player_y,
                            px + PAD_W, self._player_y + PAD_H,
                            fill=_BLUE, outline="")

        # CPU paddle
        cx = W - PAD_W - 4
        c.create_rectangle(cx, self._cpu_y,
                            cx + PAD_W, self._cpu_y + PAD_H,
                            fill=_RED, outline="")

        # Ball
        br = 7
        bx, by = int(self._ball_x), int(self._ball_y)
        c.create_oval(bx - br, by - br, bx + br, by + br, fill=_YELLOW, outline="")

        # Controls hint
        c.create_text(10, H - 12, anchor="w",
                      text="W/S or ↑↓ to move",
                      fill=_OVERLAY, font=("monospace", 10))

        # Game over
        if self._game_over:
            c.create_rectangle(0, 0, W, H, fill=_CRUST, stipple="gray50", outline="")
            color = _BLUE if self._winner == "You" else _RED
            c.create_text(W // 2, H // 2 - 40,
                          text=f"{self._winner} win{'!' if self._winner == 'You' else 's.'}",
                          fill=color, font=("monospace", 36, "bold"))
            c.create_text(W // 2, H // 2 + 10,
                          text=f"{self._score_player} : {self._score_cpu}",
                          fill=_TEXT, font=("monospace", 24))
            c.create_text(W // 2, H // 2 + 55,
                          text="R — restart   Esc — quit",
                          fill=_OVERLAY, font=("monospace", 13))


# ══════════════════════════════════════════════════════════════════════════════
# MemoryGame
# ══════════════════════════════════════════════════════════════════════════════

_MEMORY_SYMBOLS = ["★", "♦", "♠", "♥", "●", "▲", "■", "✿"]
_MEMORY_COLORS  = [_BLUE, _RED, _MAUVE, _PINK, _GREEN, _PEACH, _TEAL, _YELLOW]

class MemoryGame:
    COLS      = 4
    ROWS      = 4
    CARD_W    = 90
    CARD_H    = 90
    PAD_X     = 20
    PAD_Y     = 20
    HUD_H     = 50
    FLIP_DELAY = 900   # ms to show mismatch before flipping back

    def __init__(self, root=None, interpreter: Interpreter | None = None):
        import tkinter as tk
        self._interpreter = interpreter
        W = self.COLS * (self.CARD_W + self.PAD_X) + self.PAD_X
        H = self.ROWS * (self.CARD_H + self.PAD_Y) + self.PAD_Y + self.HUD_H

        self._own_root = root is None
        if self._own_root:
            self._win = tk.Tk()
        else:
            self._win = tk.Toplevel(root)

        self._win.title("E++ Memory")
        self._win.configure(bg=_BASE)
        self._win.resizable(False, False)

        self._canvas = tk.Canvas(
            self._win, width=W, height=H,
            bg=_BASE, highlightthickness=0,
        )
        self._canvas.pack()

        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        self._win.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        self._W = W
        self._H = H
        self._running  = False
        self._after_id = None

        self._canvas.bind("<Button-1>", self._on_click)
        self._win.bind("<KeyPress>", self._on_key)
        self._win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._reset()

    def _reset(self):
        # Build deck: 8 pairs
        pairs = list(range(8)) * 2
        random.shuffle(pairs)
        self._cards = []
        for idx, val in enumerate(pairs):
            row = idx // self.COLS
            col = idx % self.COLS
            x1 = self.PAD_X + col * (self.CARD_W + self.PAD_X)
            y1 = self.HUD_H + self.PAD_Y + row * (self.CARD_H + self.PAD_Y)
            self._cards.append({
                "val":     val,
                "x1": x1, "y1": y1,
                "x2": x1 + self.CARD_W, "y2": y1 + self.CARD_H,
                "face_up": False,
                "matched": False,
            })

        self._flipped: list[int] = []   # indices of currently-revealed cards
        self._locked  = False           # block clicks while animating
        self._moves   = 0
        self._pairs   = 0
        self._game_over = False
        self._flip_after_id = None

    def _on_key(self, e):
        sym = e.keysym.lower()
        if sym == "r":
            self._cancel_flip()
            self._reset()
            self._render()
        elif sym == "escape":
            self._on_close()

    def _cancel_flip(self):
        if self._flip_after_id:
            try:
                self._win.after_cancel(self._flip_after_id)
            except Exception:
                pass
            self._flip_after_id = None

    def _on_click(self, event):
        if self._locked or self._game_over:
            return
        ex, ey = event.x, event.y
        for i, card in enumerate(self._cards):
            if (card["x1"] <= ex <= card["x2"] and
                    card["y1"] <= ey <= card["y2"] and
                    not card["face_up"] and not card["matched"]):
                self._reveal(i)
                break

    def _reveal(self, idx: int):
        card = self._cards[idx]
        card["face_up"] = True
        self._flipped.append(idx)
        self._render()

        if len(self._flipped) == 2:
            self._moves += 1
            self._locked = True
            a, b = self._flipped
            if self._cards[a]["val"] == self._cards[b]["val"]:
                self._cards[a]["matched"] = True
                self._cards[b]["matched"] = True
                self._pairs += 1
                self._flipped = []
                self._locked  = False
                if self._pairs == 8:
                    self._game_over = True
                self._render()
            else:
                self._flip_after_id = self._win.after(self.FLIP_DELAY, self._hide_two)

    def _hide_two(self):
        self._flip_after_id = None
        for i in self._flipped:
            self._cards[i]["face_up"] = False
        self._flipped = []
        self._locked  = False
        self._render()

    def _on_close(self):
        self._running = False
        self._cancel_flip()
        if self._after_id:
            try:
                self._win.after_cancel(self._after_id)
            except Exception:
                pass
        try:
            self._win.destroy()
        except Exception:
            pass

    def start(self):
        self._running = True
        self._render()
        try:
            self._win.mainloop()
        except Exception:
            pass
        finally:
            self._running = False

    def _render(self):
        if not self._running:
            return
        try:
            self._do_render()
        except Exception:
            pass

    def _do_render(self):
        import tkinter as tk
        c = self._canvas
        c.delete("all")
        W, H = self._W, self._H

        # Background
        c.create_rectangle(0, 0, W, H, fill=_BASE, outline="")

        # HUD
        c.create_rectangle(0, 0, W, self.HUD_H, fill=_MANTLE, outline="")
        c.create_text(15, self.HUD_H // 2, anchor="w",
                      text=f"Moves: {self._moves}",
                      fill=_TEXT, font=("monospace", 15, "bold"))
        c.create_text(W - 15, self.HUD_H // 2, anchor="e",
                      text=f"Pairs: {self._pairs}/8",
                      fill=_TEXT, font=("monospace", 15, "bold"))

        # Cards
        for card in self._cards:
            x1, y1, x2, y2 = card["x1"], card["y1"], card["x2"], card["y2"]
            val = card["val"]

            if card["matched"]:
                # Matched card: dimmed, show symbol
                c.create_rectangle(x1, y1, x2, y2, fill=_SURFACE, outline=_OVERLAY, width=1)
                sym   = _MEMORY_SYMBOLS[val]
                color = _MEMORY_COLORS[val]
                c.create_text((x1 + x2) // 2, (y1 + y2) // 2,
                              text=sym, fill=color,
                              font=("monospace", 32, "bold"))
                # tick
                c.create_text(x2 - 8, y1 + 10, text="✓", fill=_GREEN,
                              font=("monospace", 14, "bold"))
            elif card["face_up"]:
                # Revealed card
                color = _MEMORY_COLORS[val]
                c.create_rectangle(x1, y1, x2, y2, fill=_SURFACE,
                                   outline=color, width=3)
                sym = _MEMORY_SYMBOLS[val]
                c.create_text((x1 + x2) // 2, (y1 + y2) // 2,
                              text=sym, fill=color,
                              font=("monospace", 36, "bold"))
            else:
                # Face-down card
                c.create_rectangle(x1, y1, x2, y2, fill=_SURFACE,
                                   outline=_OVERLAY, width=2)
                # decorative pattern
                c.create_rectangle(x1 + 8, y1 + 8, x2 - 8, y2 - 8,
                                   fill="", outline=_OVERLAY, width=1)
                c.create_text((x1 + x2) // 2, (y1 + y2) // 2,
                              text="?", fill=_OVERLAY,
                              font=("monospace", 24, "bold"))

        # Win screen
        if self._game_over:
            c.create_rectangle(0, self.HUD_H, W, H,
                               fill=_CRUST, stipple="gray50", outline="")
            mid_y = (self.HUD_H + H) // 2
            c.create_text(W // 2, mid_y - 40, text="You win!",
                          fill=_GREEN, font=("monospace", 32, "bold"))
            c.create_text(W // 2, mid_y, text=f"{self._moves} moves",
                          fill=_TEXT, font=("monospace", 18))
            c.create_text(W // 2, mid_y + 40, text="R — play again   Esc — quit",
                          fill=_OVERLAY, font=("monospace", 12))


# ══════════════════════════════════════════════════════════════════════════════
# Public entry point
# ══════════════════════════════════════════════════════════════════════════════

_GAMES = {
    "flappy bird": FlappyBirdGame,
    "snake":       SnakeGame,
    "pong":        PongGame,
    "memory":      MemoryGame,
}


def launch_arcade_game(kind: str, interpreter=None, root=None) -> None:
    """Launch a built-in arcade game. kind is one of
    'flappy bird', 'snake', 'pong', 'memory'."""
    if os.environ.get("EPP_HEADLESS"):
        from .errors import EppRuntimeError
        raise EppRuntimeError("games are disabled in headless mode", 0)

    key = kind.lower().strip()
    if key not in _GAMES:
        from .errors import EppRuntimeError
        raise EppRuntimeError(
            f"unknown arcade game '{kind}' — choose one of: "
            + ", ".join(sorted(_GAMES)), 0
        )

    game = _GAMES[key](root=root, interpreter=interpreter)
    game.start()
