// Optional, synthesized UI sounds (no audio assets — Web Audio oscillators).
// Off by default; gated by the themeSounds pref. initUiSounds() wires a soft
// click to every button press when enabled.
import { getSounds } from "./themePrefs";

let ctx: AudioContext | null = null;
function ac(): AudioContext | null {
  try {
    if (!ctx) {
      const C = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      ctx = new C();
    }
    if (ctx.state === "suspended") void ctx.resume();
    return ctx;
  } catch { return null; }
}

function blip(freq: number, dur: number, gain: number, type: OscillatorType = "sine") {
  const a = ac();
  if (!a) return;
  const osc = a.createOscillator();
  const g = a.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  const t = a.currentTime;
  g.gain.setValueAtTime(0, t);
  g.gain.linearRampToValueAtTime(gain, t + 0.006);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  osc.connect(g); g.connect(a.destination);
  osc.start(t); osc.stop(t + dur + 0.02);
}

export function playClick()   { if (getSounds()) blip(620, 0.06, 0.05, "triangle"); }
export function playSuccess() { if (getSounds()) { blip(660, 0.09, 0.06, "sine"); setTimeout(() => blip(880, 0.10, 0.05, "sine"), 70); } }
export function playError()   { if (getSounds()) blip(200, 0.16, 0.06, "sawtooth"); }

/** Wire a soft click to every button press (when sounds are on). Returns teardown. */
export function initUiSounds(): () => void {
  const onDown = (e: PointerEvent) => {
    if (e.button !== 0) return;
    const btn = (e.target as Element | null)?.closest?.("button");
    if (btn && !(btn as HTMLButtonElement).disabled) playClick();
  };
  document.addEventListener("pointerdown", onDown, true);
  return () => document.removeEventListener("pointerdown", onDown, true);
}
