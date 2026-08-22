// A plugin's catalog name doubles as its marketing line ("מחשוב קהילתי - תרמו
// כוח תרגום"). That reads fine in the manager card and is far too long for a
// 230px sidebar row or a page title, where it gets clipped mid-word.
//
// The catalog convention is `<שם> - <סלוגן>`, so the part before the dash IS
// the name. Shared by the sidebar row and the plugin page so the two can never
// disagree about what a plugin is called.
const SEP = /\s+[-–—]\s+/;

export function shortName(name?: string | null): string {
  const n = (name ?? "").trim();
  if (!n) return "תוסף";
  const head = n.split(SEP)[0].trim();
  return head || n;
}
