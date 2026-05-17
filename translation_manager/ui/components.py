"""
Shared UI primitives — flat button, pill, gradient cover, hover-reactive card.
Designed to match a professional launcher aesthetic (Ubisoft / Rockstar style).
"""

import tkinter as tk

import customtkinter as ctk
from .. import theme as t


def _hex_to_rgb(hx: str) -> tuple[int, int, int]:
    hx = hx.lstrip("#")
    return tuple(int(hx[i:i+2], 16) for i in (0, 2, 4))


def _blend(a: str, b: str, ratio: float) -> str:
    r1, g1, b1 = _hex_to_rgb(a)
    r2, g2, b2 = _hex_to_rgb(b)
    r = int(r1 + (r2 - r1) * ratio)
    g = int(g1 + (g2 - g1) * ratio)
    bl = int(b1 + (b2 - b1) * ratio)
    return f"#{r:02x}{g:02x}{bl:02x}"


# ─────────────────────────────────────────────────────────────
# Flat button
# ─────────────────────────────────────────────────────────────
class FlatButton(ctk.CTkButton):
    """Solid-fill button with consistent typography and hover."""

    def __init__(
        self,
        master,
        text: str,
        color: str = t.BRAND_PRIMARY,
        hover: str = t.BRAND_HOVER,
        text_color: str = t.TEXT_ON_BRAND,
        width: int = 120,
        height: int = 36,
        command=None,
        font=None,
        **kwargs,
    ):
        super().__init__(
            master,
            text=text,
            fg_color=color,
            hover_color=hover,
            text_color=text_color,
            font=font if font is not None else t.FONT_BUTTON,
            width=width,
            height=height,
            corner_radius=6,
            command=command,
            border_spacing=4,
            **kwargs,
        )


# ─────────────────────────────────────────────────────────────
# Ghost (outline) button
# ─────────────────────────────────────────────────────────────
class GhostButton(ctk.CTkButton):
    def __init__(
        self,
        master,
        text: str,
        accent: str = t.BRAND_LIGHT,
        width: int = 120,
        height: int = 36,
        command=None,
        **kwargs,
    ):
        super().__init__(
            master,
            text=text,
            fg_color="transparent",
            hover_color=t.SURFACE_4,
            text_color=accent,
            border_color=accent,
            border_width=1,
            font=t.FONT_BUTTON,
            width=width,
            height=height,
            corner_radius=6,
            command=command,
            **kwargs,
        )


# ─────────────────────────────────────────────────────────────
# Status pill — small colored chip showing a single state word
# ─────────────────────────────────────────────────────────────
class StatusPill(ctk.CTkLabel):
    def __init__(self, master, text: str = "—", color: str = t.STATE_UNKNOWN, **kwargs):
        super().__init__(
            master,
            text=f"  {text}  ",
            fg_color=color,
            text_color=t.TEXT_ON_BRAND,
            font=t.FONT_STATUS,
            corner_radius=10,
            **kwargs,
        )

    def set_state(self, text: str, color: str) -> None:
        self.configure(text=f"  {text}  ", fg_color=color)


# ─────────────────────────────────────────────────────────────
# Gradient cover — stacked CTkFrames simulate a smooth gradient.
# (CustomTkinter ScrollableFrame doesn't play nicely with tk.Canvas children,
# so we render the gradient as a column of solid-color rows instead.)
# ─────────────────────────────────────────────────────────────
class GradientCover(ctk.CTkFrame):
    """
    Themed cover: stacked CTkFrame bands simulate a vertical gradient
    matching the website's `linear-gradient(135deg, bgBase → ambient)`.
    A captioned title is painted in the theme's primary accent color
    (yellow for cyberpunk, red for tsushima, gold for hogwarts, etc.).
    """

    BANDS = 5   # kept low for perf — visible enough on hero-sized surfaces

    def __init__(
        self,
        master,
        color_top: str,
        color_bottom: str,
        accent: str = "#ffffff",
        width: int = 260,
        height: int = 140,
        caption: str = "",
        caption_size: int = 22,
        corner_radius: int = 18,
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color=color_top,
            width=width,
            height=height,
            corner_radius=corner_radius,
            border_width=1,
            border_color="#1f1f30",   # rgba(255,255,255,0.06) equivalent
            **kwargs,
        )
        self.pack_propagate(False)
        self.grid_propagate(False)

        self.color_top = color_top
        self.color_bottom = color_bottom
        self.accent = accent
        self.caption = caption
        self._caption_size = caption_size
        self._build_bands()

        if caption:
            # Caption painted in the theme's accent color (matches website
            # where the cover title uses tokens.primary, e.g. #fff700)
            self._caption_lbl = ctk.CTkLabel(
                self, text=caption,
                font=(t.FONT_DISPLAY, caption_size, "bold"),
                text_color=accent, fg_color="transparent",
            )
            self._caption_lbl.place(relx=0.5, rely=0.5, anchor="center")

    def _build_bands(self) -> None:
        for i in range(self.BANDS):
            self.grid_rowconfigure(i, weight=1, uniform="band")
        self.grid_columnconfigure(0, weight=1)
        for i in range(self.BANDS):
            color = _blend(self.color_top, self.color_bottom, i / max(self.BANDS - 1, 1))
            band = ctk.CTkFrame(self, fg_color=color, corner_radius=0)
            band.grid(row=i, column=0, sticky="nsew")

    def set_caption(self, text: str) -> None:
        if hasattr(self, "_caption_lbl"):
            self._caption_lbl.configure(text=text)


