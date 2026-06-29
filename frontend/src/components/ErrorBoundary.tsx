// Last-resort safety net so a single component crash doesn't leave the
// launcher with a black window and no recovery path. Catches any error
// thrown during render or in a lifecycle method below this boundary
// and surfaces it to the user with a "reload" button.
import { Component, type ErrorInfo, type ReactNode } from "react";
import { safeReportCrash } from "../lib/eel";

interface Props { children: ReactNode }
interface State { error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surface to the eel console too, so it lands in any log file the
    // user is willing to share with us. We don't want to silently
    // swallow the stack — that's how the v1.0.5 black-screen happened.
    console.error("[ErrorBoundary] caught", error, info.componentStack);
    // Report to the dev (opt-in gated + PII-scrubbed on the Python side).
    void safeReportCrash(
      error.name || "FrontendError",
      error.message || String(error),
      (info.componentStack || "").slice(0, 4000),
      "react-error-boundary",
    );
  }

  reset = () => {
    this.setState({ error: null });
    // Hard reload — clears any half-mounted state from the crashed
    // subtree. The bridged Python process keeps running.
    try { window.location.reload(); } catch { /* no-op */ }
  };

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div
        dir="rtl"
        className="h-screen w-screen grid place-items-center p-8"
        style={{ background: "#050510", color: "#e2e8f0" }}
      >
        <div className="max-w-lg text-center space-y-4">
          <div className="text-5xl">⚠️</div>
          <h1 className="text-white text-2xl font-bold">משהו התקלקל</h1>
          <p className="text-slate-400 text-sm">
            התוכנה נתקלה בשגיאה לא צפויה. נסה לטעון מחדש —
            הנתונים שלך לא נפגעו.
          </p>
          <pre
            dir="ltr"
            className="text-[11px] text-rose-300/90 bg-rose-500/10 border border-rose-500/30
                       rounded-lg p-3 text-left overflow-auto max-h-48 font-mono whitespace-pre-wrap"
          >
            {this.state.error.message}
          </pre>
          <button
            type="button"
            onClick={this.reset}
            className="px-5 py-2.5 rounded-xl bg-[#00ffe0]/15 border border-[#00ffe0]/40
                       text-[#00ffe0] hover:bg-[#00ffe0]/25 text-sm font-bold transition"
          >
            טען מחדש
          </button>
        </div>
      </div>
    );
  }
}
