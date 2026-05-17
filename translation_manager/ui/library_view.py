"""
Library view — three vertically-stacked sections like the original design:

  1. עם מודים מותקנים      ← active or disabled launcher mods
  2. מותקנים ללא מוד       ← detected on disk but no mod yet
  3. לא מותקנים            ← everything else from the catalog

Card layout matches the website's GameCard (cover + text section). All
overlays (version chip / availability ribbon / progress bar) live BELOW
the cover in the text section instead of placed on top of it — this
avoids the scroll-artifact bug in CustomTkinter where `.place()`-ed
widgets leave ghost copies during wheel scroll.

Clicking a card opens GameDetailModal — the per-game window that mirrors
the website's GameDetailModal.tsx.
"""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import game_detector
from .. import games_catalog
from .. import mod_logic as ml
from .. import paths as user_paths
from .. import theme as t
from ..config import GAMES, Strings as S
from ..games_catalog import CatalogGame
from .components import (CoverImage, FlatButton, SectionHeader, VersionChip,
                         bind_recursive)
from .game_detail_panel import GameDetailPanel


# ─────────────────────────────────────────────────────────────
# Card dimensions — 200×300 cover (2:3 aspect = matches actual JPGs)
# plus an 80px text strip. Total 200×380.
# ─────────────────────────────────────────────────────────────
CARD_W      = 200
COVER_W     = 200
COVER_H     = 300
TEXT_H      = 96
CARD_H      = COVER_H + TEXT_H


# ─────────────────────────────────────────────────────────────
# Availability → (badge label, badge color)
# ─────────────────────────────────────────────────────────────
def _availability_visual(av: str) -> tuple[str, str]:
    return {
        "available":   ("זמין",     t.STATE_ACTIVE),
        "in-progress": ("בתהליך",  t.ACCENT_YELLOW),
        "coming-soon": ("בקרוב",   t.ACCENT_CYAN),
        "planned":     ("מתוכנן",  t.TEXT_MUTED),
    }.get(av, ("—", t.TEXT_MUTED))


# ─────────────────────────────────────────────────────────────
# Mod-status detection for launcher-managed titles
# ─────────────────────────────────────────────────────────────
def _resolve_install(game_id: str,
                     detected: dict[str, Path]) -> tuple[str | None, Path | None, bool]:
    """
    Combine user overrides + detector results + launcher mod manifests.

    Resolution order for install_path:
      1. User-saved path (`paths.get`)  — wins if it exists
      2. Detector result (Steam/Ubisoft/Epic/GOG/Rockstar/deep-scan)
      3. Launcher's `common_paths` static list
    """
    cfg = None
    for g in GAMES.values():
        if g.internal_id == game_id:
            cfg = g
            break

    install_path = user_paths.get(game_id)
    if install_path is None:
        install_path = detected.get(game_id)
    if install_path is None and cfg is not None:
        for raw in cfg.common_paths:
            p = Path(raw)
            if p.exists() and (not cfg.validation_file or cfg.is_valid_dir(p)):
                install_path = p
                break

    has_mod = cfg is not None and bool(cfg.mod_files)
    if cfg is None:
        return None, install_path, False
    if install_path is None:
        return (ml.STATE_NOT_INSTALLED if has_mod else None), None, has_mod

    state = ml.detect_state(cfg, install_path) if has_mod else ml.STATE_UNKNOWN
    return state, install_path, has_mod