# ─────────────────────────────────────────────────────────────
# CoverImage — real JPG cover loaded from the website's `public/covers/`
# folder. If the image is missing or Pillow isn't installed, falls back
# to a cheap solid-color tile (just the theme's bgBase) instead of the
# heavy 14-band gradient.
#
# This is FAST: a single CTkLabel with a pre-resized CTkImage, vs the
# old GradientCover which spawned ~14 child CTkFrames per card.
# ─────────────────────────────────────────────────────────────
def bind_recursive(widget, sequence: str, callback) -> None:
    """
    Recursively bind an event on a widget AND every descendant.

    Why: CustomTkinter labels / frames hold the visible content in inner
    tk widgets (`_canvas`, `_label`). A `widget.bind(...)` only fires when
    the click hits the *outer* container — clicks inside the inner widget
    are swallowed. This walker attaches the handler everywhere so any
    visible pixel of the card is clickable.
    """
    try:
        widget.bind(sequence, callback, add="+")
    except Exception:
        pass
    # Bind on the underlying tk components when available
    for attr in ("_canvas", "_label", "_text_label"):
        inner = getattr(widget, attr, None)
        if inner is not None:
            try:
                inner.bind(sequence, callback, add="+")
            except Exception:
                pass
    try:
        for child in widget.winfo_children():
            bind_recursive(child, sequence, callback)
    except Exception:
        pass


class CoverImage(ctk.CTkFrame):
    """
    Cover holder — CTkFrame with rounded corners + solid theme background;
    image overlaid via tk.Label + ImageTk.PhotoImage (which is what
    keeps scroll silky and avoids CTkImage's paint-trail bug).
    """

    def __init__(
        self,
        master,
        game_id: str,
        theme_key: str,
        width: int = 240,
        height: int = 260,
        corner_radius: int = 12,
        fallback_text: str = "",
        fallback_size: int = 22,
        on_click=None,
        on_context=None,
        **kwargs,
    ):
        top_color = t.CARD_GRADIENTS.get(theme_key, t.CARD_GRADIENTS["default"])[0]
        accent_color = t.CARD_ACCENTS.get(theme_key, t.CARD_ACCENTS["default"])
        super().__init__(
            master,
            fg_color=top_color,
            width=width, height=height,
            corner_radius=corner_radius,
            border_width=0,
            **kwargs,
        )
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.game_id = game_id
        self.theme_key = theme_key
        self._cover_w = width
        self._cover_h = height
        self._on_click   = on_click
        self._on_context = on_context

        # Fallback monogram shown until image arrives (or permanently if
        # the cover is missing).
        self._fallback: tk.Label | None = None
        if fallback_text:
            self._fallback = tk.Label(
                self, text=fallback_text,
                bg=top_color, fg=accent_color,
                font=(t.FONT_DISPLAY, fallback_size, "bold"),
                bd=0, highlightthickness=0,
            )
            self._fallback.place(relx=0.5, rely=0.5, anchor="center")

        # Worker-thread → UI handoff via a one-shot queue. `after()`
        # called from a worker thread is unreliable on Windows; polling
        # from the UI thread is the safe pattern.
        import queue as _queue
        self._img_queue: _queue.Queue = _queue.Queue(maxsize=1)

        self._image_label: tk.Label | None = None
        self._apply_handlers()
        self._try_load_image_async()

    def _apply_handlers(self) -> None:
        """Bind click + right-click on the cover and every descendant."""
        if self._on_click is not None:
            bind_recursive(self, "<Button-1>", self._on_click)
        if self._on_context is not None:
            bind_recursive(self, "<Button-3>", self._on_context)

    def _try_load_image_async(self) -> None:
        from .. import assets
        # Cache hit → set synchronously, no need to poll
        key = (self.game_id, self._cover_w, self._cover_h)
        cached = assets._image_cache.get(key)
        if cached is not None:
            self._set_image(cached)
            return

        # Cache miss — load on a worker thread, deliver via queue + poll
        def on_ready(img):
            if img is not None:
                try:
                    self._img_queue.put_nowait(img)
                except Exception:
                    pass

        assets.load_cover_async(
            self.game_id, self._cover_w, self._cover_h, on_ready,
        )
        # Start polling from the UI thread
        self.after(60, self._poll_image)

    def _poll_image(self) -> None:
        try:
            img = self._img_queue.get_nowait()
        except Exception:
            img = None
        if img is not None:
            self._set_image(img)
            return
        # Image not ready yet — re-schedule, but bail if widget is destroyed
        try:
            if self.winfo_exists():
                self.after(60, self._poll_image)
        except Exception:
            pass

    def _set_image(self, img) -> None:
        if img is None:
            return
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        # Tear down the fallback label (cover art has arrived)
        if self._fallback is not None:
            try:
                self._fallback.destroy()
            except Exception:
                pass
            self._fallback = None

        # Use a plain tk.Label with ImageTk.PhotoImage. This avoids the
        # vertical paint-trail bug that CTkLabel+CTkImage exhibits inside
        # CTkScrollableFrame on Windows during wheel scroll.
        try:
            from PIL import ImageTk
            photo = ImageTk.PhotoImage(img)
        except Exception:
            return
        bg = t.CARD_GRADIENTS.get(self.theme_key, t.CARD_GRADIENTS["default"])[0]
        self._image_label = tk.Label(
            self, image=photo, bg=bg, bd=0, highlightthickness=0,
            cursor="hand2",
        )
        # Keep a strong reference so the GC doesn't collect the PhotoImage
        # (tk.Label only holds a weak reference to its image argument).
        self._image_label._photo_ref = photo  # type: ignore[attr-defined]
        self._image_label.place(relx=0.5, rely=0.5, anchor="center")
        # CTkFrame's internal background canvas can paint over later-created
        # siblings — lift the image label so it stays visible.
        try:
            self._image_label.lift()
        except Exception:
            pass
        # IMPORTANT: do NOT call .lower() here — customtkinter renders the
        # rounded background on an internal canvas, and lowering the image
        # below that canvas makes it invisible.
        # Instead, raise any sibling overlay widgets (version chips, etc.)
        # that callers added BEFORE the async image arrived, so they stay
        # on top of the new image_label.
        for sibling in self.winfo_children():
            if sibling is self._image_label:
                continue
            try:
                sibling.lift()
            except Exception:
                pass
        # Re-apply click handlers so the new image label is also clickable
        self._apply_handlers()


