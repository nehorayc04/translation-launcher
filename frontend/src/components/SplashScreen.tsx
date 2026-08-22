// Short branded launch splash - an animated logo + title shown once on boot.
//
// It stays up until the first screen's images are actually READY (preloaded into
// cache by App), so the app never "opens then fills in" a few seconds later - and
// because the images come from the browser/QtWebEngine disk cache, the SECOND
// launch dismisses almost instantly. A hard `maxMs` cap guarantees it never hangs
// even if the network is down. Skips entirely when the user disabled animations.
import { useEffect, useRef, useState } from "react";
import { getAnims } from "../lib/themePrefs";

export default function SplashScreen({
  onDone, ready = true, minMs = 650, maxMs = 6000,
}: {
  onDone: () => void;
  /** Flip true once the first screen's images are cached/loaded. */
  ready?: boolean;
  /** Never dismiss before this (so a cached boot doesn't just flash). */
  minMs?: number;
  /** Hard cap so a dead network can't strand the splash. */
  maxMs?: number;
}) {
  const [leaving, setLeaving] = useState(false);
  const animsOn = getAnims();
  const start = useRef(Date.now());
  const finished = useRef(false);

  // Dismiss when (ready AND we've shown for at least minMs), OR at maxMs.
  useEffect(() => {
    if (!animsOn) { onDone(); return; }
    let raf = 0;
    const leave = () => {
      if (finished.current) return;
      finished.current = true;
      setLeaving(true);
      setTimeout(onDone, 450);            // let the fade play, then unmount
    };
    const tick = () => {
      const elapsed = Date.now() - start.current;
      if (elapsed >= maxMs) return leave();
      if (ready && elapsed >= minMs) return leave();
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [animsOn, ready, minMs, maxMs, onDone]);

  if (!animsOn) return null;

  return (
    <div
      className="fixed inset-0 z-[200] grid place-items-center transition-opacity duration-[450ms]"
      style={{ background: "#050510", opacity: leaving ? 0 : 1, pointerEvents: leaving ? "none" : "auto" }}
    >
      {/* ambient glows in the icon's own colors (blue + red) */}
      <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-[40rem] h-72 rounded-full bg-[#4f8bff]/12 blur-3xl animate-glow-pulse" aria-hidden />
      <div className="absolute -bottom-24 right-1/4 w-96 h-96 rounded-full bg-[#ff3b7b]/12 blur-3xl" aria-hidden />

      <div className="relative flex flex-col items-center text-center animate-scale-in">
        {/* Neon avatar ring */}
        {/* bg matches the icon's own black background so any circle-edge the
            square image doesn't reach blends in seamlessly (no square frame). */}
        {/* No frame - the logo floats with its own neon glow (icon's blue+red). */}
        <div className="relative mb-7 animate-float"
             style={{ filter: "drop-shadow(0 0 20px rgba(79,139,255,0.55)) drop-shadow(0 0 34px rgba(255,59,123,0.35))" }}>
          {/* fetchPriority/decoding pair with the <link rel="preload"> in
              index.html so the logo paints WITH the text, not a beat after it. */}
          <img src="./app-logo.png" alt="" className="w-32 h-32 object-contain"
               fetchPriority="high" decoding="sync" draggable={false}
               onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }} />
        </div>
        <div className="font-display text-[13px] tracking-[0.34em] mb-2.5" style={{ color: "#9db4ff" }}>
          P R O J E C T &nbsp; T R A N S L A T I O N
        </div>
        <h1 className="text-4xl font-extrabold mb-7">
          <span style={{
            backgroundImage: "linear-gradient(90deg,#4f8bff 0%,#a855f7 50%,#ff3b7b 100%)",
            WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent",
          }}>מנהל התרגומים</span>
        </h1>
        {/* loading shimmer bar, in the icon's gradient */}
        <div className="w-56 h-1.5 rounded-full overflow-hidden bg-white/10 relative">
          <div className="absolute inset-y-0 -left-1/3 w-1/3 rounded-full"
               style={{ background: "linear-gradient(90deg,#4f8bff,#a855f7,#ff3b7b)", animation: "splash-bar 1.4s ease-in-out infinite" }} />
        </div>
      </div>

      <style>{`@keyframes splash-bar { 0% { left: -33%; } 100% { left: 100%; } }`}</style>
    </div>
  );
}