# ─────────────────────────────────────────────────────────────
# Game Card — clean layout, NO place() overlays on the cover
# (the scroll-artifact issue was caused by overlays placed inside
# the scrolled cover frame; they're now in the text strip below.)
# ─────────────────────────────────────────────────────────────
class GameCard(ctk.CTkFrame):
    """Card with rounded corners — uses CTkFrame for the corner_radius.
    Safe to use here because we're rendered inside a hand-rolled
    tk.Canvas scroll viewport (not CTkScrollableFrame) so the rounded
    background doesn't leave wheel-scroll paint trails."""

    def __init__(self, master, game: CatalogGame,
                 mod_state: str | None, install_path: Path | None,
                 on_open, on_context=None, **kwargs):
        super().__init__(
            master,
            fg_color=t.SURFACE_3,
            corner_radius=18,
            border_width=0,
            width=CARD_W,
            height=CARD_H,
            **kwargs,
        )
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.game = game
        self.mod_state = mod_state
        self.install_path = install_path
        self.on_open = on_open
        self.on_context = on_context

        self._build()
        bind_recursive(self, "<Button-1>", self._click_handler)
        bind_recursive(self, "<Button-3>", self._context_handler)

    def _build(self) -> None:
        accent = t.CARD_ACCENTS.get(self.game.theme_key, t.CARD_ACCENTS["default"])
        avail_label, avail_color = _availability_visual(self.game.availability)

        # ── Cover (clean — no overlays inside) ──
        # Passing on_click/on_context here ensures the async-loaded image
        # label also routes clicks back to the card.
        cover = CoverImage(
            self,
            game_id=self.game.id,
            theme_key=self.game.theme_key,
            width=COVER_W - 12,
            height=COVER_H - 12,
            corner_radius=0,
            fallback_text=self.game.titleEn[:2].upper(),
            fallback_size=22,
            on_click=self._click_handler,
            on_context=self._context_handler,
        )
        cover.pack(pady=(6, 0), padx=6)

        # ── Text strip with rounded sub-frames ──
        text = ctk.CTkFrame(self, fg_color=t.SURFACE_3, corner_radius=0)
        text.pack(fill="both", expand=True, padx=10, pady=(6, 8))

        # Meta row: version chip (left) + availability/mod badge (right)
        meta = ctk.CTkFrame(text, fg_color=t.SURFACE_3, corner_radius=0)
        meta.pack(fill="x", pady=(0, 2))

        if self.game.version not in ("—", ""):
            VersionChip(meta, text=self.game.version, accent=accent).pack(
                side="left")

        if self.mod_state in (ml.STATE_ACTIVE, ml.STATE_DISABLED):
            mod_label, mod_color = self._mod_visual()
            ctk.CTkLabel(
                meta, text=f"● {mod_label}",
                fg_color="transparent", text_color=mod_color,
                font=(t.FONT_HEBREW, 10, "bold"),
            ).pack(side="right")
        else:
            ctk.CTkLabel(
                meta, text=f"  {avail_label}  ",
                fg_color=avail_color, text_color=t.TEXT_ON_BRAND,
                font=(t.FONT_HEBREW, 9, "bold"),
                corner_radius=8,
            ).pack(side="right")

        # Hebrew title
        ctk.CTkLabel(
            text, text=self.game.titleHe,
            font=(t.FONT_HEBREW, 12, "bold"),
            text_color=t.TEXT_PRIMARY, anchor="e",
        ).pack(fill="x", pady=(2, 0))

        # English title (in theme accent)
        ctk.CTkLabel(
            text, text=self.game.titleEn,
            font=(t.FONT_DISPLAY, 9, "bold"),
            text_color=accent, anchor="e",
        ).pack(fill="x")

        if self.game.progress is not None:
            ctk.CTkLabel(
                text, text=f"התקדמות · {self.game.progress}%",
                font=(t.FONT_DISPLAY, 9, "bold"),
                text_color=accent, anchor="e",
            ).pack(fill="x")

    def _mod_visual(self) -> tuple[str, str]:
        return {
            ml.STATE_ACTIVE:        ("פעיל",       t.STATE_ACTIVE),
            ml.STATE_DISABLED:      ("מושבת",      t.STATE_DISABLED),
            ml.STATE_NOT_INSTALLED: ("לא מותקן",   t.STATE_MISSING),
        }.get(self.mod_state, ("—", t.STATE_UNKNOWN))

    def _click_handler(self, _event) -> None:
        self.on_open(self.game, self.mod_state, self.install_path)

    def _context_handler(self, event) -> None:
        if self.on_context is not None:
            self.on_context(self.game, self.mod_state, self.install_path,
                            event.x_root, event.y_root)


