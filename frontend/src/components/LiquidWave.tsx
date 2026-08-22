// Flowing "liquid wave" progress fill - the SAME visual the public website
// uses on its live-progress dashboard. Extracted here so BOTH the home
// progress card AND the download/update progress bars share one component.
//
// `pct` drives the horizontal FILL (RTL - fills from the right leading edge);
// `ratePerMin` drives the water LEVEL + ripple speed within the fill. For a
// plain download (no translation rate) pass a small lively constant so the
// surface sits at a pleasant height and gently ripples.
import { useEffect, useRef } from "react";

export default function LiquidWave({
  pct, ratePerMin, primary, secondary, glow, height = 72,
}: {
  pct: number; ratePerMin: number; primary: string; secondary: string; glow: string; height?: number;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const tgt = useRef({ pct, rate: ratePerMin });
  tgt.current.pct = pct;
  tgt.current.rate = ratePerMin;

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const NS = 'http://www.w3.org/2000/svg';
    const TAU = Math.PI * 2;
    const CROSS_SEC = 3.5;
    const mk = (tag: string, attrs: Record<string, string | number>) => {
      const e = document.createElementNS(NS, tag);
      for (const k in attrs) e.setAttribute(k, String(attrs[k]));
      return e;
    };
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    const gid = 'lw-' + Math.random().toString(36).slice(2);
    const defs = mk('defs', {});
    const lg = mk('linearGradient', { id: gid, x1: '0', y1: '0', x2: '0', y2: '1' });
    lg.appendChild(mk('stop', { offset: '0%', 'stop-color': secondary }));
    lg.appendChild(mk('stop', { offset: '55%', 'stop-color': secondary }));
    lg.appendChild(mk('stop', { offset: '100%', 'stop-color': primary }));
    defs.appendChild(lg);
    svg.appendChild(defs);

    const grayFill = mk('path', { fill: 'rgba(255,255,255,0.09)' });
    const grayHi = mk('path', { fill: 'none', stroke: 'rgba(255,255,255,0.16)', 'stroke-width': '1.25' });
    const back = mk('path', { fill: secondary, 'fill-opacity': '0.34' });
    const front = mk('path', { fill: `url(#${gid})` });
    const hi = mk('path', { fill: 'none', stroke: 'rgba(255,255,255,0.55)', 'stroke-width': '1.5', 'stroke-opacity': '0.7' });
    svg.appendChild(grayFill); svg.appendChild(grayHi); svg.appendChild(back); svg.appendChild(front); svg.appendChild(hi);

    const bubbles = Array.from({ length: 6 }, () => {
      const el = mk('circle', { r: 1.3 + Math.random() * 2, fill: 'rgba(255,255,255,0.45)' });
      svg.appendChild(el);
      return { el, x: Math.random(), y: Math.random(), sp: 0.14 + Math.random() * 0.22 };
    });
    const mkGlow = mk('circle', { r: '9', fill: `${secondary}88` });
    const marker = mk('circle', { r: '4.5', fill: '#fff' });
    svg.appendChild(mkGlow); svg.appendChild(marker);

    const layers = [
      { path: back, dy: 4, amp: 5, waveLen: 210, freq: 1.6 },
      { path: front, dy: 0, amp: 4, waveLen: 150, freq: 2.2 },
    ];
    const top = layers[1];

    const reduce = typeof window !== 'undefined'
      && !!window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    let disp = Math.max(0, Math.min(1, tgt.current.pct / 100));
    let level = 0.15, t = 0, wt = 0, speedMul = 1, ampMul = 1, last = performance.now(), raf = 0;
    const histT = [0]; const histL = [0.15];
    const pushHist = (tm: number, lv: number) => {
      histT.push(tm); histL.push(lv);
      const cutoff = tm - 5.0; let k = 0;
      while (k < histT.length - 1 && histT[k] < cutoff) k++;
      if (k > 0) { histT.splice(0, k); histL.splice(0, k); }
    };
    const leadAt = (tm: number) => {
      const n = histT.length;
      if (tm <= histT[0]) return histL[0];
      if (tm >= histT[n - 1]) return histL[n - 1];
      let lo = 0, hi = n - 1;
      while (hi - lo > 1) { const m = (lo + hi) >> 1; if (histT[m] <= tm) lo = m; else hi = m; }
      const f = (tm - histT[lo]) / (histT[hi] - histT[lo] || 1);
      return histL[lo] + (histL[hi] - histL[lo]) * f;
    };
    type Layer = { dy: number; amp: number; waveLen: number };
    const surfY = (x: number, xStart: number, span: number, ly: Layer, phase: number, yB: number, yT: number) => {
      const delay = span > 0 ? (Math.max(0, x - xStart) / span) * CROSS_SEC : 0;
      const lv = leadAt(t - delay);
      const base = yB - (yB - yT) * lv;
      return base + ly.dy + ly.amp * ampMul * Math.sin(phase + (x / ly.waveLen) * TAU);
    };
    const ptsFor = (xa: number, xb: number, xStart: number, span: number, ly: Layer, phase: number, yB: number, yT: number): [number, number][] => {
      const steps = Math.max(2, Math.round(Math.max(1, xb - xa) / 7));
      const arr: [number, number][] = [];
      for (let i = 0; i <= steps; i++) { const x = xa + (xb - xa) * i / steps; arr.push([x, surfY(x, xStart, span, ly, phase, yB, yT)]); }
      return arr;
    };
    const areaD = (pts: [number, number][], h: number) => {
      const x0 = pts[0][0], xN = pts[pts.length - 1][0];
      let d = `M ${x0.toFixed(1)} ${h} L ${x0.toFixed(1)} ${pts[0][1].toFixed(1)}`;
      for (const [x, y] of pts) d += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
      return d + ` L ${xN.toFixed(1)} ${h} Z`;
    };
    const lineOf = (pts: [number, number][]) => {
      let d = `M ${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`;
      for (const [x, y] of pts) d += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
      return d;
    };

    const render = () => {
      const w = svg.clientWidth || 600; const h = height;
      svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
      const xStart = w * (1 - disp); const yB = h - 12; const yT = 12;
      const span = Math.max(1, w - xStart);
      const ph = -wt * top.freq;
      if (xStart > 1.5) {
        const gp = ptsFor(0, xStart, xStart, span, top, ph, yB, yT);
        grayFill.setAttribute('d', areaD(gp, h));
        grayHi.setAttribute('d', lineOf(gp));
        grayFill.setAttribute('opacity', '1'); grayHi.setAttribute('opacity', '1');
      } else {
        grayFill.setAttribute('opacity', '0'); grayHi.setAttribute('opacity', '0');
      }
      for (const ly of layers) ly.path.setAttribute('d', areaD(ptsFor(xStart, w, xStart, span, ly, -wt * ly.freq, yB, yT), h));
      hi.setAttribute('d', lineOf(ptsFor(xStart, w, xStart, span, top, ph, yB, yT)));
      const my = surfY(xStart, xStart, span, top, ph, yB, yT);
      marker.setAttribute('cx', String(xStart)); marker.setAttribute('cy', String(my));
      mkGlow.setAttribute('cx', String(xStart)); mkGlow.setAttribute('cy', String(my));
      marker.setAttribute('opacity', disp > 0.02 ? '1' : '0');
      mkGlow.setAttribute('opacity', disp > 0.02 ? '0.85' : '0');
      for (const b of bubbles) {
        const bx = xStart + b.x * (w - xStart);
        b.el.setAttribute('cx', String(bx));
        b.el.setAttribute('cy', String(8 + b.y * (h - 12)));
        b.el.setAttribute('opacity', bx > xStart ? '0.5' : '0');
      }
    };

    let onScreen = true;
    const io = typeof IntersectionObserver !== 'undefined'
      ? new IntersectionObserver((e) => { onScreen = e[0]?.isIntersecting ?? true; }, { threshold: 0 })
      : null;
    if (io && svg.parentElement) io.observe(svg.parentElement);

    const loop = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000); last = now;
      const lpm = Math.max(0, tgt.current.rate);
      const sat = lpm / (lpm + 20);
      speedMul = 0.4 + sat * 3.0 + Math.min(2.6, lpm / 110);
      ampMul = 0.6 + sat * 1.15;
      const targetPct = Math.max(0, Math.min(1, tgt.current.pct / 100));
      if (!document.hidden && onScreen) {
        t += dt; wt += dt * speedMul;
        const lnorm = Math.max(0.08, Math.min(0.95, 0.08 + 0.87 * sat));
        level += (lnorm - level) * Math.min(1, dt * 6);
        pushHist(t, level);
        disp += (targetPct - disp) * Math.min(1, dt * 5);
        for (const b of bubbles) { b.y -= b.sp * 0.02 * speedMul; if (b.y < 0) { b.y = 1; b.x = Math.random(); } }
        render();
      }
      raf = requestAnimationFrame(loop);
    };

    if (reduce) {
      disp = Math.max(0, Math.min(1, tgt.current.pct / 100));
      const sat0 = Math.max(0, tgt.current.rate) / (Math.max(0, tgt.current.rate) + 20);
      level = Math.max(0.08, Math.min(0.95, 0.08 + 0.87 * sat0));
      pushHist(0, level);
      render();
    } else {
      raf = requestAnimationFrame(loop);
    }
    return () => { cancelAnimationFrame(raf); if (io) io.disconnect(); };
  }, [primary, secondary, glow, height]);

  return (
    <div
      className="relative w-full rounded-2xl overflow-hidden"
      style={{ height, background: `${primary}12`, boxShadow: `inset 0 0 26px ${glow}22` }}
    >
      <svg ref={svgRef} className="block w-full" style={{ height }} preserveAspectRatio="none" />
    </div>
  );
}
