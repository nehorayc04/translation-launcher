import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

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

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
