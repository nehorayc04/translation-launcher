// Per-game accent context. The selected game "paints the environment":
// the fixed .accent-bg layer (index.css) reads the --accent CSS var off
// :root, and any component can call useSetAccent() to recolor the whole app
// background to the current game's theme color. Setting null restores the
// neutral brand default.
import {
  createContext, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from "react";
import { getAccent, getAccent2 } from "./themePrefs";

// The neutral default tracks the user's Appearance pref (themePrefs), falling
// back to brand cyan.
const DEFAULT_ACCENT = getAccent();

interface AccentCtx {
  accent: string;                       // current resolved accent (always a color)
  setAccent: (c: string | null) => void; // null → restore default
}

const Ctx = createContext<AccentCtx>({ accent: DEFAULT_ACCENT, setAccent: () => {} });

export function AccentProvider({ children }: { children: ReactNode }) {
  const [accent, setAccentState] = useState<string>(DEFAULT_ACCENT);
  // Secondary colour for the two-tone ambient wash. A per-GAME accent is always
  // single (both = the game colour); only the user's default can be two-tone.
  const [accent2, setAccent2State] = useState<string>(getAccent2());

  // null restores the user's CURRENT neutral pref (re-read live so a change in
  // Appearance settings takes effect immediately on the next close); a color
  // paints both tones the same (a game's single accent).
  const setAccent = (c: string | null) => {
    if (c) { setAccentState(c); setAccent2State(c); }
    else { setAccentState(getAccent()); setAccent2State(getAccent2()); }
  };

  // Push the resolved colors onto :root so the plain-CSS .accent-bg layer
  // (and anything else that wants `var(--accent)`) tracks them live.
  useEffect(() => {
    document.documentElement.style.setProperty("--accent", accent);
    document.documentElement.style.setProperty("--accent2", accent2);
  }, [accent, accent2]);

  const value = useMemo(() => ({ accent, setAccent }), [accent]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAccent(): string {
  return useContext(Ctx).accent;
}

/** Set the app-wide accent while a component is mounted; restore the
 *  default on unmount. Pass a color (e.g. accentFor(theme_key)). */
export function useSetAccent(color: string | null | undefined) {
  const { setAccent } = useContext(Ctx);
  useEffect(() => {
    setAccent(color ?? null);
    return () => setAccent(null);
  }, [color, setAccent]);
}

/** Imperative setter (for hover handlers etc.). */
export function useAccentSetter(): (c: string | null) => void {
  return useContext(Ctx).setAccent;
}
