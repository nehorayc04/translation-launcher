// Friendly empty-state - an illustrative icon bubble + title + hint +
// optional CTA. Used where a list/section has no content yet.
import type { ReactNode } from "react";

interface Props {
  icon?: ReactNode;        // defaults to a sparkle
  title: string;
  hint?: string;
  action?: { label: string; onClick: () => void };
  accent?: string;
}

export default function EmptyState({ icon, title, hint, action, accent = "#00ffe0" }: Props) {
  return (
    <div className="flex flex-col items-center text-center py-16 px-6 animate-fade-in">
      <div className="relative mb-5">
        <div className="absolute inset-0 rounded-full blur-2xl opacity-50"
             style={{ background: `${accent}33` }} aria-hidden />
        <div className="relative w-20 h-20 rounded-2xl grid place-items-center ring-1"
             style={{ background: `${accent}12`, color: accent, ["--tw-ring-color" as string]: `${accent}40` }}>
          {icon ?? (
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M12 3l1.9 4.6L18.5 9l-4.6 1.4L12 15l-1.9-4.6L5.5 9l4.6-1.4L12 3z" />
              <path d="M19 14l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8.8-2z" />
            </svg>
          )}
        </div>
      </div>
      <h3 className="text-white font-bold text-lg mb-1.5">{title}</h3>
      {hint && <p className="text-slate-400 text-sm max-w-sm leading-relaxed">{hint}</p>}
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className="mt-5 px-5 py-2.5 rounded-xl font-bold text-brand-ink transition hover:brightness-110
                     shadow-[0_10px_24px_-8px_rgba(0,0,0,0.6)]"
          style={{ background: accent }}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
