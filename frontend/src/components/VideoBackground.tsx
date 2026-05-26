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
//
// Source loading — direct <video src>, NOT fetch()+blob.
//   The background clip is ~56 MB. The old code did `fetch('/214405.mp4')`
//   then `.blob()`, which buffers the ENTIRE file into memory before the
//   <video> ever gets a source. On a slow / contended boot that transfer
//   stalled, `blobUrl` stayed null, and the screen was just black — and
//   the in-flight 56 MB starved the cover-image requests. A direct src
//   lets Chromium stream progressively (HTTP range requests): playback
//   starts after a few hundred KB and the file keeps buffering in the
//   background. Far more resilient, and it never blocks other assets.
import { useEffect, useRef, useState } from "react";

// VP9/WebM (NOT H.264/MP4). PySide6's QtWebEngine wheel ships without
// proprietary codecs - H.264 in an MP4 container fails with
// `DEMUXER_ERROR_NO_SUPPORTED_STREAMS`. VP9/WebM is patent-free and
// always present in Chromium's media stack. The clip is re-encoded
// from 1080p/56MB H.264 to 720p/3.9MB VP9 (in frontend/public/) by
// ffmpeg - tiny perceptual loss at background-loop scale, ~14x
// smaller bundle. Relative path resolves correctly under both
// transports (./X under file:// = next to index.html; under HTTP =
// document root + X).
const VIDEO_SRC         = "./214405.webm";
// Pre-extracted single frame from the video — shipped as a static JPG
// next to the .webm so the low-perf path has the same visual identity
// (cosmic gradient + stars) without paying for video decode/composite.
// Built by `ffmpeg -ss 00:00:02 -i 214405.webm -frames:v 1 -update 1
// -q:v 2 bg-poster.jpg`; re-bake if the source clip changes.
const POSTER_SRC        = "./bg-poster.jpg";
const FADE_LEAD_SECONDS = 0.8;   // start crossfade this many sec before end
const FADE_MS           = 600;   // gentler fade, fully covers a ~350ms reset

// Frame-drop sentinel — pauses the loop when something else on the
// machine (a local LLM, a heavy render job, etc.) is starving the GPU
// and Chromium's compositor is missing frames. A choppy bg video
// triggers visible UI flicker on QtWebEngine; pausing it freezes the
// last decoded frame in place — looks like a still poster, costs zero
// GPU. Retries every RESUME_AFTER_MS so the loop comes back once the
// pressure eases.
const SAMPLE_INTERVAL_MS = 3000;
const DROP_THRESHOLD     = 8;     // dropped frames per 3s window → pause
const RESUME_AFTER_MS    = 30_000;

// Boot-time perf probe. Counts RAF frames over PROBE_DURATION_MS BEFORE
// the <video> elements mount; if the system can't sustain the FPS
// target the loop never starts and we render only the static gradient
// overlay. Catches the "user already had a heavy GPU workload running
// when the launcher opened" case the dynamic sentinel can't help with
// (the sentinel reacts to drops, but a fresh boot needs to refuse the
// load before it starts).
const PROBE_DURATION_MS = 700;
const PROBE_MIN_FPS     = 45;
type PerfMode = "probing" | "ok" | "low";

