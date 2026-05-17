// Grid view with 3 sections: with mod / installed-no-mod / not installed.
// Refresh buttons for quick + deep scan.
import type { Game } from "../lib/types";
import GameCard from "../components/GameCard";
import { useMemo, useState } from "react";

interface Props {
  games: Game[];
  onOpenGame:  (g: Game) => void;
  onScanDeep:  () => Promise<void>;
  /** Bumped by App's sidebar refresh — forwarded to in-progress
   *  GameCards so their live progress bars re-pull. */
  refreshNonce?: number;
}

export default function LibraryView({ games, onOpenGame, onScanDeep, refreshNonce }: Props) {
  const [busy, setBusy] = useState<"deep" | null>(null);

  const sections = useMemo(() => {
    // Strict mod states (post-refactor): ACTIVE / DISABLED / NOT_INSTALLED /
    // NOT_AVAILABLE / UNKNOWN. Everything that is installed but doesn't have
    // an ACTIVE or DISABLED mod belongs in the "no mod" bucket — including
    // NOT_AVAILABLE titles (no package authored yet) and NOT_INSTALLED ones
    // (package exists but not deployed). Otherwise those rows fall through
    // every section and silently disappear from the grid.
    const withMod   = games.filter((g) => g.is_installed && g.mod_state === "ACTIVE");
    const withModD  = games.filter((g) => g.is_installed && g.mod_state === "DISABLED");
    const installed = games.filter((g) =>
      g.is_installed && g.mod_state !== "ACTIVE" && g.mod_state !== "DISABLED"
    );
    const missing   = games.filter((g) => !g.is_installed);
    return [
      { key: "mod",       title: "מותקנים — תרגום פעיל",   items: withMod,   accent: "#22c55e" },
      { key: "moddis",    title: "מותקנים — תרגום מושבת",  items: withModD,  accent: "#f59e0b" },
      { key: "installed", title: "מותקנים ללא תרגום",      items: installed, accent: "#a0a7b3" },
      { key: "missing",   title: "לא נמצאו במחשב",         items: missing,   accent: "#5a627a" },
    ].filter((s) => s.items.length > 0);
  }, [games]);

  const runDeep = async () => {
    setBusy("deep");
    try { await onScanDeep(); } finally { setBusy(null); }
  };

  return (
    <div className="h-full overflow-y-auto px-8 py-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <button
          disabled={busy !== null}
          onClick={runDeep}
          className="px-5 py-2.5 rounded-xl bg-brand-yellow hover:bg-yellow-300
                     text-brand-ink text-sm font-bold disabled:opacity-50 transition
                     shadow-[0_6px_15px_-6px_rgba(255,247,0,0.5)]
                     flex items-center gap-2"
        >
          {busy === "deep" ? (
            <>
              <span className="w-4 h-4 border-2 border-brand-ink border-t-transparent
                               rounded-full animate-spin" />
              סורק את כל הכוננים…
            </>
          ) : (
            "סריקת כוננים מלאה"
          )}
        </button>
        <h1 className="text-3xl font-extrabold text-white">ספריית המשחקים</h1>
      </div>

      {/* Sections */}
      {sections.length === 0 && (
        <div className="text-center text-slate-400 py-20">
          לא נמצאו משחקים. נסה סריקה עמוקה כדי לסרוק את כל הכוננים.
        </div>
      )}

      {sections.map((sec) => (
        <section key={sec.key} className="mb-10">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-slate-400 text-sm">{sec.items.length}</span>
            <h2 className="text-xl font-bold text-white">{sec.title}</h2>
            <span
              className="h-[2px] flex-1 rounded-full opacity-30"
              style={{ background: `linear-gradient(to left, ${sec.accent}, transparent)` }}
            />
          </div>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-5">
            {sec.items.map((g) => (
              <div key={g.id} className="flex justify-center">
                <GameCard game={g} onClick={onOpenGame} refreshNonce={refreshNonce} />
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
