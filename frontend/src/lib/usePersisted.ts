// A useState whose value is remembered in localStorage, so a choice (sort order,
// grid/list view, …) survives leaving a view and coming back (the component
// remounts on every nav, which resets a plain useState).
import { useState } from "react";

export function usePersisted<T extends string>(key: string, initial: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const s = localStorage.getItem(key);
      return (s as T) || initial;
    } catch {
      return initial;
    }
  });
  const set = (v: T) => {
    setValue(v);
    try { localStorage.setItem(key, v); } catch { /* ignore */ }
  };
  return [value, set];
}
