"""
Theme — palette and tokens lifted from the website's `src/theme/themes.ts`.

Supports two **chrome modes** matching the website's ThemeToggle:

  • `"game"`  — Cyberpunk chrome: yellow #fff700 + cyan #00ffe0 on deep
                purple-tinted black. Orbitron display font.
  • `"clean"` — Neutral grayscale chrome: off-white text on slightly-blue
                dark background. System fonts. No yellow highlights.

Per-game cover gradients (CARD_GRADIENTS / CARD_ACCENTS) DO NOT swap with
the mode — each game keeps its own theme on its card. The chrome (sidebar,
buttons, text, accents) is what changes.

Switching modes:
    >>> from translation_manager import theme
    >>> theme.apply_mode("clean")   # updates module globals
"""

# ═════════════════════════════════════════════════════════════
# Static tokens — IDENTICAL in both modes
# ═════════════════════════════════════════════════════════════

# Status colors (universal)
STATE_ACTIVE    = "#22c55e"   # green
STATE_DISABLED  = "#f59e0b"   # amber
STATE_MISSING   = "#ef4444"   # red
STATE_UNKNOWN   = "#64748b"   # slate

HOVER_GREEN     = "#15803d"
HOVER_CYAN      = "#0e7490"
HOVER_AMBER     = "#cc8400"
HOVER_RED       = "#b91c1c"
HOVER_GOLD      = "#a98b2c"
HOVER_PURPLE    = "#7e22ce"

# Text-on-bright-button is always dark
TEXT_ON_LIGHT   = "#0a0a14"
TEXT_ON_BRAND   = "#0a0a14"

# Layout constants
KICKER_TRACKING = "  "

# Per-game cover gradients (from website themes.ts) — DO NOT swap on mode
CARD_GRADIENTS: dict[str, tuple[str, str]] = {
    "cyberpunk":  ("#070710", "#1a0d40"),
    "tsushima":   ("#0a0303", "#3a0a0a"),
    "alanwake":   ("#050807", "#0a1a14"),
    "rdr":        ("#1a1108", "#3a2008"),
    "hogwarts":   ("#070818", "#0a164a"),
    "default":    ("#0a0a14", "#101830"),
    "gta":        ("#0a0a14", "#101830"),
    "elden":      ("#1a1108", "#3a2008"),
    "witcher":    ("#0a0303", "#3a0a0a"),
    "bg3":        ("#070818", "#0a164a"),
}

CARD_ACCENTS: dict[str, str] = {
    "cyberpunk":  "#fff700",
    "tsushima":   "#c10916",
    "alanwake":   "#a8c4a2",
    "rdr":        "#c7791e",
    "hogwarts":   "#d4af37",
    "default":    "#88ccff",
    "gta":        "#88ccff",
    "elden":      "#c7791e",
    "witcher":    "#c10916",
    "bg3":        "#d4af37",
}


# ═════════════════════════════════════════════════════════════
# Mode-specific palettes
# ═════════════════════════════════════════════════════════════
_GAME_TOKENS = {
    # Brand
    "ACCENT_YELLOW":   "#fff700",
    "ACCENT_CYAN":     "#00ffe0",
    "BG_BASE":         "#070710",
    "AMBIENT_PURPLE":  "#1a0d40",
    # Surfaces — clear hierarchy so rounded corners on panels read
    # visibly against the window bg (and against each other).
    "SURFACE_0":       "#050510",   # window bg (darkest — where video peeks)
    "SURFACE_1":       "#121226",   # sidebar / chrome panels
    "SURFACE_2":       "#121226",   # main content panel
    "SURFACE_3":       "#1a1a35",   # cards inside panels
    "SURFACE_4":       "#26264a",   # card hover / accent inputs
    "SURFACE_5":       "#33335c",   # highest highlight
    "SURFACE_NAV":     "#0a0a14",
    # Strokes
    "BORDER_DIM":      "#1f1f30",
    "BORDER_BRIGHT":   "#33334a",
    "BORDER_ACCENT":   "#3a3a14",   # ≈ #fff70022 over dark
    # Primary action (yellow)
    "BRAND_PRIMARY":   "#fff700",
    "BRAND_HOVER":     "#d4cf00",
    "BRAND_LIGHT":     "#fff966",
    "BRAND_DARK":      "#9c9700",
    # Section accents
    "ACCENT_HOME":     "#fff700",
    "ACCENT_LIB":      "#d4af37",
    "ACCENT_SETTINGS": "#00ffe0",
    # Text
    "TEXT_PRIMARY":    "#f0f0ff",
    "TEXT_SECONDARY":  "#a0a7b3",
    "TEXT_MUTED":      "#5a5e6f",
    "TEXT_ACCENT":     "#fff700",
    # Fonts
    "FONT_DISPLAY":    "Orbitron",
    "FONT_HEBREW":     "Heebo",
    "FONT_FALLBACK":   "Segoe UI",
    "FONT_FAMILY_BOLD":"Segoe UI Semibold",
}