# ─────────────────────────────────────────────────────────────
# Library view
# ─────────────────────────────────────────────────────────────
class LibraryView(ctk.CTkFrame):
    """
    Library view with a HAND-ROLLED scrollable area (`tk.Canvas` + scrollbar).

    Why not `CTkScrollableFrame`?
      Its inner CTk canvas leaves vertical paint trails on wheel-scroll
      (Windows-specific bug). Manual canvas + tk.Frame scrolls cleanly and
      builds faster — that's why the library no longer takes 2-3s to load.
    """

    MIN_COLUMNS = 2
    MAX_COLUMNS = 8

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=t.SURFACE_2, **kwargs)

        self._columns = 4  # auto-recalculated on resize
        self._last_width = 0
        self._detail_panel: GameDetailPanel | None = None
        self._canvas: tk.Canvas | None = None
        self._inner: tk.Frame | None = None
        self._inner_id: int | None = None

        self._build_header()
        self._build_scroll_area()
        self._quick_launcher_scan()
        self._scan_results = self._scan_now()
        self._build_sections()

        # Re-flow the grid when the window resizes
        self.bind("<Configure>", self._on_resize)

    # ─────────────────────────────────────────────────────────
    # Manual scrollable area — Canvas + Scrollbar + inner Frame
    # ─────────────────────────────────────────────────────────
    def _build_scroll_area(self) -> None:
        wrap = ctk.CTkFrame(self, fg_color=t.SURFACE_2)
        wrap.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(
            wrap, bg=t.SURFACE_2, bd=0, highlightthickness=0,
        )
        sb = ctk.CTkScrollbar(
            wrap, command=self._canvas.yview,
            button_color=t.SURFACE_4,
            button_hover_color=t.ACCENT_YELLOW,
        )
        self._canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        # Inner frame holds all section content
        self._inner = tk.Frame(self._canvas, bg=t.SURFACE_2, bd=0,
                               highlightthickness=0)
        self._inner_id = self._canvas.create_window(
            (0, 0), window=self._inner, anchor="nw",
        )

        # Keep scrollregion in sync with content size
        self._inner.bind("<Configure>", self._on_inner_configure)
        # Match inner frame width to canvas viewport
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        # Mouse wheel scrolling when hovering the canvas
        self._canvas.bind("<Enter>", lambda _e: self._bind_wheel())
        self._canvas.bind("<Leave>", lambda _e: self._unbind_wheel())

    def _on_inner_configure(self, _e) -> None:
        if self._canvas is not None:
            bbox = self._canvas.bbox("all")
            if bbox is not None:
                self._canvas.configure(scrollregion=bbox)

    def _on_canvas_configure(self, e) -> None:
        if self._canvas is not None and self._inner_id is not None:
            self._canvas.itemconfig(self._inner_id, width=e.width)

    def _bind_wheel(self) -> None:
        if self._canvas is not None:
            self._canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self) -> None:
        if self._canvas is not None:
            self._canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, e) -> None:
        if self._canvas is not None:
            self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    # ── header ──────────────────────────────────────────────
    def _build_header(self) -> None:
        ctk.CTkLabel(
            self, text="ה ס פ ר י י ה  ·  L I B R A R Y",
            font=t.FONT_KICKER, text_color=t.ACCENT_CYAN, anchor="e",
        ).pack(fill="x", padx=28, pady=(20, 0))

        bar = ctk.CTkFrame(self, fg_color=t.SURFACE_2)
        bar.pack(fill="x", padx=28, pady=(2, 8))

        # Deep scan button — walks all drives, finds games even when no
        # launcher (Steam/Epic/Ubisoft/GOG) knows about them.
        self._deep_btn = FlatButton(
            bar, text="סרוק כוננים",
            color=t.ACCENT_CYAN, hover=t.HOVER_CYAN,
            text_color=t.TEXT_ON_BRAND,
            width=130, height=36, command=self._deep_scan,
        )
        self._deep_btn.pack(side="left", padx=(0, 8))

        # Quick rescan (registry / manifests only)
        FlatButton(
            bar, text=S.LIB_REFRESH,
            color=t.ACCENT_YELLOW, hover=t.BRAND_HOVER,
            text_color=t.TEXT_ON_BRAND,
            width=110, height=36, command=lambda: (self._quick_launcher_scan(),
                                                    self._refresh()),
        ).pack(side="left")

        self._count_lbl = ctk.CTkLabel(
            bar, text="", font=t.FONT_BODY,
            text_color=t.TEXT_SECONDARY, anchor="e",
        )
        self._count_lbl.pack(side="left", padx=12)

        ctk.CTkLabel(
            bar, text=S.LIB_TITLE,
            font=t.FONT_PAGE_TITLE, text_color=t.ACCENT_YELLOW, anchor="e",
        ).pack(side="right", fill="x", expand=True)

    # ── scanning ────────────────────────────────────────────
    def _scan_now(self) -> dict[str, tuple[str | None, Path | None, bool]]:
        """
        Synchronously gather install + mod state for every catalog game.
        Uses the cached launcher-scan results (Steam / Ubisoft / Epic / GOG /
        Rockstar) — those have to be populated by `_quick_launcher_scan` first.
        """
        detected = game_detector.cached()
        results = {}
        for game in games_catalog.ALL_GAMES:
            results[game.id] = _resolve_install(game.id, detected)
        return results

    def _quick_launcher_scan(self) -> None:
        """Fast registry/manifest scan of all installed launchers."""
        game_detector.refresh_quick()

    def _deep_scan(self) -> None:
        """Walk every drive looking for installed games — runs in a thread
        so the UI stays responsive while it runs."""
        self._deep_btn.configure(state="disabled", text="סורק...")
        self._count_lbl.configure(text="סורק את כל הכוננים...")

        def worker():
            def progress(msg: str):
                try:
                    if self.winfo_exists():
                        self.after(0, self._count_lbl.configure, {"text": msg})
                except Exception:
                    pass
            game_detector.refresh_deep(progress_cb=progress)
            try:
                if self.winfo_exists():
                    self.after(0, self._on_deep_done)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_deep_done(self) -> None:
        self._deep_btn.configure(state="normal", text="סרוק כוננים")
        self._refresh()

    def _refresh(self) -> None:
        self._scan_results = self._scan_now()
        if hasattr(self, "_sections_container"):
            self._sections_container.destroy()
        self._build_sections()

    # ── section layout ──────────────────────────────────────
    def _build_sections(self) -> None:
        """Three sections rendered progressively so the library shows
        content within ~100ms and finishes filling in the background."""
        self._sections_container = tk.Frame(self._inner, bg=t.SURFACE_2,
                                            bd=0, highlightthickness=0)
        self._sections_container.pack(fill="x", padx=22, pady=(4, 20))

        # Bucket the catalog
        with_mod, installed_no_mod, missing = [], [], []
        for game in games_catalog.sorted_games():
            state, path, has_mod = self._scan_results.get(
                game.id, (None, None, False))
            if state in (ml.STATE_ACTIVE, ml.STATE_DISABLED):
                with_mod.append((game, state, path))
            elif path is not None:
                installed_no_mod.append((game, state, path))
            else:
                missing.append((game, state, path))

        # Update counter immediately
        self._count_lbl.configure(
            text=f"{len(games_catalog.ALL_GAMES)} כותרים  ·  "
                 f"{len(with_mod)} עם מודים  ·  "
                 f"{len(installed_no_mod)} מותקנים  ·  "
                 f"{len(missing)} לא מותקנים",
        )

        # First two sections render synchronously (small — ≤6 cards) so the
        # user sees content immediately. The "not installed" section is the
        # heavy one (26 cards) — render it incrementally via after_idle so
        # the UI stays responsive.
        self._render_section("מותקנים עם מוד פעיל", t.STATE_ACTIVE, with_mod)
        self._render_section("מותקנים — מוכנים להתקנת מוד",
                             t.ACCENT_CYAN, installed_no_mod)
        # Schedule heavy section in idle time
        self.after(10, self._render_section_lazy,
                   "לא מותקנים / מתוכננים", t.TEXT_MUTED, missing)

    def _render_section_lazy(self, title: str, accent: str,
                             items: list[tuple]) -> None:
        """Lazy render — header first, then cards in chunks of 4 per
        after_idle tick so the UI never freezes for more than ~50ms."""
        # Section header
        header = tk.Frame(self._sections_container, bg=t.SURFACE_2, bd=0,
                          highlightthickness=0)
        header.pack(fill="x", pady=(14, 8), padx=6)
        SectionHeader(header, title, accent=accent).pack(side="right", fill="x")
        tk.Label(
            header, text=f"{len(items)} כותרים",
            bg=t.SURFACE_2, fg=t.TEXT_MUTED,
            font=t.FONT_FOOTER, anchor="w",
        ).pack(side="left")

        if not items:
            tk.Label(
                self._sections_container,
                text="(אין משחקים בקטגוריה זו כרגע)",
                bg=t.SURFACE_2, fg=t.TEXT_MUTED,
                font=t.FONT_BODY, anchor="e",
            ).pack(fill="x", padx=18, pady=(0, 16))
            return

        grid = tk.Frame(self._sections_container, bg=t.SURFACE_2, bd=0,
                        highlightthickness=0)
        grid.pack(fill="x", padx=6, pady=(0, 10))
        cols = self._columns
        for col in range(cols):
            grid.grid_columnconfigure(col, weight=1, uniform="card")

        # Render in chunks
        self._lazy_grid = grid
        self._lazy_items = items
        self._lazy_cols = cols
        self._lazy_idx = 0
        self.after_idle(self._render_chunk)

    def _render_chunk(self) -> None:
        """Render 4 cards per tick. Keeps each tk event loop iteration short."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        chunk = 4
        end = min(self._lazy_idx + chunk, len(self._lazy_items))
        cols = self._lazy_cols
        for idx in range(self._lazy_idx, end):
            game, state, path = self._lazy_items[idx]
            card = GameCard(
                self._lazy_grid, game=game,
                mod_state=state, install_path=path,
                on_open=self._open_modal,
                on_context=self._show_context_menu,
            )
            card.grid(row=idx // cols, column=idx % cols,
                      padx=6, pady=6, sticky="n")
        self._lazy_idx = end
        if self._lazy_idx < len(self._lazy_items):
            self.after_idle(self._render_chunk)

    def _render_section(self, title: str, accent: str,
                        items: list[tuple[CatalogGame, str | None, Path | None]]) -> None:
        # Section header is ALWAYS shown — even when empty — so the user
        # always sees the full library structure (with-mod / installed /
        # missing) and knows where games will appear later.
        header = tk.Frame(self._sections_container, bg=t.SURFACE_2, bd=0,
                          highlightthickness=0)
        header.pack(fill="x", pady=(14, 8), padx=6)
        SectionHeader(header, title, accent=accent).pack(side="right", fill="x")
        tk.Label(
            header, text=f"{len(items)} כותרים",
            bg=t.SURFACE_2, fg=t.TEXT_MUTED,
            font=t.FONT_FOOTER, anchor="w",
        ).pack(side="left")

        # Empty-state placeholder
        if not items:
            tk.Label(
                self._sections_container,
                text="(אין משחקים בקטגוריה זו כרגע)",
                bg=t.SURFACE_2, fg=t.TEXT_MUTED,
                font=t.FONT_BODY, anchor="e",
            ).pack(fill="x", padx=18, pady=(0, 16))
            return

        # Section grid — column count derives from current window width so
        # the spacing between cards stays uniform when resizing the window.
        grid = tk.Frame(self._sections_container, bg=t.SURFACE_2, bd=0,
                        highlightthickness=0)
        grid.pack(fill="x", padx=6, pady=(0, 10))
        cols = self._columns
        for col in range(cols):
            grid.grid_columnconfigure(col, weight=1, uniform="card")

        for idx, (game, state, path) in enumerate(items):
            card = GameCard(
                grid, game=game,
                mod_state=state, install_path=path,
                on_open=self._open_modal,
                on_context=self._show_context_menu,
            )
            card.grid(row=idx // cols, column=idx % cols,
                      padx=6, pady=6, sticky="n")

    # ── responsive grid (column count follows window width) ──
    def _on_resize(self, event) -> None:
        if event.width == self._last_width:
            return
        self._last_width = event.width
        # Card is 200px wide + 12px outer margin → ~212 per column.
        new_cols = max(self.MIN_COLUMNS, min(self.MAX_COLUMNS, event.width // 220))
        if new_cols != self._columns:
            self._columns = new_cols
            # Debounce: rebuild on next idle so we don't thrash during drag
            self.after_idle(self._rebuild_sections)

    def _rebuild_sections(self) -> None:
        if hasattr(self, "_sections_container"):
            self._sections_container.destroy()
        self._build_sections()

    # ── embedded detail panel (replaces the grid inside this window) ──
    def _open_modal(self, game: CatalogGame, mod_state: str | None,
                    install_path: Path | None) -> None:
        # Tear down anything previously shown
        if self._detail_panel is not None:
            try:
                self._detail_panel.destroy()
            except Exception:
                pass
            self._detail_panel = None
        # Hide grid (header stays visible). The scroll canvas itself is hidden
        # via pack_forget on its parent; sections live inside it.
        if self._canvas is not None:
            self._canvas.master.pack_forget()
        # Build & show detail directly on self (the LibraryView CTkFrame)
        self._detail_panel = GameDetailPanel(
            self,
            game=game, mod_state=mod_state, install_path=install_path,
            on_back=self._close_detail,
            on_action=self._do_mod_action,
            on_path_change=self._on_path_change,
        )
        self._detail_panel.pack(fill="both", expand=True, padx=22, pady=(4, 20))

    def _close_detail(self) -> None:
        if self._detail_panel is not None:
            try:
                self._detail_panel.destroy()
            except Exception:
                pass
            self._detail_panel = None
        # Re-show the scroll area
        if self._canvas is not None:
            self._canvas.master.pack(fill="both", expand=True)

    def _on_path_change(self, game_id: str, _new_path: Path | None) -> None:
        # User saved or cleared a custom path inside the detail modal;
        # refresh the library so the card reflects the new state.
        self._refresh()

    # ── context menu (right-click) ───────────────────────────
    def _show_context_menu(self, game: CatalogGame, mod_state: str | None,
                           install_path: Path | None,
                           x_root: int, y_root: int) -> None:
        menu = tk.Menu(
            self, tearoff=0,
            bg=t.SURFACE_3, fg=t.TEXT_PRIMARY,
            activebackground=t.ACCENT_YELLOW, activeforeground=t.TEXT_ON_BRAND,
            font=(t.FONT_HEBREW, 11),
            bd=0, relief="flat",
        )
        menu.add_command(
            label="פתח כרטיס משחק",
            command=lambda: self._open_modal(game, mod_state, install_path),
        )
        menu.add_separator()
        menu.add_command(
            label="הגדרות",
            command=lambda: self._open_settings(game, mod_state, install_path),
        )
        if install_path is not None:
            menu.add_command(
                label="פתח תיקייה",
                command=lambda: self._open_folder(install_path),
            )
        menu.add_separator()
        menu.add_command(
            label="הגדר נתיב ידנית...",
            command=lambda: self._set_path_dialog(game),
        )
        if user_paths.get(game.id) is not None:
            menu.add_command(
                label="נקה נתיב מותאם",
                command=lambda: (user_paths.set_path(game.id, None),
                                 self._refresh()),
            )
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

    def _open_settings(self, game: CatalogGame, mod_state: str | None,
                       install_path: Path | None) -> None:
        # Settings IS the detail modal — it has the sidebar with path field.
        self._open_modal(game, mod_state, install_path)

    def _open_folder(self, path: Path) -> None:
        if path is None or not path.exists():
            return
        import os, subprocess, sys
        if sys.platform == "win32":
            os.startfile(str(path))  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _set_path_dialog(self, game: CatalogGame) -> None:
        current = user_paths.get(game.id)
        initial = str(current) if current else str(Path.home())
        folder = filedialog.askdirectory(
            initialdir=initial,
            title=f"בחר תיקיית התקנה — {game.titleHe}",
        )
        if folder:
            user_paths.set_path(game.id, folder)
            self._refresh()

    def _do_mod_action(self, game: CatalogGame, action: str,
                       install_path: Path | None) -> None:
        # Resolve launcher GameConfig
        cfg = None
        for g in GAMES.values():
            if g.internal_id == game.id and g.mod_files:
                cfg = g
                break
        if cfg is None or install_path is None:
            messagebox.showinfo(S.CONFIRM_TITLE, "המשחק לא נתמך לניהול דרך המנהל.")
            return

        if action == "enable":
            ml.enable_mod(cfg, install_path)
        elif action == "disable":
            ml.disable_mod(cfg, install_path)
        elif action == "uninstall":
            if not messagebox.askyesno(S.CONFIRM_TITLE, S.CONFIRM_UNINST):
                return
            ml.uninstall_mod(cfg, install_path)

        self._refresh()
