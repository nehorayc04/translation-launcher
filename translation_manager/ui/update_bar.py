"""
Bottom update bar — fixed-height strip with rolling news ticker + status text.
"""

import customtkinter as ctk

from .. import theme as t
from ..config import Strings as S


class UpdateBar(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=t.SURFACE_1,
            height=44,
            corner_radius=20,
            border_width=0,
            **kwargs,
        )
        self.pack_propagate(False)

        # Right-side: title with "live" indicator
        right = ctk.CTkFrame(self, fg_color=t.SURFACE_1)
        right.pack(side="right", padx=14, fill="y")

        ctk.CTkLabel(
            right, text=S.UPDATE_TITLE,
            font=t.FONT_BODY_BOLD, text_color=t.TEXT_PRIMARY,
        ).pack(side="right", pady=12)

        # Pulsing green dot ("live updates")
        self._dot = ctk.CTkLabel(
            right, text="●", font=("Segoe UI", 14, "bold"),
            text_color=t.STATE_ACTIVE,
        )
        self._dot.pack(side="right", padx=(0, 8), pady=12)

        # Left-side: version label
        ctk.CTkLabel(
            self, text=S.UPDATE_LATEST,
            font=t.FONT_FOOTER, text_color=t.TEXT_MUTED,
        ).pack(side="left", padx=14, pady=12)

        # Center: news ticker (cycles through the items)
        self._ticker_text = ctk.StringVar(value=S.UPDATE_NEWS_1)
        ctk.CTkLabel(
            self, textvariable=self._ticker_text,
            font=t.FONT_TICKER, text_color=t.ACCENT_CYAN, anchor="center",
        ).pack(side="left", padx=20, fill="both", expand=True, pady=12)

        self._news = [S.UPDATE_NEWS_1, S.UPDATE_NEWS_2, S.UPDATE_NEWS_3]
        self._idx = 0
        self.after(4000, self._tick)
        self.after(1200, self._pulse)

    def _tick(self) -> None:
        """Rotate ticker text every few seconds. No-op once destroyed."""
        if not self.winfo_exists():
            return
        self._idx = (self._idx + 1) % len(self._news)
        self._ticker_text.set(self._news[self._idx])
        self.after(4500, self._tick)

    def _pulse(self) -> None:
        """Alternate the live-dot color for a subtle pulse effect."""
        if not self.winfo_exists():
            return
        try:
            current = self._dot.cget("text_color")
        except Exception:
            return
        next_color = t.STATE_DISABLED if current == t.STATE_ACTIVE else t.STATE_ACTIVE
        self._dot.configure(text_color=next_color)
        self.after(900, self._pulse)
