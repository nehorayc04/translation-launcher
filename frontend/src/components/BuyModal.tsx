// In-launcher PayPal Smart Buttons modal. Adapted from the website's
// BuyButton.tsx but rendered as a centered modal in the same window
// (no popup, no system browser). Uses the same /api/paypal create-order
// + capture-order endpoints; the Supabase access token comes from the
// Python auth subsystem via the bridge.
//
// Env vars (build-time, baked from .env.build):
//   VITE_PAYPAL_CLIENT_ID   - required. PayPal app's public client id.
//                              Sandbox key for testing, live for prod.
//   VITE_PAYPAL_ENV         - 'sandbox' (default) | 'live'  (informational)
//   VITE_PAYPAL_CURRENCY    - default 'ILS' (Israeli new shekel)
import { useEffect, useMemo, useState } from "react";
import {
  PayPalScriptProvider,
  PayPalButtons,
  type ReactPayPalScriptOptions,
} from "@paypal/react-paypal-js";
import { api, jsLog } from "../lib/eel";
import { IconOptHdrBuyTitle, IconOptStatAmountLabel } from "./UiIcons";

const API_BASE = "https://hebrew-translation-hub.com";

interface Props {
  /** Catalog id of the game being purchased. */
  gameId:     string;
  /** Display-only - actual amount is looked up server-side. */
  gameTitle:  string;
  /** Display-only - same as above. UI hint for the price label. */
  priceCents: number;
  /** Backdrop click / X button. Fires regardless of payment outcome.
   *  Parent should unmount the modal entirely on this (conditional
   *  render `{open && <BuyModal/>}`) - far more reliable than the
   *  modal returning null on a stale prop. */
  onClose:    () => void;
  /** Fired AFTER a successful capture. Parent kicks the burst poller
   *  + the optimistic ownership flip - this modal calls onClose() at
   *  the same point so the parent doesn't even need to track buyOpen
   *  for the close path. */
  onSuccess:  () => void;
}

function formatPrice(cents: number, currency: string): string {
  const amount = cents / 100;
  const body = amount % 1 === 0 ? amount.toFixed(0) : amount.toFixed(2);
  if (currency.toUpperCase() === "ILS") return `${body} ₪`;
  if (currency.toUpperCase() === "USD") return `$${body}`;
  return `${currency.toUpperCase()} ${body}`;
}

export function BuyModal({ gameId, gameTitle, priceCents, onClose, onSuccess }: Props) {
  // The parent MOUNTS this component only when buyOpen=true and
  // UNMOUNTS it on close. So the mere fact that this component is
  // running means the modal is open. No `open` prop, no return-null
  // branch - close = unmount = guaranteed.
  const [error, setError] = useState<string | null>(null);
  const [done,  setDone]  = useState(false);

  console.log("[BuyModal] mount/render - done:", done);
  jsLog(`[BuyModal] mount/render done=${done}`);

  // Esc closes the modal - matches the rest of the launcher's modal UX.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const clientId = (import.meta.env.VITE_PAYPAL_CLIENT_ID as string | undefined) || "";
  const env      = ((import.meta.env.VITE_PAYPAL_ENV as string | undefined) || "sandbox").toLowerCase();
  const currency = (import.meta.env.VITE_PAYPAL_CURRENCY as string | undefined) || "ILS";

  const sdkOptions: ReactPayPalScriptOptions = useMemo(() => ({
    clientId,
    currency,
    intent:        "capture",
    components:    "buttons",
    "data-env":    env,
  }), [clientId, currency, env]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-[min(440px,90vw)] rounded-2xl bg-[#0f1218] border border-white/10 shadow-2xl p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-white font-bold text-lg inline-flex items-center gap-1.5"><IconOptHdrBuyTitle width={20} className="shrink-0 opacity-90" />רכישת תרגום</h2>
            <div className="text-slate-400 text-sm mt-0.5">{gameTitle}</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="סגור"
            className="text-slate-400 hover:text-white text-xl leading-none px-2"
          >
            ✕
          </button>
        </div>

        <div className="rounded-xl bg-white/[0.04] border border-white/[0.06] px-4 py-3 flex items-center justify-between">
          <span className="text-slate-300 text-sm inline-flex items-center gap-1.5"><IconOptStatAmountLabel width={18} className="shrink-0 opacity-90" />סכום לתשלום</span>
          <span className="text-brand-yellow font-bold text-xl">
            {formatPrice(priceCents, currency)}
          </span>
        </div>

        {!clientId && (
          <div className="text-amber-300/90 text-sm text-center px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30">
            PayPal טרם הוגדר - חסר <code className="font-mono">VITE_PAYPAL_CLIENT_ID</code> בבילד.
          </div>
        )}

        {clientId && !done && (
          <div className="space-y-2">
            <PayPalScriptProvider options={sdkOptions}>
              <PayPalButtons
                forceReRender={[gameId, priceCents, currency]}
                style={{ layout: "horizontal", tagline: false, height: 44 }}
                createOrder={async () => {
                  setError(null);
                  const tok = await api.authGetAccessToken();
                  if (!tok) {
                    setError("not-signed-in");
                    throw new Error("not-signed-in");
                  }
                  const r = await fetch(`${API_BASE}/api/paypal?action=create-order`, {
                    method:  "POST",
                    headers: {
                      "Content-Type": "application/json",
                      Authorization:  `Bearer ${tok}`,
                    },
                    body: JSON.stringify({ gameId }),
                  });
                  const data = await r.json().catch(() => ({}));
                  if (!r.ok || !data?.orderID) {
                    const msg = data?.error || `HTTP ${r.status}`;
                    setError(msg);
                    throw new Error(msg);
                  }
                  return data.orderID as string;
                }}
                onApprove={async (apprData) => {
                  setError(null);
                  const tok = await api.authGetAccessToken();
                  if (!tok) { setError("not-signed-in"); return; }
                  try {
                    const r = await fetch(`${API_BASE}/api/paypal?action=capture-order`, {
                      method:  "POST",
                      headers: {
                        "Content-Type": "application/json",
                        Authorization:  `Bearer ${tok}`,
                      },
                      body: JSON.stringify({ orderID: apprData.orderID }),
                    });
                    const data = await r.json().catch(() => ({}));
                    if (!r.ok || !data?.ok) {
                      setError(data?.error || `HTTP ${r.status}`);
                      return;
                    }
                    console.log("[BuyModal] capture-order OK → unmounting modal");
                    jsLog("[BuyModal] capture-order OK → unmounting");
                    setDone(true);
                    onSuccess();
                    // Conditional render in the parent means this call
                    // literally UNMOUNTS the component. The setDone/error
                    // states below this line don't render (component
                    // gone from tree).
                    onClose();
                    jsLog("[BuyModal] onClose() returned - should be unmounted now");
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
                onCancel={() => setError(null)}
                onError={(err) => {
                  console.error("[paypal SDK] onError:", err);
                  const msg =
                    err && typeof err === "object" && typeof (err as { message?: unknown }).message === "string"
                      ? (err as { message: string }).message
                      : "paypal-sdk-error";
                  setError(msg);
                }}
              />
            </PayPalScriptProvider>
          </div>
        )}

        {done && (
          <div className="text-center px-4 py-3 rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-emerald-100 text-sm font-bold">
            ✓ התשלום הושלם - טוען גישה…
          </div>
        )}

        {error && (
          <div className="text-rose-300/90 text-sm text-center px-3 py-2 rounded-lg bg-rose-500/10 border border-rose-500/30">
            תשלום נכשל: {error}
          </div>
        )}
      </div>
    </div>
  );
}
