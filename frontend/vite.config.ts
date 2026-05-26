import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Emit relative asset paths so the built index.html works under file://
  // (QtWebEngine in the Qt shell) AS WELL AS under HTTP (Eel build + Vite
  // dev server). The default '/' resolves to the drive root under file://
  // and 404s every asset - that's the white-screen bug we just hit.
  base: './',
})
