// Personal Area — mirrors the website's /profile so a user sees the
// same identity, purchases and votes whether they're on the launcher
// or in a browser. Both surfaces hit the same Supabase backend; we
// fetch through the Python bridge (auth_get_my_*) which forwards the
// stored access token to PostgREST. RLS limits everything to the
// caller, so no leakage between users.
//
// On mount + on every nav-into we run a fresh fetch (no in-memory
// cache) so an admin who just edits their profile in the browser sees
// the change here within ~1s.
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type MyPurchase } from "../lib/eel";
import { useLauncherAuth } from "../lib/useLauncherAuth";
import { resolveCoverUrl } from "../lib/coverUrl";

interface Props {
  /** Bumped by parent on the global "refresh from server" click so
   *  the personal area also pulls fresh data on demand. */
  refreshNonce: number;
  /** Routes back to home — wired by the parent App. */
  onBack:       () => void;
  /** Routes the user to the website's /profile in their default browser
   *  for the heavier flows (MFA, password change, account deletion) we
   *  intentionally don't replicate inside the launcher. */
  webProfileUrl: string;
}

export default function PersonalAreaView({
  refreshNonce, onBack, webProfileUrl,
}: Props) {
  const { user, signedIn, loading: authLoading, signOut, refresh: refreshAuth } = useLauncherAuth();

  const [purchases, setPurchases] = useState<MyPurchase[] | null>(null);
  const [votes,     setVotes]     = useState<string[] | null>(null);
  const [pulling,   setPulling]   = useState(false);

  const pull = useCallback(async () => {
    if (!signedIn) {
      setPurchases([]);
      setVotes([]);
      return;
    }
    setPulling(true);
    try {
      // Refresh the cached identity first so a name/avatar edit done
      // in the browser propagates immediately. Failures here are
      // non-fatal — the purchases/votes calls handle auth themselves.
      await refreshAuth();
      const [p, v] = await Promise.all([
        api.authGetMyPurchases().catch(() => []),
        api.authGetMyVotes().catch(() => []),
      ]);
      setPurchases(p);
      setVotes(v);
    } finally {
      setPulling(false);
    }
  }, [signedIn, refreshAuth]);

  // Fresh fetch on mount AND every time the parent bumps the nonce.
  // Combined effect: any "refresh from server" click pulls the
  // personal area too.
  useEffect(() => { void pull(); }, [pull, refreshNonce]);

  if (authLoading) {
    return (
      <div className="h-full grid place-items-center">
        <div className="w-10 h-10 border-2 border-brand-yellow border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!signedIn) {
    return (
      <div className="h-full grid place-items-center p-10" dir="rtl">
        <div className="max-w-md text-center space-y-3">
          <div className="text-5xl">🔐</div>
          <h2 className="text-white text-xl font-bold">צריך להיכנס תחילה</h2>
          <p className="text-slate-400 text-sm">
            כדי לראות את האזור האישי שלך — רכישות, הצבעות ופרטים אישיים —
            התחבר דרך הסרגל בצד.
          </p>
          <button
            type="button"
            onClick={onBack}
            className="px-4 py-2 rounded-xl bg-white/5 border border-white/10
                       text-slate-300 hover:bg-white/10 text-xs font-semibold transition"
          >
            חזרה לדף הבית
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto" dir="rtl">
      <div className="px-6 sm:px-8 py-6 max-w-5xl mx-auto space-y-6">
        <IdentityCard
          user={user}
          purchasesCount={purchases?.length ?? 0}
          votesCount={votes?.length ?? 0}
          pulling={pulling}
          onSignOut={signOut}
          onOpenWebProfile={() => window.open(webProfileUrl, '_blank', 'noopener,noreferrer')}
          onRefresh={pull}
        />

        <PurchasesSection rows={purchases} />

        <VotesSection ids={votes} />
      </div>
    </div>
  );
}

// ── identity card ────────────────────────────────────────────────
function IdentityCard({
  user, purchasesCount, votesCount, pulling, onSignOut, onOpenWebProfile, onRefresh,
}: {
  user:             { fullName?: string; email?: string; avatarUrl?: string; provider?: string } | null;
  purchasesCount:   number;
  votesCount:       number;
  pulling:          boolean;
  onSignOut:        () => void | Promise<void>;
  onOpenWebProfile: () => void;
  onRefresh:        () => void | Promise<void>;
}) {
  const displayName = user?.fullName?.trim() || user?.email?.split('@')[0] || 'משתמש';
  const initials = useMemo(() => displayName.slice(0, 2).toUpperCase(), [displayName]);

  return (
    <section
      className="rounded-3xl border border-white/10 backdrop-blur-2xl p-5 md:p-6
                 flex flex-col md:flex-row items-center md:items-stretch gap-5"
      style={{
        background:
          'radial-gradient(circle at 80% 0%, rgba(0,255,224,0.10), transparent 60%),' +
          'radial-gradient(circle at 20% 100%, rgba(255,247,0,0.05), transparent 65%),' +
          'rgba(7, 7, 16, 0.55)',
        boxShadow: '0 30px 60px -25px rgba(0,0,0,0.7)',
      }}
    >
      <div className="shrink-0">
        {user?.avatarUrl ? (
          <img
            src={user.avatarUrl}
            alt={displayName}
            referrerPolicy="no-referrer"
            className="w-20 h-20 rounded-2xl object-cover"
            style={{ boxShadow: '0 8px 24px -8px rgba(0,255,224,0.45)' }}
          />
        ) : (
          <div
            className="w-20 h-20 rounded-2xl grid place-items-center font-extrabold text-2xl"
            style={{
              background: 'linear-gradient(135deg, #00ffe0, #7c3aed)',
              color: '#0a0a14',
              boxShadow: '0 8px 24px -8px rgba(0,255,224,0.45)',
            }}
            aria-hidden
          >
            {initials}
          </div>
        )}
      </div>

      <div className="flex-1 text-right min-w-0">
        <div className="text-[11px] tracking-[0.3em] text-[#00ffe0]/80 font-display">
          PERSONAL AREA
        </div>
        <h1 className="text-2xl md:text-3xl font-bold text-white truncate">{displayName}</h1>
        <div className="text-slate-400 text-xs mt-0.5" dir="ltr">{user?.email}</div>
        <div className="text-[10px] text-slate-500 mt-0.5 uppercase tracking-wider">
          {user?.provider ?? '—'}
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 mt-3 text-xs">
          <Stat label="משחקים שנרכשו" value={purchasesCount} />
          <Stat label="הצבעות" value={votesCount} />
        </div>
      </div>

      <div className="flex flex-row md:flex-col gap-2 shrink-0 md:items-stretch">
        <button
          type="button"
          onClick={onRefresh}
          disabled={pulling}
          title="משוך מחדש מהשרת"
          className="px-3 py-2 rounded-xl text-xs font-semibold transition
                     bg-white/5 border border-white/10 text-slate-200
                     hover:bg-white/10 disabled:opacity-50 disabled:cursor-wait whitespace-nowrap"
        >
          {pulling ? 'מסנכרן…' : 'סנכרן עכשיו'}
        </button>
        <button
          type="button"
          onClick={onOpenWebProfile}
          className="px-3 py-2 rounded-xl text-xs font-semibold transition
                     bg-[#00ffe0]/10 border border-[#00ffe0]/40 text-[#00ffe0]
                     hover:bg-[#00ffe0]/20 whitespace-nowrap"
        >
          עריכה מורחבת באתר ↗
        </button>
        <button
          type="button"
          onClick={onSignOut}
          className="px-3 py-2 rounded-xl text-xs font-semibold transition
                     bg-rose-500/10 border border-rose-500/30 text-rose-200
                     hover:bg-rose-500/20 whitespace-nowrap"
        >
          התנתק
        </button>
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="text-white font-bold text-base">{value}</span>
      <span className="text-slate-400">{label}</span>
    </div>
  );
}

// ── purchases ────────────────────────────────────────────────────
function PurchasesSection({ rows }: { rows: MyPurchase[] | null }) {
  if (rows === null) return <SectionSkeleton title="המשחקים שלי" />;

  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-white font-bold text-lg">המשחקים שלי</h2>
        <span className="text-xs text-slate-500">{rows.length} פריטים</span>
      </div>

      {rows.length === 0 ? (
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 text-center">
          <div className="text-3xl mb-2">📦</div>
          <p className="text-slate-300 text-sm">עדיין לא רכשת תרגומים.</p>
          <p className="text-slate-500 text-xs mt-1">
            עיין בספרייה וקנה את התרגום הראשון — הוא יופיע כאן מיד.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {rows.map((row) => <PurchaseCard key={String(row.id)} row={row} />)}
        </div>
      )}
    </section>
  );
}

function PurchaseCard({ row }: { row: MyPurchase }) {
  const g = row.games;
  const title = g?.title_he || g?.title_en || row.game_id;
  // Same resolver the GameCard uses → bare filename → /covers/<file>.
  const coverSrc = g ? resolveCoverUrl(g.cover_url, g.id) : '/covers/unknown.jpg';
  const purchasedAt = useMemo(() => {
    try {
      return new Date(row.created_at).toLocaleDateString('he-IL', {
        day: '2-digit', month: '2-digit', year: 'numeric',
      });
    } catch {
      return '';
    }
  }, [row.created_at]);

  return (
    <article
      className="group relative rounded-xl overflow-hidden border border-white/10
                 bg-slate-900/40 transition hover:border-white/25"
      style={{ aspectRatio: '2/3' }}
    >
      <img
        src={coverSrc}
        alt={title}
        loading="lazy"
        className="absolute inset-0 w-full h-full object-cover
                   group-hover:scale-[1.03] transition-transform duration-300"
        onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
      />
      <div className="absolute inset-x-0 bottom-0 p-3
                      bg-gradient-to-t from-black/95 via-black/60 to-transparent" dir="rtl">
        <div className="text-white text-sm font-bold leading-tight line-clamp-2">{title}</div>
        {g?.version_label && (
          <div className="text-[10px] text-slate-300 mt-0.5">{g.version_label}</div>
        )}
        {purchasedAt && (
          <div className="text-[10px] text-emerald-300 mt-1.5 font-mono" dir="ltr">
            ✓ {purchasedAt}
          </div>
        )}
      </div>
    </article>
  );
}

// ── votes ────────────────────────────────────────────────────────
function VotesSection({ ids }: { ids: string[] | null }) {
  if (ids === null) return <SectionSkeleton title="ההצבעות שלי" />;

  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-white font-bold text-lg">ההצבעות שלי</h2>
        <span className="text-xs text-slate-500">{ids.length} הצבעות</span>
      </div>

      {ids.length === 0 ? (
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6 text-center">
          <p className="text-slate-300 text-sm">עוד לא הצבעת לאף משחק.</p>
          <p className="text-slate-500 text-xs mt-1">
            הצבע באתר תחת "הצבעה לפרויקט הבא" כדי לעזור לבחור את התרגום הבא.
          </p>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {ids.map((id) => (
            <span
              key={id}
              className="px-3 py-1.5 rounded-full text-xs font-mono
                         bg-[#7c3aed]/10 border border-[#7c3aed]/30 text-[#c4b5fd]"
              dir="ltr"
            >
              {id}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

// ── tiny shared skeleton ─────────────────────────────────────────
function SectionSkeleton({ title }: { title: string }) {
  return (
    <section className="space-y-3">
      <h2 className="text-white font-bold text-lg">{title}</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="rounded-xl bg-white/[0.04] animate-pulse" style={{ aspectRatio: '2/3' }} />
        ))}
      </div>
    </section>
  );
}
