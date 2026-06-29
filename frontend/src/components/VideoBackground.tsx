// Static background — a single pre-extracted frame from the old looping clip
// (`bg-poster.jpg`) plus the tinted gradient overlay.
//
// The animated <video> background was REMOVED. A continuously-decoded +
// per-frame-composited full-screen video is the single most expensive thing a
// desktop web UI can paint; a still frame is visually identical at full-screen
// background scale and costs ZERO decode/composite, so the UI stays smooth
// regardless of what else uses the GPU (and regardless of whether Chromium is
// on the GPU or software path). (The component name is kept so App.tsx's import
// is unchanged.) NOTE: the launcher now runs Chromium with GPU compositing ON
// by default (see main_qt.py); a static poster is still the right call here.
const POSTER_SRC = "./bg-poster.jpg";

export default function VideoBackground() {
  return (
    <>
      {/* base fill — shows instantly before the poster decodes */}
      <div className="fixed inset-0" style={{ zIndex: 0, background: "#050510" }} aria-hidden />
      <img
        src={POSTER_SRC}
        alt=""
        aria-hidden
        decoding="async"
        className="fixed inset-0 w-full h-full object-cover pointer-events-none"
        style={{ zIndex: 0 }}
      />
      {/* tinted overlay — sits between the background and the content */}
      <div
        className="fixed inset-0 pointer-events-none
                   bg-gradient-to-br from-[#050510]/60 via-[#0a0a20]/45 to-[#1a0d40]/40"
        style={{ zIndex: 1 }}
      />
    </>
  );
}
