// Game payload — mirrors `main_eel._game_payload()`.
// Fields come straight from CatalogGame dataclass + install/mod enrichment.
export type Availability = "available" | "in-progress" | "coming-soon" | "planned";
export type ModState     = "ACTIVE" | "DISABLED" | "NOT_INSTALLED" | "NOT_AVAILABLE" | "UNKNOWN";

export interface Game {
  id: string;
  titleEn: string;
  titleHe: string;
  version: string;
  theme_key: string;
  availability: Availability;
  tagline: string;
  description: string;
  progress: number | null;
  install_path: string | null;
  is_installed: boolean;
  has_mod_support: boolean;
  mod_state: ModState;
  /** Pinned to the home "תרגומים מובילים" row by the admin panel. */
  featured?: boolean;
  /** Catalog-level sort order, lower = earlier. Used to order featured games. */
  sortOrder?: number;
  /** Admin-managed cover URL from the catalog (cover_url in DB).
   *  Preferred over the bundled /covers/<id>.jpg fallback so that
   *  newly-added games (whose art was never shipped with the launcher)
   *  still render their cover instead of a broken-image icon. */
  cover?: string | null;
}

export interface ScanResult {
  games: Game[];
  found: number;
}

export interface OpResult {
  ok: boolean;
  error?: string;
  state?: ModState;
  count?: number;
  exe?: string;
}
