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
  // Blob URL keeps the static .mp4 path out of the DOM so IDM-style
  // sniffers can't grab a downloadable source. Fetched once, shared
  // between both <video> layers, revoked on unmount.
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/214405.mp4");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      } catch (e) {
        console.warn("[VideoBackground] blob fetch failed, falling back to direct src:", e);
        if (!cancelled) setBlobUrl("/214405.mp4");
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, []);

  // Boot: start A at t=0, start B at t=duration/2 so the two layers are
  // permanently out of phase. We wait for metadata so currentTime sticks.
  //
  // Autoplay robustness: Chromium intermittently rejects the FIRST
  // play() (no prior user gesture, app-mode launch, power-saver, etc.)
  // even though our <video> has muted+autoplay+playsInline. The user
  // sees a frozen poster frame. So we layer three retry strategies:
  //   1. Re-attempt play() on every relevant media event (canplay,
  //      loadeddata, playing) until paused === false.
  //   2. A one-time, capture-phase document listener for ANY user
  //      gesture (pointerdown, keydown, touchstart). The gesture
  //      satisfies Chromium's autoplay heuristic, so the retry
  //      succeeds on first interaction.
  //   3. A short retry loop (~300ms apart, 6 attempts) right after
  //      mount in case the initial reject was a transient decoder
  //      busy-state.
  useEffect(() => {
    const a = refA.current;
    const b = refB.current;
    if (!a || !b) return;

    const cleanups: Array<() => void> = [];

    const tryPlay = (el: HTMLVideoElement, where: string) => {
      el.play().catch((e) => console.log(`Autoplay prevented [${where}]:`, e));
    };

    const begin = async (el: HTMLVideoElement, offsetRatio: number, tag: string) => {
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

      // Belt-and-braces in case React stripped the attribute somehow.
      el.muted        = true;
      el.playsInline  = true;
      el.loop         = true;

      tryPlay(el, `boot:${tag}`);

      // Retry on every event that means "the player has more data to
      // chew on". Each handler short-circuits once the element is
      // actively playing.
      const retry = () => { if (el.paused) tryPlay(el, `evt:${tag}`); };
      ["canplay", "loadeddata", "playing", "stalled", "suspend"].forEach((ev) => {
        el.addEventListener(ev, retry);
        cleanups.push(() => el.removeEventListener(ev, retry));
      });

      // 6 × 300ms ≈ 1.8s of patient retrying. Cheap; bails the moment
      // the video starts playing.
      let attempts = 0;
      const interval = window.setInterval(() => {
        if (!el.paused || attempts >= 6) {
          window.clearInterval(interval);
          return;
        }
        attempts += 1;
        tryPlay(el, `poll:${tag}#${attempts}`);
      }, 300);
      cleanups.push(() => window.clearInterval(interval));
    };

    begin(a, 0,   "A");
    begin(b, 0.5, "B");

    // Last-resort: any user gesture anywhere on the page nudges both
    // layers back to life. capture-phase so we don't compete with
    // app-level handlers; { once: true } so we don't leak listeners.
    const onGesture = () => {
      [a, b].forEach((el) => { if (el && el.paused) tryPlay(el, "gesture"); });
    };
    const opts: AddEventListenerOptions = { once: true, capture: true, passive: true };
    document.addEventListener("pointerdown", onGesture, opts);
    document.addEventListener("keydown",     onGesture, opts);
    document.addEventListener("touchstart",  onGesture, opts);
    cleanups.push(() => {
      document.removeEventListener("pointerdown", onGesture, true);
      document.removeEventListener("keydown",     onGesture, true);
      document.removeEventListener("touchstart",  onGesture, true);
    });

    return () => { cleanups.forEach((fn) => fn()); };
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
      {/* Both crossfading layers live inside one fixed wrapper plus a
          transparent shield on top. IDM and similar extensions look for
          a hoverable <video> element to attach their "download this
          video" panel — the shield catches that hover instead, and
          pointer-events:none on each video makes sure the browser never
          registers hover on them directly either. */}
      <div className="fixed inset-0" style={{ zIndex: 0 }} aria-hidden>
        <video
          ref={refA}
          autoPlay muted playsInline loop preload="auto"
          className="absolute inset-0 w-full h-full object-cover pointer-events-none"
          style={layerStyle(active === "A")}
          src={blobUrl ?? undefined}
        />
        <video
          ref={refB}
          autoPlay muted playsInline loop preload="auto"
          className="absolute inset-0 w-full h-full object-cover pointer-events-none"
          style={layerStyle(active === "B")}
          src={blobUrl ?? undefined}
        />
        <div className="absolute inset-0 z-10 bg-transparent" />
      </div>
      {/* Tinted overlay — sits between video and content */}
      <div
        className="fixed inset-0 pointer-events-none
                   bg-gradient-to-br from-[#050510]/60 via-[#0a0a20]/45 to-[#1a0d40]/40"
        style={{ zIndex: 1 }}
      />
    </>
  );
}
