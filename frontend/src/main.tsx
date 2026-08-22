import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { safeReportEvent } from './lib/eel'
import { initDesignOverrides } from './designer/applyOverrides'
import { logGpuOnce } from './lib/gpuInfo'

// ── ONE shell per executable ─────────────────────────────────────────────────
// "ביג-לאנץ" is a SEPARATE PROGRAM (BigLaunch.exe), not a mode of this app, so
// this root only ever renders the desktop launcher. The in-process React
// console that used to live behind a `#big` fragment was REMOVED: two consoles
// drift apart, and the second one carried a second way back to the desktop -
// and the console must have exactly one, in its own Settings.

// Global handled-error capture - uncaught errors + unhandled promise
// rejections that escape React's ErrorBoundary. The app keeps running (this is
// NOT the app crashing), so these are reported as SILENT events (anonymous,
// opt-in gated, PII-scrubbed) - stored + aggregated, no user message, no admin
// email. Only a real Python-process crash keeps its dialog + email.
window.addEventListener('error', (e) => {
  const err = e.error as Error | undefined
  safeReportEvent(
    'js_error',
    `${err?.name || 'WindowError'}: ${err?.message || e.message || 'window error'}`,
    'window.onerror',
    err?.name || 'WindowError',
    'error',
  )
})
window.addEventListener('unhandledrejection', (e) => {
  const r = (e as PromiseRejectionEvent).reason
  const err = r instanceof Error ? r : undefined
  safeReportEvent(
    'js_unhandled_rejection',
    `${err?.name || 'UnhandledRejection'}: ${err?.message || String(r)}`,
    'unhandledrejection',
    err?.name || 'UnhandledRejection',
    'error',
  )
})

// Native-desktop hardening - block the default Chromium right-click menu
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

// Smart sleep - pause all CSS animations while the window is hidden (minimized
// or sent to the system tray). The Qt webview maps window visibility to document
// visibility, so this fires on minimize + tray-hide and reverses on restore, so
// an unseen launcher costs ~0% CPU/GPU. Purely visual; no data/poller changes.
const applyAsleep = () => {
  document.documentElement.dataset.appAsleep = document.hidden ? 'true' : 'false'
}
document.addEventListener('visibilitychange', applyAsleep)
applyAsleep()

// Apply a saved launcher-designer design (no-op until design-overrides.json
// is filled by an export from the designer tool).
initDesignOverrides()

// Probe the real GPU/renderer ONCE and write it to launcher.log - the decisive
// "is GPU acceleration actually on?" signal for performance diagnosis.
logGpuOnce()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
