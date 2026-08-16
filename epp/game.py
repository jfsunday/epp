"""2D jump'n'run game engine for E++.

A canvas-based side-scrolling platformer with procedural level generation.
Each run is unique — chunks are assembled from varied patterns with randomized
parameters (heights, widths, gaps, colors, decorations).

Controls: Left/Right arrow or A/D to move, Space or Up to jump.
"""

from __future__ import annotations

import math
import os
import random
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .interpreter import Interpreter


# ── Constants ─────────────────────────────────────────────────────────

TICK_MS = 16          # ~60 fps
GRAVITY = 0.6
JUMP_FORCE = -11.5
MOVE_SPEED = 5
MAX_FALL_SPEED = 12

PLAYER_W = 24
PLAYER_H = 32

GROUND_Y_RATIO = 0.82  # ground sits at 82% of canvas height

# Colors — Catppuccin Mocha palette
BG_COLORS = ["#1e1e2e", "#181825", "#11111b"]
PLATFORM_PALETTES = [
    {"top": "#89b4fa", "body": "#313244", "accent": "#74c7ec"},
    {"top": "#a6e3a1", "body": "#313244", "accent": "#94e2d5"},
    {"top": "#f38ba8", "body": "#313244", "accent": "#eba0ac"},
    {"top": "#fab387", "body": "#313244", "accent": "#f9e2af"},
    {"top": "#cba6f7", "body": "#313244", "accent": "#b4befe"},
    {"top": "#f5c2e7", "body": "#313244", "accent": "#f2cdcd"},
]
PLAYER_COLOR = "#89dceb"
PLAYER_EYE = "#1e1e2e"
STAR_COLOR = "#f9e2af"
CLOUD_COLOR = "#45475a"
SCORE_COLOR = "#cdd6f4"
GAMEOVER_COLOR = "#f38ba8"


# ── Chunk Generators ──────────────────────────────────────────────────

def _gen_flat_run(x: float, y: float, difficulty: float) -> list[dict]:
    """A simple flat platform run."""
    w = random.randint(120, 250 - int(difficulty * 8))
    return [{"x": x, "y": y, "w": max(60, w), "h": 18}]


def _gen_staircase_up(x: float, y: float, difficulty: float) -> list[dict]:
    """Ascending staircase of 2-4 platforms."""
    steps = random.randint(2, min(4, 2 + int(difficulty * 0.3)))
    plats = []
    cx, cy = x, y
    for _ in range(steps):
        w = random.randint(60, 120)
        plats.append({"x": cx, "y": cy, "w": w, "h": 16})
        cx += w + random.randint(30, 60)
        cy -= random.randint(35, 55)
    return plats


def _gen_staircase_down(x: float, y: float, difficulty: float) -> list[dict]:
    """Descending staircase."""
    steps = random.randint(2, 3)
    plats = []
    cx, cy = x, y
    for _ in range(steps):
        w = random.randint(60, 130)
        plats.append({"x": cx, "y": cy, "w": w, "h": 16})
        cx += w + random.randint(25, 55)
        cy += random.randint(30, 50)
    return plats


def _gen_floating_islands(x: float, y: float, difficulty: float) -> list[dict]:
    """Small floating platforms at varied heights."""
    count = random.randint(2, 4)
    plats = []
    cx = x
    for _ in range(count):
        w = random.randint(45, 90)
        offset_y = random.randint(-80, 40)
        plats.append({"x": cx, "y": y + offset_y, "w": w, "h": 14})
        cx += w + random.randint(50, 90 + int(difficulty * 5))
    return plats


def _gen_gap_jump(x: float, y: float, difficulty: float) -> list[dict]:
    """Two platforms with a significant gap between them."""
    w1 = random.randint(80, 160)
    gap = random.randint(60, 100 + int(difficulty * 8))
    w2 = random.randint(80, 160)
    drop = random.randint(-20, 20)
    return [
        {"x": x, "y": y, "w": w1, "h": 18},
        {"x": x + w1 + gap, "y": y + drop, "w": w2, "h": 18},
    ]


def _gen_zigzag(x: float, y: float, difficulty: float) -> list[dict]:
    """Alternating high-low platforms."""
    count = random.randint(3, 5)
    plats = []
    cx = x
    for i in range(count):
        w = random.randint(50, 90)
        offset = -50 if i % 2 == 0 else 30
        plats.append({"x": cx, "y": y + offset, "w": w, "h": 14})
        cx += w + random.randint(40, 70)
    return plats


