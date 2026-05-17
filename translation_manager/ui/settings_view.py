"""
Settings view — manage custom game paths, the website project path,
and reset auto-detection. Designed to mirror the layout language of the
Home / Library views (right-aligned section titles, accented dividers).
"""

import customtkinter as ctk

from .. import theme as t
from .. import website
from ..config import WEBSITE_PROJECT_DIR, Strings as S
from .components import FlatButton, SectionHeader


class SettingsView(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=t.SURFACE_2,
            scrollbar_fg_color=t.SURFACE_2,
            scrollbar_button_color=t.SURFACE_4,
            scrollbar_button_hover_color=t.ACCENT_SETTINGS,
            **kwargs,
        )
        self._build_title()
        self._build_paths_section()
        self._build_website_section()
        self._build_about_section()

    def _build_title(self) -> None:
        # Kicker
        ctk.CTkLabel(
            self, text="ה ג ד ר ו ת  ·  S E T T I N G S",
            font=t.FONT_KICKER, text_color=t.ACCENT_CYAN, anchor="e",
        ).pack(fill="x", padx=28, pady=(20, 0))

        # Page title in theme.primary (yellow / off-white via theme tokens)
        ctk.CTkLabel(
            self, text=S.SETTINGS_TITLE,
            font=t.FONT_PAGE_TITLE, text_color=t.ACCENT_YELLOW, anchor="e",
        ).pack(fill="x", padx=28, pady=(2, 18))

    def _build_paths_section(self) -> None:
        SectionHeader(self, S.SETTINGS_PATHS, accent=t.ACCENT_LIB).pack(
            fill="x", padx=28, pady=(0, 8))

        card = ctk.CTkFrame(
            self, fg_color=t.SURFACE_3, corner_radius=10,
            border_width=1, border_color=t.BORDER_DIM,
        )
        card.pack(fill="x", padx=22, pady=(0, 18))

        ctk.CTkLabel(
            card,
            text="ניתן להוסיף נתיב מותאם אישית לכל משחק דרך מסך הספרייה — "
                 "לחץ על כפתור 'עיון...' בכרטיס המשחק.",
            font=t.FONT_BODY, text_color=t.TEXT_SECONDARY,
            anchor="e", justify="right", wraplength=620,
        ).pack(fill="x", padx=16, pady=16)

    def _build_website_section(self) -> None:
        SectionHeader(self, S.SETTINGS_WEBSITE, accent=t.ACCENT_HOME).pack(
            fill="x", padx=28, pady=(0, 8))

        card = ctk.CTkFrame(
            self, fg_color=t.SURFACE_3, corner_radius=10,
            border_width=1, border_color=t.BORDER_DIM,
        )
        card.pack(fill="x", padx=22, pady=(0, 18))

        body = ctk.CTkFrame(card, fg_color=t.SURFACE_3)
        body.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(
            body, text=str(WEBSITE_PROJECT_DIR),
            font=("Consolas", 11), text_color=t.TEXT_MUTED, anchor="e",
        ).pack(fill="x", pady=(0, 12))

        actions = ctk.CTkFrame(body, fg_color=t.SURFACE_3)
        actions.pack(fill="x")
        FlatButton(
            actions, text=S.HOME_HERO_BUILD,
            color=t.BRAND_PRIMARY, hover=t.BRAND_HOVER,
            width=160, height=36,
            command=website.open_project_folder,
        ).pack(side="right")

    def _build_about_section(self) -> None:
        SectionHeader(self, "אודות", accent=t.ACCENT_SETTINGS).pack(
            fill="x", padx=28, pady=(0, 8))

        card = ctk.CTkFrame(
            self, fg_color=t.SURFACE_3, corner_radius=10,
            border_width=1, border_color=t.BORDER_DIM,
        )
        card.pack(fill="x", padx=22, pady=(0, 24))

        ctk.CTkLabel(
            card,
            text="Translation Manager — מנהל מודי תרגום למשחקי PC.\n"
                 "מבוסס Python 3 + customtkinter.  © 2026 Nehoray",
            font=t.FONT_BODY, text_color=t.TEXT_SECONDARY,
            anchor="e", justify="right",
        ).pack(fill="x", padx=16, pady=16)
