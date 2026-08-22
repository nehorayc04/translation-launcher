/* The /preview page — mounts the REAL launcher App (../frontend/src/App)
 * with the REAL launcher CSS, so it looks 1:1. The Vite `designer-mock-eel`
 * plugin swaps the eel backend module for ../mock/eel (sample data), so the
 * app renders fully without the Qt/Eel runtime. The designer's main page
 * embeds this via an <iframe> and inspects/edits it (same-origin). */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fe/index.css";
import App from "@fe/App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