# ─────────────────────────────────────────────────────────────
# Version chip — small rounded pill in theme.primary color
# (matches the version chip overlaid on each website cover)
# ─────────────────────────────────────────────────────────────
class VersionChip(ctk.CTkLabel):
    def __init__(self, master, text: str, accent: str = t.ACCENT_YELLOW, **kwargs):
        super().__init__(
            master,
            text=f"  {text}  ",
            text_color=accent,
            fg_color=t.SURFACE_0,
            font=t.FONT_CHIP,
            corner_radius=10,
            **kwargs,
        )


# ─────────────────────────────────────────────────────────────
# Section header (right-aligned for Hebrew RTL feel)
# ─────────────────────────────────────────────────────────────
class SectionHeader(ctk.CTkFrame):
    def __init__(self, master, text: str, accent: str = t.BRAND_PRIMARY, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        # Right-aligned title with a colored vertical bar
        ctk.CTkLabel(
            self, text=text, font=t.FONT_SECTION,
            text_color=t.TEXT_PRIMARY, anchor="e",
        ).pack(side="right", padx=(8, 0))

        bar = ctk.CTkFrame(self, fg_color=accent, width=4, height=22, corner_radius=2)
        bar.pack(side="right")
        bar.pack_propagate(False)


# ─────────────────────────────────────────────────────────────
# Progress bar — thin animated fill
# ─────────────────────────────────────────────────────────────
class MiniProgress(ctk.CTkFrame):
    def __init__(self, master, value: int = 0, color: str = t.BRAND_PRIMARY,
                 height: int = 6, **kwargs):
        super().__init__(
            master,
            fg_color=t.SURFACE_4,
            height=height,
            corner_radius=height // 2,
            **kwargs,
        )
        self.pack_propagate(False)
        self._fill = ctk.CTkFrame(
            self, fg_color=color, corner_radius=height // 2,
        )
        self._fill.place(relx=0, rely=0, relheight=1, relwidth=max(0, min(value, 100)) / 100)

    def set_value(self, value: int, color: str | None = None) -> None:
        self._fill.place_configure(relwidth=max(0, min(value, 100)) / 100)
        if color:
            self._fill.configure(fg_color=color)
