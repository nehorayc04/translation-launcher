// Seamless looping background.
//
// Why two <video> elements?
//   At the loop seam Chromium's WebMediaPlayer typically introduces a
//   1-2 frame decoder reset — visible as a black flash or freeze.
//   Mounting two videos and crossfading just before the end hides the
//   seam on whichever element is currently invisible.
//
// Mechanics:
//   • Both <video>s are `loop` and play continuously, but they're started
//     OFFSET by ~duration/2 so they're never near their seam at the same
//     time. The fade just swaps opacity — neither element is seeked
//     while it's visible, which is what used to cause the harsh jump.
//   • The RAF tick watches the currently-active layer's remaining time
//     and toggles `active` once it drops below FADE_LEAD_SECONDS.
//   • The just-faded-out layer continues looping in the background; by
//     the time we crossfade back to it, it's already past its seam.
import { useEffect, useRef, useState } from "react";

const FADE_LEAD_SECONDS = 0.8;   // start crossfade this many sec before end
const FADE_MS           = 600;   // gentler fade, fully covers a ~350ms reset

export default function VideoBackground() {
  const refA = useRef<HTMLVideoElement>(null);
  const refB = useRef<HTMLVideoElement>(null);
  const [active, setActive] = useState<"A" | "B">("A");
  const lastSwapRef = useRef<number>(0);

  // Boot: start A at t=0, start B at t=duration/2 so the two layers are
  // permanently out of phase. We wait for metadata so currentTime sticks.
  useEffect(() => {
    const a = refA.current;
    const b = refB.current;
    if (!a || !b) return;

    const begin = async (el: HTMLVideoElement, offsetRatio: number) => {
      // metadata gives us duration; without it currentTime can be clamped.
      if (!Number.isFinite(el.duration) || el.duration <= 0) {
        await new Promise<void>((resolve) => {
          const done = () => { el.removeEventListener("loadedmetadata", done); resolve(); };
          el.addEventListener("loadedmetadata", done, { once: true });
        });
      }
      try {
        el.currentTime = (el.duration || 0) * offsetRatio;
      } catch { /* some browsers throw on premature seek — safe to ignore */ }
      try { await el.play(); }
      catch (err) { console.warn("[video] autoplay blocked:", err); }
    };

    begin(a, 0);
    begin(b, 0.5);
  }, []);

  // Crossfade scheduler — observes the active layer only; the inactive
  // layer just loops freely in the background.
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const cur = (active === "A" ? refA : refB).current;
      if (cur && cur.duration > 0) {
        const remaining = cur.duration - cur.currentTime;
        const now = performance.now();
        if (remaining < FADE_LEAD_SECONDS && (now - lastSwapRef.current) > 1500) {
          lastSwapRef.current = now;
          // No seek — the other layer is already mid-playback (offset by
          // duration/2 at boot). Just flip opacity.
          setActive((prev) => (prev === "A" ? "B" : "A"));
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active]);

  // Final-unmount cleanup — pause + release both <video> elements so the
  // Chromium GPU/decoder threads release immediately when the launcher
  // window closes. Without this, Chrome's --app subprocess can linger as
  // a black leftover window for several seconds after Python exits.
  useEffect(() => {
    return () => {
      [refA.current, refB.current].forEach((v) => {
        if (!v) return;
        try {
          v.pause();
          v.removeAttribute("src");
          v.load();           // forces the decoder to release
        } catch {
          /* unmount-time errors are harmless — page is going away anyway */
        }
      });
    };
  }, []);

  const layerStyle = (visible: boolean): React.CSSProperties => ({
    zIndex: 0,
    opacity: visible ? 1 : 0,
    transitionProperty: "opacity",
    transitionDuration: `${FADE_MS}ms`,
    transitionTimingFunction: "ease-in-out",
  });

  return (
    <>
      <video
        ref={refA}
        autoPlay muted playsInline loop preload="auto"
        className="fixed inset-0 w-screen h-screen object-cover"
        style={layerStyle(active === "A")}
        src="/214405.mp4"
      />
      <video
        ref={refB}
        autoPlay muted playsInline loop preload="auto"
        className="fixed inset-0 w-screen h-screen object-cover"
        style={layerStyle(active === "B")}
        src="/214405.mp4"
      />
      {/* Tinted overlay — sits between video and content */}
      <div
        className="fixed inset-0 pointer-events-none
                   bg-gradient-to-br from-[#050510]/60 via-[#0a0a20]/45 to-[#1a0d40]/40"
        style={{ zIndex: 1 }}
      />
    </>
  );
}
