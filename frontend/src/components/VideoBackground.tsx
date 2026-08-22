// Static background - a single pre-extracted frame from the old looping clip
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
// The poster image was REMOVED (user request): the app background is now a
// soft, gentle AMBIENT colour driven by the "צבע אווירה" Appearance setting
// (the .accent-bg layer reads --accent / ambient-rainbow). Here we only paint
// a calm dark base for that colour to glow over - zero decode/composite cost.
export default function VideoBackground() {
  return (
    <div
      className="fixed inset-0 pointer-events-none"
      style={{
        zIndex: 0,
        background:
          "radial-gradient(120% 100% at 50% -10%, #0c0c20 0%, #070714 55%, #050510 100%)",
      }}
      aria-hidden
    />
  );
}
