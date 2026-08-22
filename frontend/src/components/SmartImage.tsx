// An <img> that shows a shimmering skeleton placeholder over its own area
// until the picture actually paints - so a fresh install (or a cleared cache)
// never flashes an empty box while covers/banners stream in from the server.
// The PARENT must be a positioning context (relative/absolute) because the
// skeleton overlay is `absolute inset-0`. On error the image + skeleton both
// hide, revealing whatever fallback the parent draws behind it.
import { useState, useEffect, useRef, type ImgHTMLAttributes } from "react";

export default function SmartImage({
  className = "", onLoad, onError, ...rest
}: ImgHTMLAttributes<HTMLImageElement>) {
  const [loaded, setLoaded] = useState(false);
  const [err, setErr] = useState(false);
  // "the placeholder gave up", NOT "the image failed" - see the timer below.
  const [settled, setSettled] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  // Reset the load/error latch when `src` changes on a PERSISTED instance (a row
  // keyed by game.id that gets a different cover/banner URL from an SWR push).
  //
  // THE CACHED-IMAGE RACE (the "covers vanish after a scan" bug): when the games
  // list is rebuilt (a drive scan, a menu switch, the software tab), the cards
  // re-render/re-mount with the SAME cover URL - already in the browser cache. A
  // fresh <img> whose src is cached can become `complete` BEFORE React attaches
  // onLoad, so onLoad never fires and `loaded` stays false → the cover sits at
  // opacity-0 forever until the whole view is remounted (leave + return "fixes"
  // it). So: after each commit, if the element is already complete, mark it
  // loaded synchronously instead of waiting for an event that won't come.
  useEffect(() => {
    setErr(false);
    setSettled(false);
    const el = imgRef.current;
    if (el && el.complete && el.naturalWidth > 0) {
      setLoaded(true);            // cached + decoded → no onLoad will fire
    } else if (el && el.complete && el.naturalWidth === 0 && el.src) {
      setErr(true);              // cached error (broken) → also no onError fires
    } else {
      setLoaded(false);          // genuinely loading → skeleton until onLoad
    }
  }, [rest.src]);
  // STUCK-LOAD safety net (same reasoning as GameCard) - a request that never
  // fires onLoad/onError must not leave the skeleton shimmering forever. It
  // only SETTLES the placeholder; it must never latch the image off, because
  // this clock starts at MOUNT while a lazy/off-screen image may not begin
  // fetching until much later. `settled` is therefore separate from `err`.
  useEffect(() => {
    if (loaded || err || settled) return;
    const t = window.setTimeout(() => setSettled(true), 12000);
    return () => window.clearTimeout(t);
  }, [rest.src, loaded, err, settled]);
  return (
    <>
      {!loaded && !err && !settled && <div className="skeleton absolute inset-0" aria-hidden />}
      <img
        {...rest}
        ref={imgRef}
        onLoad={(e) => { setLoaded(true); setErr(false); onLoad?.(e); }}
        onError={(e) => { setErr(true); onError?.(e); }}
        /* keyed on `loaded` alone: once a picture has decoded it must show,
           even if an earlier attempt for this element had errored. */
        className={`${className} transition-opacity duration-500 ${loaded ? "opacity-100" : "opacity-0"}`}
      />
    </>
  );
}
