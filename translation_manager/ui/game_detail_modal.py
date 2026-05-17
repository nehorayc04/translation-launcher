"""
Big-Picture style game window.

Opens maximized with a large cover, title bar, description, play button,
and a settings sidebar where the user can configure the install path
manually or browse for it.
"""

import os
import subprocess
import sys
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from .. import mod_logic as ml
from .. import paths as user_paths
from .. import theme as t
from ..config import Strings as S
from ..games_catalog import CatalogGame
from .components import CoverImage, FlatButton, GhostButton


_AVAIL_LABEL = {
    "available":   ("זמין",     "#22c55e"),
    "in-progress": ("בתהליך",  "#fff700"),
    "coming-soon": ("בקרוב",   "#00ffe0"),
    "planned":     ("מתוכנן",  "#5a5e6f"),
}


def _find_executable(install_path: Path) -> Path | None:
    """Best-effort: locate the main game .exe inside an install dir."""
    if install_path is None or not install_path.exists():
        return None
    # Prefer well-known sub-paths first
    candidates = [
        install_path / "bin" / "x64",
        install_path / "bin",
        install_path / "Bin64",
        install_path / "x64",
        install_path,
    ]
    for c in candidates:
        if not c.exists():
            continue
        try:
            exes = [p for p in c.iterdir() if p.suffix.lower() == ".exe"]
        except (OSError, PermissionError):
            continue
        # Filter out launchers / installers / crash reporters
        filtered = [e for e in exes if not any(
            kw in e.name.lower() for kw in
            ("launcher", "crash", "redist", "setup", "unins", "directx")
        )]
        if filtered:
            # Largest .exe is usually the main game binary
            return max(filtered, key=lambda p: p.stat().st_size)
        if exes:
            return max(exes, key=lambda p: p.stat().st_size)
    return None


