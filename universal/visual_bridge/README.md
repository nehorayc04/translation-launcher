# Visual LQA capture backbone (`universal/visual_bridge/`)

A read-only screen-capture logger that prepares gameplay frames for a
Vision-Language Model (VLM) to inspect for on-screen UI text overflow,
reversed RTL letters, and context mismatches. It is **game-agnostic** —
one config dict drives both **Cyberpunk 2077** and **Marvel's Spider-Man 2**.

## What it does

A safe background loop polls the **focused** window title every few seconds:

- **Target game focused** → grab the primary screen, downscale (longest edge
  ≤ `--max-dim`, default 1280 px), encode to a JPEG buffer, write it under
  `_archive/visual_logs/frames/<game_id>/`, and append a record
  `{timestamp, game_id, frame_path, window_title, ...}` to
  `_archive/visual_logs/runtime_log.jsonl`.
- **No target focused** → **idle state**: the loop only sleeps and never grabs
  the screen, so 100 % of GPU/CPU stays with the game and the system.

## Dependencies

Core path needs **only Pillow** (already a project dependency) + the native
Win32 API via `ctypes` — no `pywin32` / `pygetwindow` / `mss` install needed,
which is what keeps it clean on **Python 3.13**. `psutil`, *if present*, is
used only to annotate the focused process name; its absence changes nothing.

Optional extras: `pip install psutil` (process-name enrichment).

## Usage

```bash
# from the project root
python universal/visual_bridge/game_visual_logger.py selftest   # deps/IO smoke test
python universal/visual_bridge/game_visual_logger.py probe      # show focused window + match
python universal/visual_bridge/game_visual_logger.py --once     # capture one frame now
python universal/visual_bridge/game_visual_logger.py run        # the background loop
```

Useful flags on `run`/`--once`:

| Flag | Default | Meaning |
|---|---|---|
| `--game <id>` | (all) | restrict to one `game_id` (`cyberpunk2077` / `spiderman2`) |
| `--no-capture` | off | log focus decisions but never grab the screen |
| `--poll N` | 4.0 | focused-window poll seconds |
| `--interval N` | 5.0 | minimum seconds between captured frames |
| `--idle-poll N` | 4.0 | poll cadence while idle |
| `--max-dim N` | 1280 | longest JPEG edge (px) |
| `--quality N` | 70 | JPEG quality (1–95) |

## Adding a game

Add an entry to `GAME_WINDOW_TITLES` in `game_visual_logger.py`:

```python
GAME_WINDOW_TITLES = {
    "cyberpunk2077": ["Cyberpunk 2077 (C) 2020 by CD Projekt RED", "Cyberpunk 2077"],
    "spiderman2":    ["Marvel's Spider-Man 2", "Spider-Man 2"],
    # "newgame":     ["Exact Window Title", "Short Title"],
}
```

Matching is case-insensitive substring; list the most-specific fragment first.

## Safety

Writes are confined to `_archive/visual_logs/` by `_safe_write_check()`, which
hard-stops (exit 99) on any target outside that directory. The logger never
opens, reads, or writes a game file or a translation data array.

## Multi-monitor

The grab is scoped to the game window's rectangle over the whole virtual
desktop (via `GetWindowRect` + `ImageGrab.grab(bbox=…, all_screens=True)`), so
a game on a **secondary monitor** is captured correctly — not whatever is on
the primary display. If the window rect can't be read, it falls back to
grabbing the entire virtual desktop.

## Known limitation

GDI screen capture (what Pillow's `ImageGrab` uses) **cannot** read an
*exclusive* fullscreen DXGI surface and returns an all-black frame. The logger
**detects all-black frames** and logs them as `capture_failed` instead of
persisting a useless black JPEG. Run the game in **borderless windowed** mode
for Visual LQA capture. Any other grab/encode/write failure is also caught and
logged as `capture_failed`; the loop continues.

## Next step

Once the textual audit finishes, wire `runtime_log.jsonl` → the local
inference API: read each `frame_path`, send the JPEG to the VLM, and record
findings (text overflow / reversed RTL / context mismatch) per frame.
