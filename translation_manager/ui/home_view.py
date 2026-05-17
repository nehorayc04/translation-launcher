"""
Home view — hero card (website project) + featured-translations grid +
quick-link tiles. Mirrors the Ubisoft Connect "Home" feel.
"""

import customtkinter as ctk

from .. import theme as t
from .. import website
from ..config import Strings as S
from .components import (CoverImage, FlatButton, GhostButton, GradientCover,
                         SectionHeader, VersionChip)


class HomeView(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=t.SURFACE_2,
            scrollbar_fg_color=t.SURFACE_2,
            scrollbar_button_color=t.SURFACE_4,
            scrollbar_button_hover_color=t.BRAND_PRIMARY,
            **kwargs,
        )

        self._build_all()

    def _build_all(self) -> None:
        """Construct every section in order. Called by __init__ and by the
        refresh button to recreate the view after a full teardown."""
        self._build_page_title()
        self._build_hero()
        self._build_featured()
        self._build_quick_links()

    def _refresh(self) -> None:
        """Tear down every child widget and rebuild from scratch — picks up
        catalog edits and live-stat changes without restarting the app."""
        for child in self.winfo_children():
            child.destroy()
        self._build_all()

    # ─────────────────────────────────────────────────────────
    def _build_page_title(self) -> None:
        # Top row: refresh button on the LEFT (absolute, regardless of RTL),
        # wide-spaced kicker on the right. Same row so visual weight balances.
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", padx=28, pady=(20, 0))

        ctk.CTkButton(
            top_row, text="↻ רענון",
            width=84, height=28,
            font=(t.FONT_HEBREW, 12, "bold"),
            fg_color=t.SURFACE_4,
            hover_color=t.ACCENT_CYAN,
            text_color=t.TEXT_PRIMARY,
            corner_radius=8,
            command=self._refresh,
        ).pack(side="left", anchor="w")

        # Wide-spaced kicker line (matches Hero.tsx "תרגומי AI · 2026")
        ctk.CTkLabel(
            top_row, text="ד ף   ה ב י ת  ·  H O M E",
            font=t.FONT_KICKER, text_color=t.ACCENT_CYAN, anchor="e",
        ).pack(side="right", fill="x", expand=True)

        # Page title — in cyberpunk yellow (theme.primary) for game mode,
        # off-white for clean mode (theme tokens handle the swap)
        ctk.CTkLabel(
            self, text=S.HOME_TITLE,
            font=t.FONT_PAGE_TITLE, text_color=t.ACCENT_YELLOW, anchor="e",
        ).pack(fill="x", padx=28, pady=(2, 18))

    # ─────────────────────────────────────────────────────────
    # Hero — large banner card mirroring the website hero block.
    # Title in cyberpunk yellow (theme.primary), subtitle in cyan
    # (theme.secondary), description in muted white.
    # ─────────────────────────────────────────────────────────
    def _build_hero(self) -> None:
        # Outer wrap uses the cyberpunk gradient (bgBase → ambient) just like
        # the website's cards do — a deep purple-tinted black, not a bright
        # solid color.
        top, bot = t.CARD_GRADIENTS["cyberpunk"]
        wrap = GradientCover(
            self, top, bot,
            width=900, height=240,
            caption="",   # no caption — we paint text on the right
            corner_radius=22,
        )
        wrap.pack(fill="x", padx=28, pady=(0, 22))

        # Left side: vertical accent stripe in cyberpunk yellow
        stripe = ctk.CTkFrame(
            wrap, fg_color=t.ACCENT_YELLOW, width=4,
            corner_radius=2,
        )
        stripe.place(relx=1.0, rely=0.5, anchor="e",
                     relheight=0.7, x=-22)

        # Text content (right-aligned, RTL feel)
        body = ctk.CTkFrame(wrap, fg_color="transparent")
        body.place(relx=0.97, rely=0.5, anchor="e", relwidth=0.85)

        # Kicker (wide-spaced uppercase — matches Hero.tsx's
        # `tracking-[0.5em] text-[11px]` line)
        ctk.CTkLabel(
            body, text="ת ר ג ו מ י   A I  ·  2 0 2 6",
            font=t.FONT_KICKER,
            text_color=t.ACCENT_CYAN, anchor="e",
        ).pack(fill="x", pady=(0, 6))

        # Primary title — in cyberpunk yellow, large
        ctk.CTkLabel(
            body, text=S.HOME_HERO_TITLE,
            font=(t.FONT_DISPLAY, 32, "bold"),
            text_color=t.ACCENT_YELLOW, anchor="e",
        ).pack(fill="x")

        # Secondary subtitle — in cyan
        ctk.CTkLabel(
            body, text="הדור הבא של הלוקליזציה",
            font=(t.FONT_HEBREW, 18, "bold"),
            text_color=t.ACCENT_CYAN, anchor="e",
        ).pack(fill="x", pady=(2, 8))

        # Description
        ctk.CTkLabel(
            body, text=S.HOME_HERO_DESC,
            font=t.FONT_BODY, text_color=t.TEXT_SECONDARY,
            anchor="e", justify="right", wraplength=620,
        ).pack(fill="x", pady=(0, 14))

        # Action buttons
        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(fill="x")

        FlatButton(
            actions, text=S.HOME_HERO_LOCAL,
            color=t.ACCENT_YELLOW, hover=t.BRAND_HOVER,
            text_color=t.TEXT_ON_BRAND,
            width=160, height=38, command=self._open_local,
        ).pack(side="right", padx=(8, 0))

        GhostButton(
            actions, text=S.HOME_HERO_BUILD,
            accent=t.ACCENT_CYAN, width=160, height=38,
            command=website.open_project_folder,
        ).pack(side="right", padx=(8, 0))

    # ─────────────────────────────────────────────────────────
    # Featured cards — parsed from website's games.ts
    # ─────────────────────────────────────────────────────────
    def _build_featured(self) -> None:
        SectionHeader(self, S.HOME_FEATURED, accent=t.ACCENT_HOME).pack(
            fill="x", padx=28, pady=(4, 12))

        grid = ctk.CTkFrame(self, fg_color=t.SURFACE_2)
        grid.pack(fill="x", padx=22, pady=(0, 18))

        # Build 4 cards per row
        games = website.parse_featured_games(limit=8)
        if not games:
            ctk.CTkLabel(
                grid, text="לא נמצאו תרגומים — בדוק שהפרויקט קיים בנתיב המוגדר.",
                font=t.FONT_BODY, text_color=t.TEXT_MUTED, anchor="e",
            ).pack(fill="x", padx=8, pady=20)
            return

        # 4 columns
        for col in range(4):
            grid.grid_columnconfigure(col, weight=1, uniform="card")

        for idx, g in enumerate(games):
            self._make_game_card(grid, g).grid(
                row=idx // 4, column=idx % 4,
                padx=6, pady=6, sticky="nsew",
            )

    def _make_game_card(self, parent, g: dict) -> ctk.CTkFrame:
        avail_color = {
            "available":   t.STATE_ACTIVE,
            "in-progress": t.ACCENT_YELLOW,
            "coming-soon": t.ACCENT_CYAN,
            "planned":     t.TEXT_MUTED,
        }.get(g.get("availability", "planned"), t.TEXT_MUTED)
        avail_label = {
            "available":   "זמין",
            "in-progress": "בתהליך אריזה",
            "coming-soon": "בקרוב",
            "planned":     "מתוכנן",
        }.get(g.get("availability", "planned"), "—")

        theme_key = g.get("themeKey", "default")
        accent = t.CARD_ACCENTS.get(theme_key, t.CARD_ACCENTS["default"])

        # Card layout (matches website's GameCard): cover image on top,
        # text section beneath — no overlapping text on artwork.
        card = ctk.CTkFrame(
            parent, fg_color=t.SURFACE_3, corner_radius=16,
            border_width=1, border_color=t.BORDER_DIM,
        )

        # ── Top: cover image — 2:3 portrait (matches real cover JPGs) ──
        cover = CoverImage(
            card, game_id=g["id"], theme_key=theme_key,
            width=228, height=342, corner_radius=14,
            fallback_text=g["titleEn"][:2].upper(), fallback_size=32,
        )
        cover.pack(fill="x", padx=6, pady=(6, 0))

        # Version chip floats over the top-right corner of the cover
        VersionChip(cover, text=g.get("version", "—"), accent=accent).place(
            relx=0.96, rely=0.08, anchor="ne")

        # ── Bottom: text section ──
        text = ctk.CTkFrame(card, fg_color=t.SURFACE_3)
        text.pack(fill="both", expand=True, padx=10, pady=(8, 8))

        # Hebrew title (primary)
        ctk.CTkLabel(
            text, text=g["titleHe"],
            font=(t.FONT_HEBREW, 14, "bold"),
            text_color=t.TEXT_PRIMARY, anchor="e",
        ).pack(fill="x")

        # English title (secondary, in theme accent)
        ctk.CTkLabel(
            text, text=g["titleEn"],
            font=(t.FONT_DISPLAY, 10, "bold"),
            text_color=accent, anchor="e",
        ).pack(fill="x", pady=(0, 4))

        # Bottom ribbon row: availability badge + optional progress %
        ribbon = ctk.CTkFrame(text, fg_color=t.SURFACE_3)
        ribbon.pack(fill="x", pady=(2, 0))

        ctk.CTkLabel(
            ribbon, text=f"  {avail_label}  ",
            fg_color=avail_color, text_color=t.TEXT_ON_BRAND,
            font=(t.FONT_HEBREW, 10, "bold"),
            corner_radius=8,
        ).pack(side="left")

        if g.get("progress") is not None:
            ctk.CTkLabel(
                ribbon, text=f"{g['progress']}%",
                font=(t.FONT_DISPLAY, 10, "bold"),
                text_color=accent, anchor="e",
            ).pack(side="right")

        return card

    # ─────────────────────────────────────────────────────────
    # Quick-link tiles
    # ─────────────────────────────────────────────────────────
    def _build_quick_links(self) -> None:
        SectionHeader(self, S.HOME_QUICKLINKS, accent=t.ACCENT_SETTINGS).pack(
            fill="x", padx=28, pady=(8, 12))

        row = ctk.CTkFrame(self, fg_color=t.SURFACE_2)
        row.pack(fill="x", padx=22, pady=(0, 24))

        links = [
            ("🌐", "אתר חי",       "פתח באתר Vercel",  t.BRAND_PRIMARY,
             lambda: website.open_url("https://hebrewgames.vercel.app")),
            ("📁", "תיקיית פרויקט", "פתח ב-Explorer",  t.ACCENT_LIB,
             website.open_project_folder),
            ("⚡", "גרסה מקומית",  "שרת dist באופן מקומי", t.STATE_ACTIVE,
             self._open_local),
            ("📖", "מסמכי פרויקט", "CLAUDE.md + README",  t.STATE_DISABLED,
             website.open_project_folder),
        ]
        for col in range(4):
            row.grid_columnconfigure(col, weight=1, uniform="ql")

        for idx, (glyph, title, sub, color, command) in enumerate(links):
            self._make_quicklink(row, glyph, title, sub, color, command).grid(
                row=0, column=idx, padx=6, pady=4, sticky="nsew",
            )

    def _make_quicklink(self, parent, glyph, title, sub, color, command):
        tile = ctk.CTkFrame(
            parent, fg_color=t.SURFACE_3, corner_radius=10,
            border_width=1, border_color=t.BORDER_DIM,
            height=84,
        )
        tile.pack_propagate(False)

        # Right side: icon
        icon = ctk.CTkLabel(
            tile, text=glyph, font=("Segoe UI Emoji", 26),
            text_color=color, width=58,
        )
        icon.pack(side="right", padx=(0, 8))

        # Left side: labels
        body = ctk.CTkFrame(tile, fg_color=t.SURFACE_3)
        body.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=8)

        ctk.CTkLabel(
            body, text=title, font=t.FONT_BODY_BOLD,
            text_color=t.TEXT_PRIMARY, anchor="e",
        ).pack(fill="x")
        ctk.CTkLabel(
            body, text=sub, font=t.FONT_FOOTER,
            text_color=t.TEXT_MUTED, anchor="e",
        ).pack(fill="x")

        # Make whole tile clickable
        for w in (tile, icon, body, *body.winfo_children()):
            w.bind("<Button-1>", lambda _e: command())
            w.bind("<Enter>", lambda _e, T=tile: T.configure(fg_color=t.SURFACE_4))
            w.bind("<Leave>", lambda _e, T=tile: T.configure(fg_color=t.SURFACE_3))
        return tile

    # ─────────────────────────────────────────────────────────
    def _open_local(self) -> None:
        ok, info = website.serve_dist()
        if ok:
            # Bubble up the status to the main app's update bar if present
            try:
                self.winfo_toplevel().report_status(
                    S.MSG_SERVING.format(port=info.rsplit(":", 1)[-1]))
            except AttributeError:
                pass
        else:
            try:
                self.winfo_toplevel().report_status(S.MSG_NO_DIST, warn=True)
            except AttributeError:
                pass