_CLEAN_TOKENS = {
    # Brand (off-white instead of yellow)
    "ACCENT_YELLOW":   "#eef0f4",
    "ACCENT_CYAN":     "#a0a7b3",
    "BG_BASE":         "#0a0d18",
    "AMBIENT_PURPLE":  "#0e1424",
    # Surfaces (slightly bluer dark)
    "SURFACE_0":       "#0a0d18",
    "SURFACE_1":       "#0e1424",
    "SURFACE_2":       "#0a0d18",
    "SURFACE_3":       "#141a2a",
    "SURFACE_4":       "#1c2238",
    "SURFACE_5":       "#252c44",
    "SURFACE_NAV":     "#0a0d18",
    # Strokes
    "BORDER_DIM":      "#1e2434",
    "BORDER_BRIGHT":   "#2f3650",
    "BORDER_ACCENT":   "#2a3046",   # neutral, no yellow tint
    # Primary action (off-white pill instead of yellow)
    "BRAND_PRIMARY":   "#eef0f4",
    "BRAND_HOVER":     "#c5cad4",
    "BRAND_LIGHT":     "#ffffff",
    "BRAND_DARK":      "#a0a7b3",
    # Section accents (all neutral grey)
    "ACCENT_HOME":     "#eef0f4",
    "ACCENT_LIB":      "#a0a7b3",
    "ACCENT_SETTINGS": "#a0a7b3",
    # Text
    "TEXT_PRIMARY":    "#eef0f4",
    "TEXT_SECONDARY":  "#a0a7b3",
    "TEXT_MUTED":      "#5a627a",
    "TEXT_ACCENT":     "#eef0f4",
    # Fonts — system stack, fall back to Segoe UI / Heebo
    "FONT_DISPLAY":    "Segoe UI",
    "FONT_HEBREW":     "Heebo",
    "FONT_FALLBACK":   "Segoe UI",
    "FONT_FAMILY_BOLD":"Segoe UI Semibold",
}


# ═════════════════════════════════════════════════════════════
# State + mutator
# ═════════════════════════════════════════════════════════════
MODE = "game"


def apply_mode(mode: str) -> None:
    """Swap the module-level tokens so all newly-created widgets pick the
    palette for the requested mode. Followed by an app rebuild."""
    global MODE
    if mode not in ("game", "clean"):
        raise ValueError(f"unknown theme mode: {mode}")
    MODE = mode

    palette = _GAME_TOKENS if mode == "game" else _CLEAN_TOKENS
    g = globals()
    for k, v in palette.items():
        g[k] = v

    # Rebuild font tuples that depend on FONT_DISPLAY / FONT_HEBREW
    fd, fh = g["FONT_DISPLAY"], g["FONT_HEBREW"]
    g["FONT_LOGO"]        = (fd, 16, "bold")
    g["FONT_PAGE_TITLE"]  = (fd, 30, "bold")
    g["FONT_SECTION"]     = (fh, 16, "bold")
    g["FONT_CARD_TITLE"]  = (fh, 15, "bold")
    g["FONT_CARD_EN"]     = (fd, 12, "bold")
    g["FONT_CARD_SUB"]    = (fh, 11)
    g["FONT_NAV"]         = (fh, 14)
    g["FONT_NAV_ACTIVE"]  = (fh, 14, "bold")
    g["FONT_BODY"]        = (fh, 12)
    g["FONT_BODY_BOLD"]   = (fh, 12, "bold")
    g["FONT_BUTTON"]      = (fh, 12, "bold")
    g["FONT_STATUS"]      = (fh, 11, "bold")
    g["FONT_FOOTER"]      = (fh, 10)
    g["FONT_TICKER"]      = (fh, 11)
    g["FONT_CHIP"]        = (fd, 10, "bold")
    g["FONT_KICKER"]      = (fd, 9, "bold")


# Initialize at import time so first widget construction has tokens ready.
apply_mode("game")
