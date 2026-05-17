"""
Left-side navigation panel — logo, nav items, bottom user/footer area.
Active nav item is highlighted with a colored vertical bar and brighter text.
"""

from typing import Callable

import customtkinter as ctk

from .. import theme as t
from ..config import Strings as S


class NavItem(ctk.CTkFrame):
    """A clickable nav row with an icon glyph + label + active-state indicator."""

    def __init__(self, master, label: str, glyph: str, accent: str,
                 on_click: Callable[[str], None], key: str, **kwargs):
        super().__init__(master, fg_color=t.SURFACE_1, height=46,
                         corner_radius=0, **kwargs)
        self.pack_propagate(False)
        self.key = key
        self.accent = accent
        self.on_click = on_click
        self._active = False

        # Right-side accent indicator bar (highlighted when active)
        self._bar = ctk.CTkFrame(self, fg_color=t.SURFACE_1, width=3, corner_radius=0)
        self._bar.pack(side="right", fill="y")

        # Label + icon container — Hebrew label first (right), glyph after
        self._label = ctk.CTkLabel(
            self, text=label, font=t.FONT_NAV,
            text_color=t.TEXT_SECONDARY, anchor="e",
        )
        self._label.pack(side="right", padx=(0, 16), fill="x", expand=True)

        self._glyph = ctk.CTkLabel(
            self, text=glyph, font=("Segoe UI Emoji", 18),
            text_color=t.TEXT_SECONDARY, width=42,
        )
        self._glyph.pack(side="right")

        # Make the whole row clickable
        for w in (self, self._label, self._glyph):
            w.bind("<Button-1>", lambda _e: self.on_click(self.key))
            w.bind("<Enter>", lambda _e: self._hover(True))
            w.bind("<Leave>", lambda _e: self._hover(False))

    def _hover(self, on: bool) -> None:
        if self._active:
            return
        color = t.SURFACE_3 if on else t.SURFACE_1
        self.configure(fg_color=color)
        self._label.configure(fg_color=color)
        self._glyph.configure(fg_color=color)

    def set_active(self, active: bool) -> None:
        self._active = active
        if active:
            self.configure(fg_color=t.SURFACE_3)
            self._label.configure(fg_color=t.SURFACE_3,
                                  text_color=t.TEXT_PRIMARY,
                                  font=t.FONT_NAV_ACTIVE)
            self._glyph.configure(fg_color=t.SURFACE_3, text_color=self.accent)
            self._bar.configure(fg_color=self.accent)
        else:
            self.configure(fg_color=t.SURFACE_1)
            self._label.configure(fg_color=t.SURFACE_1,
                                  text_color=t.TEXT_SECONDARY,
                                  font=t.FONT_NAV)
            self._glyph.configure(fg_color=t.SURFACE_1, text_color=t.TEXT_SECONDARY)
            self._bar.configure(fg_color=t.SURFACE_1)


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_nav: Callable[[str], None], **kwargs):
        super().__init__(
            master, fg_color=t.SURFACE_1, width=230,
            corner_radius=20, **kwargs,
        )
        self.pack_propagate(False)
        self.on_nav = on_nav

        self._build_brand()
        self._build_nav()
        self._build_footer()

    def _build_brand(self) -> None:
        """
        Brand block — mirrors the website navbar's RTL "ת" mark + Hebrew title.
        The "ת" sits in a yellow rounded square; the title sits next to it in
        Orbitron/display font with cyan kicker underneath.
        """
        wrapper = ctk.CTkFrame(self, fg_color=t.SURFACE_1, height=80)
        wrapper.pack(fill="x", padx=0, pady=(0, 4))
        wrapper.pack_propagate(False)

        # "ת" mark (Hebrew Tav) on a yellow rounded square — matches the
        # website's navbar logo treatment.
        mark = ctk.CTkFrame(
            wrapper, width=34, height=34,
            fg_color=t.ACCENT_YELLOW, corner_radius=8,
        )
        mark.place(relx=1.0, x=-14, rely=0.42, anchor="ne")
        mark.pack_propagate(False)
        ctk.CTkLabel(
            mark, text="ת", font=(t.FONT_HEBREW, 20, "bold"),
            text_color=t.TEXT_ON_BRAND,
        ).place(relx=0.5, rely=0.5, anchor="center")

        # Brand title — Orbitron display, white
        ctk.CTkLabel(
            wrapper, text="פרויקט התרגום",
            font=(t.FONT_HEBREW, 14, "bold"),
            text_color=t.TEXT_PRIMARY, anchor="e",
        ).place(relx=1.0, x=-56, rely=0.32, anchor="ne")

        # Kicker — yellow, wide-spaced display caps
        ctk.CTkLabel(
            wrapper, text="H E B R E W   A I",
            font=(t.FONT_DISPLAY, 8, "bold"),
            text_color=t.ACCENT_CYAN, anchor="e",
        ).place(relx=1.0, x=-56, rely=0.62, anchor="ne")

        # Thin yellow-tinted divider (≈ #fff70022 over dark)
        ctk.CTkFrame(self, fg_color=t.BORDER_ACCENT, height=1).pack(
            fill="x", padx=14, pady=(0, 6))

    def _build_nav(self) -> None:
        items = [
            ("home",     S.NAV_HOME,     "🏠", t.ACCENT_HOME),
            ("library",  S.NAV_LIBRARY,  "🎮", t.ACCENT_LIB),
            ("settings", S.NAV_SETTINGS, "⚙️", t.ACCENT_SETTINGS),
        ]
        self._items: dict[str, NavItem] = {}
        for key, label, glyph, accent in items:
            ni = NavItem(self, label, glyph, accent, self._select, key)
            ni.pack(fill="x", pady=2)
            self._items[key] = ni

    def _build_footer(self) -> None:
        # User card at the bottom — placeholder avatar circle + name
        spacer = ctk.CTkFrame(self, fg_color=t.SURFACE_1)
        spacer.pack(fill="both", expand=True)

        # Theme toggle (matches website ThemeToggle: Game / Dark)
        self._build_theme_toggle()

        ctk.CTkFrame(self, fg_color=t.BORDER_DIM, height=1).pack(
            fill="x", padx=14, pady=(0, 0))

    def _build_theme_toggle(self) -> None:
        """Two-segment pill: 'משחק' / 'כהה' — switches whole-app chrome mode."""
        wrap = ctk.CTkFrame(self, fg_color=t.SURFACE_1)
        wrap.pack(fill="x", padx=14, pady=(6, 10))

        ctk.CTkLabel(
            wrap, text="מצב תצוגה",
            font=t.FONT_FOOTER, text_color=t.TEXT_MUTED, anchor="e",
        ).pack(fill="x", pady=(0, 4))

        # The pill itself — outer dark capsule with two inner buttons
        pill = ctk.CTkFrame(
            wrap, fg_color=t.SURFACE_3, corner_radius=14,
            height=32, border_width=1, border_color=t.BORDER_DIM,
        )
        pill.pack(fill="x")
        pill.pack_propagate(False)

        is_game = (t.MODE == "game")

        # Order is reversed because we pack RIGHT first → that becomes the
        # right-most segment, which feels right for RTL.
        self._btn_game = ctk.CTkButton(
            pill, text="משחק", width=80, height=26,
            fg_color=t.ACCENT_YELLOW if is_game else "transparent",
            hover_color=t.BRAND_HOVER if is_game else t.SURFACE_4,
            text_color=t.TEXT_ON_BRAND if is_game else t.TEXT_SECONDARY,
            font=t.FONT_BUTTON, corner_radius=12,
            command=lambda: self._set_mode("game"),
        )
        self._btn_game.pack(side="right", padx=3, pady=3)

        self._btn_clean = ctk.CTkButton(
            pill, text="כהה", width=80, height=26,
            fg_color="transparent" if is_game else t.ACCENT_YELLOW,
            hover_color=t.SURFACE_4 if is_game else t.BRAND_HOVER,
            text_color=t.TEXT_SECONDARY if is_game else t.TEXT_ON_BRAND,
            font=t.FONT_BUTTON, corner_radius=12,
            command=lambda: self._set_mode("clean"),
        )
        self._btn_clean.pack(side="right", padx=(0, 3), pady=3)

    def _set_mode(self, mode: str) -> None:
        if mode == t.MODE:
            return
        t.apply_mode(mode)
        # Ask the top-level window to rebuild everything
        try:
            self.winfo_toplevel().rebuild_ui()
        except AttributeError:
            pass

        card = ctk.CTkFrame(self, fg_color=t.SURFACE_1, height=64)
        card.pack(fill="x", pady=(8, 12), padx=12)
        card.pack_propagate(False)

        # avatar — round yellow badge with cyberpunk-styled initial
        avatar = ctk.CTkFrame(
            card, width=40, height=40,
            fg_color=t.ACCENT_YELLOW, corner_radius=20,
        )
        avatar.pack(side="right")
        avatar.pack_propagate(False)
        ctk.CTkLabel(
            avatar, text="N", font=(t.FONT_DISPLAY, 16, "bold"),
            text_color=t.TEXT_ON_BRAND,
        ).place(relx=0.5, rely=0.5, anchor="center")

        labels = ctk.CTkFrame(card, fg_color=t.SURFACE_1)
        labels.pack(side="right", padx=(0, 10), fill="both", expand=True)

        ctk.CTkLabel(
            labels, text="Nehoray", font=t.FONT_BODY_BOLD,
            text_color=t.TEXT_PRIMARY, anchor="e",
        ).pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(
            labels, text="Mod Manager", font=t.FONT_FOOTER,
            text_color=t.TEXT_MUTED, anchor="e",
        ).pack(fill="x")

    def _select(self, key: str) -> None:
        """User clicked a nav item — update visual + notify the app."""
        self._update_visual(key)
        self.on_nav(key)

    def _update_visual(self, key: str) -> None:
        for k, item in self._items.items():
            item.set_active(k == key)

    def set_active(self, key: str) -> None:
        """Externally sync the highlighted item without firing the callback."""
        self._update_visual(key)
