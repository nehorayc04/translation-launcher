"""
Main application window — Ubisoft-style chrome:

┌────────────────────────────────────────────────────────────┐
│        ┃                                                   │  ← native title bar
│  side  ┃                  main content                     │     (min/max/close)
│  bar   ┃                                                   │
│        ┃                                                   │
├────────┴───────────────────────────────────────────────────┤
│   bottom update bar (status, news ticker)                  │
└────────────────────────────────────────────────────────────┘
"""

from pathlib import Path

import customtkinter as ctk

from .. import theme as t
from .. import website
from ..config import Strings as S
from .home_view import HomeView
from .library_view import LibraryView
from .settings_view import SettingsView
from .sidebar import Sidebar
from .update_bar import UpdateBar
from .video_background import VideoBackground

VIDEO_PATH = Path(__file__).parent.parent / "214405.mp4"


class TranslationManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(S.APP_TITLE)
        self.geometry("1280x780")
        self.minsize(1080, 680)
        self.configure(fg_color=t.SURFACE_0)
        # Native title bar (min/max/close) — do NOT call overrideredirect.

        # ── Video background ──
        # Lives BENEATH every other widget. Built once and preserved across
        # rebuild_ui calls (rebuild_ui skips this widget when destroying).
        self._video_bg = VideoBackground(self, VIDEO_PATH, fps_cap=24)
        self._video_bg.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        self._video_bg.lower()
        # Seed the decode thread with the initial window size so it doesn't
        # spin painting full-resolution frames into a 200x200 default Label
        # before the first <Configure> event fires.
        self._video_bg._target_size = (1280, 780)

        self._current_view = "home"
        self._build_layout()
        self._show_view(self._current_view)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─────────────────────────────────────────────────────────
    # Rebuild — wipes the whole UI tree and reconstructs with the
    # currently-applied theme tokens. Called when the user toggles
    # between "game" and "clean" modes.
    # ─────────────────────────────────────────────────────────
    def rebuild_ui(self) -> None:
        active_view = self._current_view
        # Destroy every child widget EXCEPT the video background so the
        # decode thread keeps running through the rebuild.
        for child in list(self.winfo_children()):
            if child is self._video_bg:
                continue
            child.destroy()
        self.configure(fg_color=t.SURFACE_0)
        self._build_layout()
        self._show_view(active_view)
        # Re-lower so the rebuilt chrome stays on top of the video
        self._video_bg.lower()

    # ─────────────────────────────────────────────────────────
    def _build_layout(self) -> None:
        # Top container splits horizontally: sidebar | main area.
        # Generous margins + rounded corners + transparent fill so the
        # blurred-glass video shows around AND through the soft edges.
        top = ctk.CTkFrame(self, fg_color="transparent",
                           corner_radius=18)
        top.pack(side="top", fill="both", expand=True,
                 padx=20, pady=(20, 6))

        # Sidebar on the LEFT (rounded glass panel).
        self.sidebar = Sidebar(top, on_nav=self._show_view)
        self.sidebar.pack(side="left", fill="y", padx=(0, 10))

        # Main content area — rounded glass panel
        self.main = ctk.CTkFrame(top, fg_color=t.SURFACE_2, corner_radius=20)
        self.main.pack(side="left", fill="both", expand=True)

        # Lazy view construction — only Home is built at startup; Library and
        # Settings are constructed the first time the user navigates to them.
        # This cuts cold-start time roughly in half (the library scans 7 game
        # directories and builds 14+ widgets per tile).
        self._view_factories: dict[str, type[ctk.CTkFrame]] = {
            "home":     HomeView,
            "library":  LibraryView,
            "settings": SettingsView,
        }
        self.views: dict[str, ctk.CTkFrame] = {
            "home": HomeView(self.main),
        }

        # Bottom update bar — pinned to the window bottom with side margins
        # matching the top frame so the video forms a continuous frame.
        self.update_bar = UpdateBar(self)
        self.update_bar.pack(side="bottom", fill="x", padx=22, pady=(0, 14))

        # Status overlay (a thin label above the update bar, used by views)
        self._status_lbl = ctk.CTkLabel(
            self, text="", font=t.FONT_BODY,
            text_color=t.BRAND_LIGHT, anchor="e",
        )
        self._status_lbl.pack(side="bottom", fill="x", padx=24, pady=(0, 2))

        # Activate first nav item
        self.sidebar.set_active("home")

    # ─────────────────────────────────────────────────────────
    def _show_view(self, key: str) -> None:
        self._current_view = key
        # Lazily construct the view on first access
        if key not in self.views and key in self._view_factories:
            self.views[key] = self._view_factories[key](self.main)
        for k, view in self.views.items():
            view.pack_forget()
        self.views[key].pack(fill="both", expand=True)
        # Keep the sidebar highlight in sync when navigation is triggered
        # programmatically (e.g. after a rebuild)
        self.sidebar.set_active(key)

    # ─────────────────────────────────────────────────────────
    # Public hook used by views to surface short status messages
    # ─────────────────────────────────────────────────────────
    def report_status(self, text: str, warn: bool = False) -> None:
        self._status_lbl.configure(
            text=text,
            text_color=t.STATE_MISSING if warn else t.BRAND_LIGHT,
        )
        # auto-clear after 5s
        self.after(5000, lambda: self._status_lbl.configure(text=""))

    def _on_close(self) -> None:
        website.shutdown_server()
        self.destroy()
