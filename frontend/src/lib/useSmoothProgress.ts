// useSmoothProgress: turn a coarse/sticky backend percentage (e.g. a mod-install
// stage that jumps 25 → 55 → 100 and sits on 55 for a long time) into a value
// that always FLOWS. While the real percentage is stuck, the shown value keeps
// creeping forward - decelerating as it climbs, never past ~96 - so a long stage
// never looks frozen; it snaps to 100 the moment the real percentage reaches 100.
//
// Used for the shared mod-install progress bar, so EVERY mod (not just the
// multi-stage Witcher 3 applier) gets the smooth animation.
import { useEffect, useRef, useState } from "react";

export function useSmoothProgress(target: number, active: boolean): number {
  const [shown, setShown] = useState(0);
  const shownRef = useRef(0);
  const targetRef = useRef(target);
  targetRef.current = target;

  useEffect(() => {
    if (!active) { shownRef.current = 0; setShown(0); return; }
    let raf = 0;
    const loop = () => {
      const cur = shownRef.current;
      const t = targetRef.current;
      // Goal: the real target if it's ahead of us, else a soft ceiling that
      // creeps toward ~96 (slower the higher we are). Real 100 → go all the way.
      const goal = t >= 100
        ? 100
        : Math.min(96, Math.max(t, cur + (96 - cur) * 0.04));
      const next = cur + (goal - cur) * 0.09;
      if (t >= 100 && next > 99.4) { shownRef.current = 100; setShown(100); return; }
      shownRef.current = next;
      setShown(next);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [active]);

  return shown;
}
