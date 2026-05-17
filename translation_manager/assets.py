"""
Cover-image loader — maps internal game IDs to the JPGs that ship inside
`<website>/public/covers/<id>.jpg`, resizes them with Pillow, and caches the
CTkImage so each cover is loaded at most once per app run.
"""

import threading
from pathlib import Path
from typing import Callable

from .config import WEBSITE_PROJECT_DIR


def _cover_fit(img, target_w: int, target_h: int):
    """
    CSS `object-fit: cover` — scale so the image FILLS the target box
    then crop the overflow. Preserves aspect ratio (no stretching).
    """
    from PIL import Image
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    tgt_ratio = target_w / target_h
    if src_ratio > tgt_ratio:
        # Source wider than target → scale by height, crop sides
        new_h = target_h
        new_w = int(round(new_h * src_ratio))
    else:
        # Source taller than target → scale by width, crop top/bottom
        new_w = target_w
        new_h = int(round(new_w / src_ratio))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top  = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))

# ── Locate the covers folder (public/ in dev, dist/ in prod build) ──
_COVER_DIRS = [
    WEBSITE_PROJECT_DIR / "public" / "covers",
    WEBSITE_PROJECT_DIR / "dist"   / "covers",
]


def find_cover(game_id: str) -> Path | None:
    """Return the on-disk cover path for `game_id`, or None if missing."""
    for d in _COVER_DIRS:
        p = d / f"{game_id}.jpg"
        if p.exists():
            return p
    return None


# ─────────────────────────────────────────────────────────────
# Image cache — keyed by (game_id, width, height). CTkImage is
# heavy enough that we share instances across cards.
# ─────────────────────────────────────────────────────────────
_image_cache: dict[tuple[str, int, int], object] = {}
_cache_lock = threading.Lock()


def load_cover(game_id: str, width: int, height: int):
    """
    Load a cover image (PIL Image, cache-aware). Returns None on missing /
    load failure so the caller can fall back to a placeholder.

    PIL Image is the storage format — callers convert to ImageTk.PhotoImage
    (or CTkImage) at the widget-creation site. ImageTk.PhotoImage on a plain
    `tk.Label` avoids the scroll paint-trail bug that CTkImage exhibits
    inside CTkScrollableFrame.
    """
    key = (game_id, width, height)
    with _cache_lock:
        if key in _image_cache:
            return _image_cache[key]

    path = find_cover(game_id)
    if path is None:
        return None

    try:
        from PIL import Image
        img = Image.open(path).convert("RGB")
        img = _cover_fit(img, width, height)
    except Exception:
        return None

    with _cache_lock:
        _image_cache[key] = img
    return img


def load_cover_async(game_id: str, width: int, height: int,
                     on_ready: Callable[[object], None]) -> None:
    """Load a cover on a background thread; call `on_ready(image_or_None)`
    when done. The caller is responsible for marshalling back to the UI
    thread (e.g. via widget.after(0, ...))."""
    def worker():
        img = load_cover(game_id, width, height)
        on_ready(img)
    threading.Thread(target=worker, daemon=True).start()
