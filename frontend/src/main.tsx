import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { safeReportCrash } from './lib/eel'
import { initDesignOverrides } from './designer/applyOverrides'
import { logGpuOnce } from './lib/gpuInfo'

// Global crash capture — uncaught errors + unhandled promise rejections that
// escape React's ErrorBoundary. Reported (opt-in gated, PII-scrubbed) so we
// see crashes that happen outside the render tree (event handlers, async).
window.addEventListener('error', (e) => {
  const err = e.error as Error | undefined
  void safeReportCrash(
    err?.name || 'WindowError',
    err?.message || e.message || 'window error',
    (err?.stack || '').slice(0, 4000),
    'window.onerror',
  )
})
window.addEventListener('unhandledrejection', (e) => {
  const r = (e as PromiseRejectionEvent).reason
  const err = r instanceof Error ? r : undefined
  void safeReportCrash(
    err?.name || 'UnhandledRejection',
    err?.message || String(r),
    (err?.stack || '').slice(0, 4000),
    'unhandledrejection',
  )
})

// Native-desktop hardening — block the default Chromium right-click menu
// everywhere except inside editable fields where users genuinely need it
// (cut/copy/paste). Runs once on module load so it covers the entire app.
const isEditable = (t: EventTarget | null): boolean => {
  if (!(t instanceof HTMLElement)) return false
  const tag = t.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || t.isContentEditable
}
window.addEventListener('contextmenu', (e) => {
  if (!isEditable(e.target)) e.preventDefault()
})
// Also kill drag-start for images / links (extra belt-and-suspenders on top
// of the CSS rule, since some elements don't honor -webkit-user-drag).
window.addEventListener('dragstart', (e) => {
  if (!isEditable(e.target)) e.preventDefault()
})

// Apply a saved launcher-designer design (no-op until design-overrides.json
// is filled by an export from the designer tool).
initDesignOverrides()

// Probe the real GPU/renderer ONCE and write it to launcher.log — the decisive
// "is GPU acceleration actually on?" signal for performance diagnosis.
logGpuOnce()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
