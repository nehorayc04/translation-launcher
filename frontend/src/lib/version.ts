// Canonical version model for the launcher UI — MIRRORS the website's
// `website/src/lib/version.ts` and the backend `main_eel.py:_parse_version`.
// Keep the three in lockstep.
//
// SemVer `MAJOR.MINOR.PATCH` + optional pre-release stage `-<stage>.<n>`
// (e.g. `1.1.0-beta.2`). Stages oldest→newest: alpha → beta → rc → stable.
// Legacy date scheme (`2026.05.22`) ranks below every semver; the `—`/`-`
// placeholder is shown as-is.

export type Stage = "alpha" | "beta" | "rc" | "stable";

const STAGE_RANK: Record<Stage, number> = { alpha: 0, beta: 1, rc: 2, stable: 3 };

const STAGE_ALIASES: Record<string, Stage> = {
  alpha: "alpha", a: "alpha", pre: "alpha",
  beta: "beta", b: "beta",
  rc: "rc", "release-candidate": "rc", releasecandidate: "rc",
  stable: "stable", final: "stable", release: "stable", "": "stable",
};

export interface ParsedVersion {
  scheme: number;
  major: number;
  minor: number;
  patch: number;
  stage: Stage;
  stageRank: number;
  pre: number;
  isDate: boolean;
  hasDigit: boolean;
  raw: string;
}

export function parseVersion(input: string | null | undefined): ParsedVersion {
  const raw = (input ?? "").trim();
  const body = raw.replace(/^v+/i, "");
  const hasDigit = /\d/.test(body);

  const dash = body.indexOf("-");
  const coreStr = dash >= 0 ? body.slice(0, dash) : body;
  const preStr = dash >= 0 ? body.slice(dash + 1) : "";

  const nums = coreStr.split(".").slice(0, 3).map((p) => {
    const d = p.replace(/\D/g, "");
    return d ? parseInt(d, 10) : 0;
  });
  const major = nums[0] ?? 0;
  const minor = nums[1] ?? 0;
  const patch = nums[2] ?? 0;
  const isDate = major >= 2000;

  let stage: Stage = "stable";
  let pre = 0;
  if (preStr) {
    const m = preStr.toLowerCase().match(/^([a-z][a-z-]*)\.?(\d+)?/);
    if (m) {
      stage = STAGE_ALIASES[m[1]] ?? "stable";
      pre = m[2] ? parseInt(m[2], 10) : 0;
    }
  }

  return {
    scheme: isDate ? 0 : 1,
    major, minor, patch,
    stage,
    stageRank: STAGE_RANK[stage],
    pre,
    isDate,
    hasDigit,
    raw,
  };
}

function sortKey(p: ParsedVersion): number[] {
  return [p.scheme, p.major, p.minor, p.patch, p.stageRank, p.pre];
}

export function compareVersions(
  a: string | null | undefined,
  b: string | null | undefined,
): number {
  const ka = sortKey(parseVersion(a));
  const kb = sortKey(parseVersion(b));
  for (let i = 0; i < ka.length; i++) {
    if (ka[i] !== kb[i]) return ka[i] < kb[i] ? -1 : 1;
  }
  return 0;
}

export function isNewer(
  candidate: string | null | undefined,
  current: string | null | undefined,
): boolean {
  return compareVersions(candidate, current) > 0;
}

export function stageOf(v: string | null | undefined): Stage {
  return parseVersion(v).stage;
}

export function formatVersion(v: string | null | undefined): string {
  const raw = (v ?? "").trim();
  if (!raw || !/\d/.test(raw)) return raw;
  return "v" + raw.replace(/^v+/i, "");
}

export const STAGE_LABEL_HE: Record<Stage, string> = {
  alpha: "אלפא",
  beta: "בטא",
  rc: "מועמד לשחרור",
  stable: "",
};

export const STAGE_BADGE: Record<
  Stage,
  { label: string; short: string; fg: string; bg: string; border: string } | null
> = {
  alpha:  { label: "אלפא", short: "α",  fg: "#ffdede", bg: "rgba(122,22,22,0.92)", border: "rgba(239,68,68,0.9)" },
  beta:   { label: "בטא",  short: "β",  fg: "#ffe9c7", bg: "rgba(120,72,12,0.92)", border: "rgba(245,158,11,0.9)" },
  rc:     { label: "RC",   short: "rc", fg: "#dff1ff", bg: "rgba(16,68,100,0.92)", border: "rgba(56,189,248,0.9)" },
  stable: null,
};

export function resolveStage(
  releaseStage: string | null | undefined,
  version: string | null | undefined,
): Stage {
  const s = (releaseStage ?? "").toLowerCase().trim();
  if (s && s in STAGE_RANK) return s as Stage;
  return stageOf(version);
}
