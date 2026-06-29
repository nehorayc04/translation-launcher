// Per-game accent context. The selected game "paints the environment":
// the fixed .accent-bg layer (index.css) reads the --accent CSS var off
// :root, and any component can call useSetAccent() to recolor the whole app
// background to the current game's theme color. Setting null restores the
// neutral brand default.
import {
  createContext, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from "react";
import { getAccent } from "./themePrefs";

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

  // null restores the user's CURRENT neutral pref (re-read live so a change in
  // Appearance settings takes effect immediately on the next close).
  const setAccent = (c: string | null) => setAccentState(c || getAccent());

  // Push the resolved color onto :root so the plain-CSS .accent-bg layer
  // (and anything else that wants `var(--accent)`) tracks it live.
  useEffect(() => {
    document.documentElement.style.setProperty("--accent", accent);
  }, [accent]);

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