export default function VideoBackground() {
  const refA = useRef<HTMLVideoElement>(null);
  const refB = useRef<HTMLVideoElement>(null);
  const [active, setActive] = useState<"A" | "B">("A");
  const lastSwapRef = useRef<number>(0);
  const [perfMode, setPerfMode] = useState<PerfMode>("probing");

  // Boot probe — measure RAF cadence for PROBE_DURATION_MS. If the FPS
  // is healthy mount the <video> elements; if it's already starved
  // (e.g. a local LLM is hammering the GPU) skip video entirely for
  // this session and render only the gradient. Runs once on mount.
  useEffect(() => {
    const t0 = performance.now();
    let frames = 0;
    let raf = 0;
    const tick = () => {
      frames += 1;
      const elapsed = performance.now() - t0;
      if (elapsed < PROBE_DURATION_MS) {
        raf = requestAnimationFrame(tick);
      } else {
        const fps = (frames * 1000) / elapsed;
        setPerfMode(fps >= PROBE_MIN_FPS ? "ok" : "low");
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
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
    if (perfMode !== "ok") return;
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
  }, [perfMode]);

  // Crossfade scheduler — observes the active layer only; the inactive
  // layer just loops freely in the background.
  useEffect(() => {
    if (perfMode !== "ok") return;
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
  }, [active, perfMode]);

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

  // Frame-drop sentinel. Polls getVideoPlaybackQuality() on the active
  // layer; if drops/window exceeds DROP_THRESHOLD the loop is paused
  // (current frame stays on screen as a static poster) and a retry
  // timer attempts a resume after RESUME_AFTER_MS. The cycle repeats
  // until the system has the headroom to play smoothly again.
  useEffect(() => {
    if (perfMode !== "ok") return;
    const a = refA.current;
    const b = refB.current;
    if (!a || !b) return;

    let lastDropsA = 0;
    let lastDropsB = 0;
    let paused = false;
    let resumeId = 0;

    const readDrops = (el: HTMLVideoElement): number => {
      try {
        const q = el.getVideoPlaybackQuality?.();
        return q?.droppedVideoFrames ?? 0;
      } catch {
        return 0;
      }
    };

    const tryResume = () => {
      paused = false;
      lastDropsA = readDrops(a);
      lastDropsB = readDrops(b);
      a.play().catch(() => { /* autoplay shield will retry */ });
      b.play().catch(() => { /* autoplay shield will retry */ });
    };

    const sample = () => {
      if (paused) return;
      const da = readDrops(a);
      const db = readDrops(b);
      const windowDrops = Math.max(da - lastDropsA, db - lastDropsB);
      lastDropsA = da;
      lastDropsB = db;
      if (windowDrops >= DROP_THRESHOLD) {
        paused = true;
        try { a.pause(); } catch { /* ignored */ }
        try { b.pause(); } catch { /* ignored */ }
        resumeId = window.setTimeout(tryResume, RESUME_AFTER_MS);
      }
    };

    const id = window.setInterval(sample, SAMPLE_INTERVAL_MS);
    return () => {
      window.clearInterval(id);
      if (resumeId) window.clearTimeout(resumeId);
    };
  }, [perfMode]);

  const layerStyle = (visible: boolean): React.CSSProperties => ({
    zIndex: 0,
    opacity: visible ? 1 : 0,
    transitionProperty: "opacity",
    transitionDuration: `${FADE_MS}ms`,
    transitionTimingFunction: "ease-in-out",
  });

  // Low-perf mode: the boot probe found the system can't sustain the
  // FPS target (typically a local LLM saturating the GPU). Render the
  // pre-extracted poster frame from the same clip instead of the
  // moving video — same visual identity, zero decode/composite cost.
  // During the ~700ms probe we render the poster too so the screen
  // isn't blank or jarring if we end up switching to "ok" right after.
  if (perfMode !== "ok") {
    return (
      <>
        <div className="fixed inset-0" style={{ zIndex: 0, background: "#050510" }} aria-hidden />
        <img
          src={POSTER_SRC}
          alt=""
          aria-hidden
          className="fixed inset-0 w-full h-full object-cover pointer-events-none"
          style={{ zIndex: 0 }}
        />
        <div
          className="fixed inset-0 pointer-events-none
                     bg-gradient-to-br from-[#050510]/60 via-[#0a0a20]/45 to-[#1a0d40]/40"
          style={{ zIndex: 1 }}
        />
      </>
    );
  }

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
          src={VIDEO_SRC}
        />
        <video
          ref={refB}
          autoPlay muted playsInline loop preload="auto"
          className="absolute inset-0 w-full h-full object-cover pointer-events-none"
          style={layerStyle(active === "B")}
          src={VIDEO_SRC}
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
