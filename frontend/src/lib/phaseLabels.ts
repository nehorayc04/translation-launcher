// Mirror of the website's src/lib/phaseLabels.ts. Kept in sync manually -
// the website is the canonical source of truth (the API contract lives
// there), but copying the table here is cheaper than building a shared
// npm package for one tiny dictionary.
export const PHASE_LABELS_HE: Record<string, string> = {
  extraction:  "שליפת נתונים",
  translation: "תרגום נתונים",
  packaging:   "אריזת נתונים",
  qa:          "בקרת איכות",
  deployment:  "פריסה",
  idle:        "הושלם",
};

export const PHASE_DONE_LABEL_HE: Record<string, string> = {
  extraction:  "נשלפו עד כה",
  translation: "שורות תורגמו",
  packaging:   "קבצים נארזו",
  qa:          "פריטים אומתו",
  deployment:  "פריטים נפרסו",
  idle:        "הושלם במלואו",
};

export const PHASE_REMAINING_LABEL_HE: Record<string, string> = {
  extraction:  "נותרו לשליפה",
  translation: "שורות נותרו",
  packaging:   "קבצים נותרו",
  qa:          "פריטים נותרו",
  deployment:  "פריטים נותרו",
  idle:        "-",
};

export const PHASE_RATE_LABEL_HE: Record<string, string> = {
  extraction:  "קצב שליפה / שעה",
  translation: "קצב עיבוד GPU / שעה",
  packaging:   "קצב אריזה / שעה",
  qa:          "קצב בקרה / שעה",
  deployment:  "קצב פריסה / שעה",
  idle:        "-",
};

export function resolvePhaseHeadline(
  phase:        string,
  phaseLabelHe: string | null | undefined,
): string {
  if (phaseLabelHe && phaseLabelHe.trim()) return phaseLabelHe;
  return PHASE_LABELS_HE[phase] ?? "התקדמות";
}

export function resolvePhaseDoneLabel(phase: string): string {
  return PHASE_DONE_LABEL_HE[phase] ?? "בוצעו";
}
export function resolvePhaseRemainingLabel(phase: string): string {
  return PHASE_REMAINING_LABEL_HE[phase] ?? "נותרו";
}
export function resolvePhaseRateLabel(phase: string): string {
  return PHASE_RATE_LABEL_HE[phase] ?? "קצב / שעה";
}
