import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

export interface SiteConfig {
  hero?:     { titleHe?: string; taglineHe?: string; accent?: string };
  sections?: { visible?: Record<string, boolean>; order?: string[] };
  theme?:    { primary?: string; secondary?: string; fontDisplay?: string; fontBody?: string };
  faq?:      Array<{ q: string; a: string }>;
  footer?:   { textHe?: string };
  customCss?: string;
}

const CONFIG_URL = 'https://hebrew-translation-hub.vercel.app/api/config';

const Ctx = createContext<SiteConfig | null>(null);

export function SiteConfigProvider({ children }: { children: ReactNode }) {
  const [cfg, setCfg] = useState<SiteConfig | null>(null);

  useEffect(() => {
    let alive = true;
    const fetchOnce = () =>
      fetch(CONFIG_URL)
        .then((r) => r.json())
        .then((j) => {
          if (alive) setCfg(j?.config ?? {});
        })
        .catch(() => { if (alive) setCfg({}); });
    fetchOnce();
    const id = window.setInterval(fetchOnce, 30_000);
    return () => { alive = false; window.clearInterval(id); };
  }, []);

  useEffect(() => {
    const css = cfg?.customCss ?? '';
    let el = document.getElementById('site-custom-css') as HTMLStyleElement | null;
    if (!css) { el?.remove(); return; }
    if (!el) {
      el = document.createElement('style');
      el.id = 'site-custom-css';
      document.head.appendChild(el);
    }
    el.textContent = css;
  }, [cfg?.customCss]);

  const value = useMemo(() => cfg ?? {}, [cfg]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSiteConfig(): SiteConfig {
  return useContext(Ctx) ?? {};
}
