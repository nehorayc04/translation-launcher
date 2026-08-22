// Release-maturity pill - אלפא / בטא / RC. Stable shows nothing. Mirrors the
// website's StageBadge. Resolves the stage from the explicit `releaseStage`
// field, falling back to the version's own `-beta`-style suffix.
import { resolveStage, STAGE_BADGE } from "../lib/version";

export function StageBadge({
  releaseStage,
  version,
}: {
  releaseStage?: string | null;
  version?: string | null;
}) {
  const stage = resolveStage(releaseStage, version);
  const b = STAGE_BADGE[stage];
  if (!b) return null; // stable → no badge

  return (
    <span
      className="inline-flex items-center rounded-full border px-1.5 py-0.5 text-[9px] font-bold whitespace-nowrap"
      style={{ color: b.fg, background: b.bg, borderColor: b.border }}
      title={`גרסה מוקדמת - ${b.label}`}
    >
      {b.label}
    </span>
  );
}
