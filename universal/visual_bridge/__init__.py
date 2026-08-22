"""
universal.visual_bridge
=======================
Universal Visual LQA capture backbone. Re-exports the public surface of
`game_visual_logger` so callers can do::

    from universal.visual_bridge import capture_frame, run_loop, GAME_WINDOW_TITLES

The package is read-only toward all game/translation data — see the module
docstring in `game_visual_logger.py`.
"""
from __future__ import annotations

from .game_visual_logger import (
    __version__,
    GAME_WINDOW_TITLES,
    FocusInfo,
    FrameResult,
    LoopConfig,
    foreground_focus,
    match_game,
    capture_frame,
    log_event,
    run_loop,
)

__all__ = [
    "__version__",
    "GAME_WINDOW_TITLES",
    "FocusInfo",
    "FrameResult",
    "LoopConfig",
    "foreground_focus",
    "match_game",
    "capture_frame",
    "log_event",
    "run_loop",
]