CHUNK_GENERATORS = [
    _gen_flat_run,
    _gen_staircase_up,
    _gen_staircase_down,
    _gen_floating_islands,
    _gen_gap_jump,
    _gen_zigzag,
]


# ── Decoration Generators ────────────────────────────────────────────

def _make_stars(cam_x: float, canvas_w: int, canvas_h: int, seed: int) -> list[tuple]:
    """Generate background stars based on camera position."""
    rng = random.Random(seed)
    stars = []
    # Stars repeat in bands of 800px
    band_start = int(cam_x // 800) * 800 - 800
    band_end = int(cam_x + canvas_w) + 800
    for bx in range(band_start, band_end, 800):
        rng2 = random.Random(seed ^ (bx * 7919))
        count = rng2.randint(8, 18)
        for _ in range(count):
            sx = bx + rng2.randint(0, 800)
            sy = rng2.randint(10, int(canvas_h * 0.6))
            size = rng2.choice([1, 1, 1, 2, 2, 3])
            stars.append((sx, sy, size))
    return stars


def _make_clouds(cam_x: float, canvas_w: int, canvas_h: int, seed: int) -> list[tuple]:
    """Generate parallax clouds."""
    rng = random.Random(seed + 42)
    clouds = []
    band_start = int(cam_x * 0.3 // 600) * 600 - 600
    band_end = int((cam_x + canvas_w) * 0.3) + 600
    for bx in range(band_start, band_end, 600):
        rng2 = random.Random(seed ^ (bx * 3571))
        count = rng2.randint(1, 3)
        for _ in range(count):
            cx = bx + rng2.randint(0, 600)
            cy = rng2.randint(30, int(canvas_h * 0.35))
            w = rng2.randint(60, 140)
            h = rng2.randint(20, 40)
            clouds.append((cx, cy, w, h))
    return clouds


# ── Game Class ────────────────────────────────────────────────────────

class JumpAndRunGame:
    def __init__(self, root=None, interpreter: Interpreter | None = None):
        import tkinter as tk

        self._interpreter = interpreter
        self._own_root = root is None
        if self._own_root:
            self._root = tk.Tk()
        else:
            self._root = root

        self._root.title("E++ Jump and Run")
        self._root.configure(bg="#1e1e2e")

        # Canvas fills the window
        self._canvas = tk.Canvas(
            self._root, bg="#1e1e2e",
            highlightthickness=0,
        )
        self._canvas.pack(fill="both", expand=True)

        # Set initial size and center
        self._root.geometry("900x550")
        self._root.update_idletasks()
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        self._root.geometry(f"900x550+{(sw-900)//2}+{(sh-550)//2}")
        self._root.minsize(600, 400)

        # Game state
        self._running = False
        self._game_over = False
        self._score = 0
        self._high_score = 0
        self._seed = random.randint(0, 2**31)

        # Player
        self._px = 100.0
        self._py = 300.0
        self._vx = 0.0
        self._vy = 0.0
        self._on_ground = False
        self._facing_right = True

        # World
        self._platforms: list[dict] = []
        self._cam_x = 0.0
        self._furthest_x = 0.0
        self._difficulty = 0.0
        self._palette = random.choice(PLATFORM_PALETTES)
        self._bg_color = random.choice(BG_COLORS)

        # Keys
        self._keys: set[str] = set()
        self._root.bind("<KeyPress>", self._key_down)
        self._root.bind("<KeyRelease>", self._key_up)
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        self._canvas_w = 900
        self._canvas_h = 550

        self._init_world()

    def _on_canvas_resize(self, event):
        self._canvas_w = event.width
        self._canvas_h = event.height

    def _key_down(self, e):
        self._keys.add(e.keysym.lower())
        if self._game_over and e.keysym.lower() in ("space", "return"):
            self._restart()

    def _key_up(self, e):
        self._keys.discard(e.keysym.lower())

    def _init_world(self):
        """Generate the starting platforms."""
        self._platforms.clear()
        ground_y = self._canvas_h * GROUND_Y_RATIO

        # Spawn platform under player
        self._platforms.append({"x": 0, "y": ground_y, "w": 300, "h": 20})
        self._py = ground_y - PLAYER_H
        self._furthest_x = 300
        self._difficulty = 0.0

        # Generate initial chunks
        for _ in range(8):
            self._generate_chunk()

    def _generate_chunk(self):
        """Append a new procedural chunk to the world."""
        # Pick a generator, avoiding the same one twice in a row
        gen = random.choice(CHUNK_GENERATORS)
        gap_before = random.randint(30, 70 + int(self._difficulty * 3))
        base_y = self._canvas_h * GROUND_Y_RATIO + random.randint(-30, 30)

        new_plats = gen(self._furthest_x + gap_before, base_y, self._difficulty)

        # Vary the palette occasionally
        if random.random() < 0.25:
            self._palette = random.choice(PLATFORM_PALETTES)

        for p in new_plats:
            p["palette"] = dict(self._palette)
            self._platforms.append(p)

        if new_plats:
            rightmost = max(p["x"] + p["w"] for p in new_plats)
            self._furthest_x = max(self._furthest_x, rightmost)

        self._difficulty = min(10, self._difficulty + 0.15)

    def _restart(self):
        """Reset for a new run."""
        self._seed = random.randint(0, 2**31)
        self._px = 100.0
        self._py = 300.0
        self._vx = 0.0
        self._vy = 0.0
        self._on_ground = False
        self._facing_right = True
        self._cam_x = 0.0
        self._furthest_x = 0.0
        self._score = 0
        self._difficulty = 0.0
        self._game_over = False
        self._palette = random.choice(PLATFORM_PALETTES)
        self._bg_color = random.choice(BG_COLORS)
        self._keys.clear()
        self._init_world()

    def start(self):
        """Start the game loop and enter mainloop."""
        self._running = True
        self._tick()
        try:
            self._root.mainloop()
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
            self._root.after(TICK_MS, self._tick)
        except Exception:
            self._running = False

    # ── Physics ───────────────────────────────────────────────────────

    def _update(self):
        # Horizontal input
        move = 0
        if "left" in self._keys or "a" in self._keys:
            move -= 1
            self._facing_right = False
        if "right" in self._keys or "d" in self._keys:
            move += 1
            self._facing_right = True

        self._vx = move * MOVE_SPEED

        # Jump
        if self._on_ground and ("space" in self._keys or "up" in self._keys or "w" in self._keys):
            self._vy = JUMP_FORCE
            self._on_ground = False

        # Gravity
        self._vy = min(self._vy + GRAVITY, MAX_FALL_SPEED)

        # Move
        self._px += self._vx
        self._py += self._vy

        # Platform collision (only when falling)
        self._on_ground = False
        if self._vy >= 0:
            for p in self._platforms:
                px_right = self._px + PLAYER_W
                px_left = self._px
                if (px_right > p["x"] and px_left < p["x"] + p["w"]):
                    player_bottom = self._py + PLAYER_H
                    plat_top = p["y"]
                    if player_bottom >= plat_top and player_bottom <= plat_top + p["h"] + self._vy + 2:
                        self._py = plat_top - PLAYER_H
                        self._vy = 0
                        self._on_ground = True
                        break

        # Prevent going left of start
        if self._px < 0:
            self._px = 0

        # Score = furthest distance
        dist = int(self._px / 10)
        if dist > self._score:
            self._score = dist

        # Camera follows player
        target_cam = self._px - self._canvas_w * 0.3
        self._cam_x += (target_cam - self._cam_x) * 0.1

        # Generate more world ahead
        while self._furthest_x < self._cam_x + self._canvas_w + 500:
            self._generate_chunk()

        # Clean up platforms far behind
        self._platforms = [
            p for p in self._platforms
            if p["x"] + p["w"] > self._cam_x - 200
        ]

        # Death: fell off screen
        if self._py > self._canvas_h + 100:
            self._game_over = True
            if self._score > self._high_score:
                self._high_score = self._score

    # ── Rendering ─────────────────────────────────────────────────────

    def _render(self):
        c = self._canvas
        c.delete("all")
        w = self._canvas_w
        h = self._canvas_h

        # Background
        c.create_rectangle(0, 0, w, h, fill=self._bg_color, outline="")

        cam = self._cam_x

        # Stars (parallax at 0.1x)
        for sx, sy, size in _make_stars(cam, w, h, self._seed):
            rx = sx - cam * 0.1
            if -5 < rx < w + 5:
                if size <= 1:
                    c.create_oval(rx, sy, rx + 2, sy + 2, fill=STAR_COLOR, outline="")
                else:
                    c.create_oval(rx - 1, sy - 1, rx + size, sy + size,
                                  fill=STAR_COLOR, outline="")

        # Clouds (parallax at 0.3x)
        for cx, cy, cw, ch in _make_clouds(cam, w, h, self._seed):
            rx = cx - cam * 0.3
            if -cw < rx < w + cw:
                c.create_oval(rx, cy, rx + cw, cy + ch, fill=CLOUD_COLOR, outline="")
                c.create_oval(rx + cw * 0.2, cy - ch * 0.3,
                              rx + cw * 0.8, cy + ch * 0.7,
                              fill=CLOUD_COLOR, outline="")

        # Platforms
        for p in self._platforms:
            px = p["x"] - cam
            if px + p["w"] < -20 or px > w + 20:
                continue
            pal = p.get("palette", self._palette)
            # Body
            c.create_rectangle(
                px, p["y"], px + p["w"], p["y"] + p["h"],
                fill=pal["body"], outline=""
            )
            # Top edge (accent line)
            c.create_rectangle(
                px, p["y"], px + p["w"], p["y"] + 3,
                fill=pal["top"], outline=""
            )
            # Small detail ticks on wider platforms
            if p["w"] > 80:
                for tx in range(int(px) + 15, int(px + p["w"]) - 10, 25):
                    c.create_line(tx, p["y"] + 6, tx, p["y"] + p["h"] - 3,
                                  fill=pal["accent"], width=1)

        # Player
        ppx = self._px - cam
        ppy = self._py

        if not self._game_over:
            # Body
            c.create_rectangle(
                ppx + 2, ppy + 4, ppx + PLAYER_W - 2, ppy + PLAYER_H,
                fill=PLAYER_COLOR, outline=""
            )
            # Head
            c.create_oval(
                ppx + 4, ppy, ppx + PLAYER_W - 4, ppy + 14,
                fill=PLAYER_COLOR, outline=""
            )
            # Eye
            eye_x = ppx + 15 if self._facing_right else ppx + 7
            c.create_oval(eye_x, ppy + 4, eye_x + 4, ppy + 8,
                          fill=PLAYER_EYE, outline="")
            # Legs (simple animation based on position)
            leg_phase = math.sin(self._px * 0.15) * 3 if abs(self._vx) > 0 else 0
            c.create_line(ppx + 7, ppy + PLAYER_H, ppx + 5 + leg_phase,
                          ppy + PLAYER_H + 6, fill=PLAYER_COLOR, width=3)
            c.create_line(ppx + PLAYER_W - 7, ppy + PLAYER_H,
                          ppx + PLAYER_W - 5 - leg_phase,
                          ppy + PLAYER_H + 6, fill=PLAYER_COLOR, width=3)

        # HUD
        c.create_text(
            20, 20, text=f"Score {self._score}", anchor="nw",
            fill=SCORE_COLOR, font=("monospace", 16, "bold")
        )
        if self._high_score > 0:
            c.create_text(
                20, 45, text=f"Best {self._high_score}", anchor="nw",
                fill="#6c7086", font=("monospace", 11)
            )

        # Game over screen
        if self._game_over:
            # Dim overlay
            c.create_rectangle(0, 0, w, h, fill="#11111b", stipple="gray50", outline="")
            c.create_text(
                w // 2, h // 2 - 30, text="Game Over",
                fill=GAMEOVER_COLOR, font=("monospace", 36, "bold")
            )
            c.create_text(
                w // 2, h // 2 + 20,
                text=f"Score {self._score}",
                fill=SCORE_COLOR, font=("monospace", 20)
            )
            c.create_text(
                w // 2, h // 2 + 60,
                text="Press Space to try again",
                fill="#6c7086", font=("monospace", 14)
            )


def launch_game(interpreter: Interpreter | None = None, root=None):
    """Create and run the jump'n'run game."""
    if os.environ.get("EPP_HEADLESS"):
        from .errors import EppRuntimeError
        raise EppRuntimeError("games are disabled in headless mode", 0)

    game = JumpAndRunGame(root=root, interpreter=interpreter)
    game.start()