class GameDetailModal(ctk.CTkToplevel):
    """Big-Picture-style window: large cover on the left, info+play on the
    right, settings sidebar on the far right."""

    def __init__(self, master, game: CatalogGame,
                 mod_state: str | None = None,
                 install_path: Path | None = None,
                 on_action: Callable | None = None,
                 on_path_change: Callable | None = None):
        super().__init__(master)
        self.game = game
        self.mod_state = mod_state
        self.install_path = install_path
        self.on_action = on_action
        self.on_path_change = on_path_change

        self.title(game.titleHe)
        self.minsize(900, 600)
        self.configure(fg_color=t.SURFACE_0)
        try:
            self.state("zoomed")          # maximize on Windows
        except Exception:
            self.geometry("1280x780")
        self.transient(master.winfo_toplevel())
        self.after(150, self._try_grab)

        self._build()
        self.bind("<Escape>", lambda _e: self.destroy())

    def _try_grab(self) -> None:
        try:
            self.grab_set()
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────
    def _build(self) -> None:
        accent  = t.CARD_ACCENTS.get(self.game.theme_key, t.CARD_ACCENTS["default"])
        bg_top, _ = t.CARD_GRADIENTS.get(self.game.theme_key, t.CARD_GRADIENTS["default"])
        self.configure(fg_color=bg_top)

        # ── Close button (top-left for Hebrew RTL) ──
        close_btn = GhostButton(
            self, text="✕  סגור",
            accent=t.TEXT_SECONDARY, width=100, height=32,
            command=self.destroy,
        )
        close_btn.place(relx=0.0, rely=0.0, x=18, y=18, anchor="nw")

        # Header kicker — full-bleed across the top, right-aligned
        ctk.CTkLabel(
            self, text="ת ר ג ו ם   ע ב ר י  ·  H E B R E W   A I",
            font=(t.FONT_DISPLAY, 11, "bold"),
            text_color=accent,
        ).place(relx=1.0, rely=0.0, x=-30, y=24, anchor="ne")

        # ── Main content split ──
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.place(relx=0.5, rely=0.5, anchor="center",
                   relwidth=0.94, relheight=0.86)

        # Settings sidebar — RIGHT side (Hebrew RTL feel)
        sidebar = self._build_settings_sidebar(main)
        sidebar.pack(side="right", fill="y", padx=(20, 0))

        # Center: info + actions
        center = ctk.CTkFrame(main, fg_color="transparent")
        center.pack(side="right", fill="both", expand=True, padx=(20, 20))
        self._build_info_section(center, accent)

        # Left: huge cover
        left = ctk.CTkFrame(main, fg_color="transparent")
        left.pack(side="left", fill="y")
        self._build_cover(left)

    # ─────────────────────────────────────────────────────────
    def _build_cover(self, parent) -> None:
        cover = CoverImage(
            parent,
            game_id=self.game.id,
            theme_key=self.game.theme_key,
            width=420, height=630,
            corner_radius=18,
            fallback_text=self.game.titleEn[:2].upper(),
            fallback_size=64,
        )
        cover.pack(pady=20)

    # ─────────────────────────────────────────────────────────
    def _build_info_section(self, parent, accent: str) -> None:
        # Hebrew title — huge
        ctk.CTkLabel(
            parent, text=self.game.titleHe,
            font=(t.FONT_HEBREW, 42, "bold"),
            text_color=t.TEXT_PRIMARY, anchor="e",
        ).pack(fill="x", pady=(20, 0))

        # English title — display font, accent color
        ctk.CTkLabel(
            parent, text=self.game.titleEn,
            font=(t.FONT_DISPLAY, 18, "bold"),
            text_color=accent, anchor="e",
        ).pack(fill="x", pady=(0, 14))

        # Meta row: availability badge + version
        meta = ctk.CTkFrame(parent, fg_color="transparent")
        meta.pack(fill="x", pady=(0, 14))

        avail_label, avail_color = _AVAIL_LABEL.get(
            self.game.availability, ("—", t.TEXT_MUTED))
        ctk.CTkLabel(
            meta, text=f"  {avail_label}  ",
            fg_color=avail_color, text_color=t.TEXT_ON_BRAND,
            font=(t.FONT_HEBREW, 12, "bold"), corner_radius=8,
        ).pack(side="right")

        if self.game.version not in ("—", ""):
            ctk.CTkLabel(
                meta, text=self.game.version,
                font=(t.FONT_DISPLAY, 11, "bold"),
                text_color=accent,
            ).pack(side="right", padx=(8, 12))

        # Tagline
        ctk.CTkLabel(
            parent, text=self.game.tagline,
            font=(t.FONT_HEBREW, 17),
            text_color=accent, anchor="e", justify="right",
            wraplength=560,
        ).pack(fill="x", pady=(0, 10))

        # Description
        ctk.CTkLabel(
            parent, text=self.game.description,
            font=(t.FONT_HEBREW, 13),
            text_color=t.TEXT_SECONDARY, anchor="e", justify="right",
            wraplength=560,
        ).pack(fill="x", pady=(0, 16))

        # Progress bar
        if self.game.progress is not None:
            ctk.CTkLabel(
                parent, text=f"התקדמות הפרויקט · {self.game.progress}%",
                font=(t.FONT_HEBREW, 11, "bold"),
                text_color=accent, anchor="e",
            ).pack(fill="x", pady=(0, 4))
            track = ctk.CTkFrame(parent, fg_color=t.SURFACE_4, height=8,
                                 corner_radius=4)
            track.pack(fill="x", pady=(0, 18))
            track.pack_propagate(False)
            fill = ctk.CTkFrame(track, fg_color=accent, corner_radius=4)
            fill.place(relx=0, rely=0, relheight=1,
                       relwidth=max(0.0, min(self.game.progress, 100)) / 100)

        # ── Action buttons ──
        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.pack(fill="x", pady=(10, 0))

        # Play button (always visible — disabled if no install path)
        exe = _find_executable(self.install_path) if self.install_path else None
        play_state = "normal" if exe else "disabled"
        play_btn = FlatButton(
            actions, text="▶  שחק",
            color=accent, hover=accent,
            text_color=t.TEXT_ON_BRAND,
            width=180, height=48, command=self._launch,
            font=(t.FONT_HEBREW, 16, "bold"),
        )
        play_btn.configure(state=play_state)
        play_btn.pack(side="right")
        if exe is None:
            ctk.CTkLabel(
                actions, text="לא נמצא קובץ הרצה — הגדר נתיב בצד",
                font=t.FONT_FOOTER, text_color=t.TEXT_MUTED, anchor="e",
            ).pack(side="right", padx=(8, 14))

        # Mod controls (only if launcher manages this title)
        if self.mod_state is not None and self.install_path is not None:
            if self.mod_state == ml.STATE_ACTIVE:
                FlatButton(
                    actions, text=S.BTN_DISABLE,
                    color=t.STATE_DISABLED, hover=t.HOVER_AMBER,
                    text_color=t.TEXT_ON_LIGHT,
                    width=140, height=48,
                    command=lambda: self._do_action("disable"),
                ).pack(side="right", padx=(12, 0))
            elif self.mod_state == ml.STATE_DISABLED:
                FlatButton(
                    actions, text=S.BTN_ENABLE,
                    color=t.STATE_ACTIVE, hover=t.HOVER_GREEN,
                    width=140, height=48,
                    command=lambda: self._do_action("enable"),
                ).pack(side="right", padx=(12, 0))

    # ─────────────────────────────────────────────────────────
    def _build_settings_sidebar(self, parent) -> ctk.CTkFrame:
        """Right-side panel: path config + folder browse."""
        wrap = ctk.CTkFrame(
            parent, fg_color=t.SURFACE_3, corner_radius=14,
            border_width=1, border_color=t.BORDER_DIM, width=300,
        )
        wrap.pack_propagate(False)

        ctk.CTkLabel(
            wrap, text="ה ג ד ר ו ת",
            font=(t.FONT_DISPLAY, 11, "bold"),
            text_color=t.ACCENT_CYAN, anchor="e",
        ).pack(fill="x", padx=18, pady=(20, 4))

        ctk.CTkLabel(
            wrap, text="נתיב המשחק",
            font=(t.FONT_HEBREW, 14, "bold"),
            text_color=t.TEXT_PRIMARY, anchor="e",
        ).pack(fill="x", padx=18, pady=(8, 6))

        # Path entry (preloaded with detected path if any)
        self._path_entry = ctk.CTkEntry(
            wrap, font=(t.FONT_HEBREW, 11),
            fg_color=t.SURFACE_0, border_color=t.ACCENT_CYAN,
            border_width=1, text_color=t.TEXT_PRIMARY, justify="right",
            height=40,
        )
        self._path_entry.pack(fill="x", padx=18, pady=(0, 8))
        if self.install_path:
            self._path_entry.insert(0, str(self.install_path))

        # Browse button
        FlatButton(
            wrap, text="עיון בתיקיות...",
            color=t.ACCENT_CYAN, hover=t.HOVER_CYAN,
            text_color=t.TEXT_ON_BRAND,
            width=260, height=36, command=self._browse_path,
        ).pack(fill="x", padx=18, pady=(0, 8))

        # Save / Clear buttons
        save_row = ctk.CTkFrame(wrap, fg_color="transparent")
        save_row.pack(fill="x", padx=18, pady=(0, 18))

        FlatButton(
            save_row, text="שמור",
            color=t.ACCENT_YELLOW, hover=t.BRAND_HOVER,
            text_color=t.TEXT_ON_BRAND,
            width=120, height=34, command=self._save_path,
        ).pack(side="right")

        GhostButton(
            save_row, text="נקה",
            accent=t.STATE_MISSING, width=80, height=34,
            command=self._clear_path,
        ).pack(side="right", padx=(0, 8))

        # Divider
        ctk.CTkFrame(wrap, fg_color=t.BORDER_DIM, height=1).pack(
            fill="x", padx=18, pady=(0, 14))

        # Open install folder
        FlatButton(
            wrap, text="פתח תיקיית התקנה",
            color=t.SURFACE_4, hover=t.SURFACE_5,
            text_color=t.TEXT_PRIMARY,
            width=260, height=36, command=self._open_folder,
        ).pack(fill="x", padx=18, pady=(0, 6))

        # Mod uninstall (if applicable)
        if self.mod_state in (ml.STATE_ACTIVE, ml.STATE_DISABLED):
            GhostButton(
                wrap, text=S.BTN_UNINSTALL,
                accent=t.STATE_MISSING, width=260, height=36,
                command=lambda: self._do_action("uninstall"),
            ).pack(fill="x", padx=18, pady=(0, 6))

        return wrap

    # ─────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────
    def _browse_path(self) -> None:
        initial = self.install_path or Path.home()
        folder = filedialog.askdirectory(
            initialdir=str(initial), title="בחר תיקיית התקנת המשחק",
        )
        if folder:
            self._path_entry.delete(0, "end")
            self._path_entry.insert(0, folder)

    def _save_path(self) -> None:
        raw = self._path_entry.get().strip().strip('"')
        if not raw:
            self._clear_path()
            return
        p = Path(raw)
        if not p.exists():
            messagebox.showwarning("נתיב לא קיים", f"התיקייה לא נמצאה:\n{p}")
            return
        user_paths.set_path(self.game.id, str(p))
        self.install_path = p
        messagebox.showinfo("נשמר", "הנתיב נשמר. הספרייה תתעדכן עם הסגירה.")
        if self.on_path_change:
            self.on_path_change(self.game.id, p)

    def _clear_path(self) -> None:
        user_paths.set_path(self.game.id, None)
        self._path_entry.delete(0, "end")
        if self.on_path_change:
            self.on_path_change(self.game.id, None)

    def _open_folder(self) -> None:
        target = self.install_path
        if target is None or not target.exists():
            messagebox.showwarning("אין נתיב", "לא נמצאה תיקיית התקנה.")
            return
        if sys.platform == "win32":
            os.startfile(str(target))  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(target)])

    def _launch(self) -> None:
        exe = _find_executable(self.install_path) if self.install_path else None
        if exe is None:
            messagebox.showwarning("לא נמצא הרצה", "לא ניתן למצוא את קובץ ההרצה.")
            return
        try:
            subprocess.Popen([str(exe)], cwd=str(exe.parent))
        except OSError as e:
            messagebox.showerror("שגיאה", f"לא ניתן להפעיל:\n{e}")

    def _do_action(self, action: str) -> None:
        if self.on_action is not None:
            self.on_action(self.game, action, self.install_path)
        self.destroy()
