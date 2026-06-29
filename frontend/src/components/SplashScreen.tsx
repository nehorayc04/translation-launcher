// Short branded launch splash — an animated logo + title shown once on app
// boot, then fades out. Skips instantly when the user disabled animations.
import { useEffect, useState } from "react";
import { getAnims } from "../lib/themePrefs";

export default function SplashScreen({ onDone }: { onDone: () => void }) {
  const [leaving, setLeaving] = useState(false);
  const animsOn = getAnims();

  useEffect(() => {
    if (!animsOn) { onDone(); return; }
    const t1 = setTimeout(() => setLeaving(true), 1500);  // start fade
    const t2 = setTimeout(onDone, 2000);                  // unmount
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [animsOn, onDone]);

  if (!animsOn) return null;

  return (
    <div
      className="fixed inset-0 z-[200] grid place-items-center transition-opacity duration-500"
      style={{ background: "#050510", opacity: leaving ? 0 : 1, pointerEvents: leaving ? "none" : "auto" }}
    >
      {/* ambient brand glows */}
      <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-[40rem] h-72 rounded-full bg-brand-yellow/10 blur-3xl animate-glow-pulse" aria-hidden />
      <div className="absolute -bottom-24 right-1/4 w-96 h-96 rounded-full bg-brand-cyan/10 blur-3xl" aria-hidden />

      <div className="relative flex flex-col items-center text-center animate-scale-in">
        {/* Neon avatar ring */}
        <div className="relative w-24 h-24 rounded-full bg-[#1a0d40] border-2 border-[#00ffe0]
                        shadow-[0_0_40px_rgba(0,255,224,0.55)] overflow-hidden grid place-items-center mb-6
                        animate-float">
          <img src="./profile.png" alt="" className="w-full h-full object-cover"
               onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }} />
        </div>
        <div className="font-display text-[11px] tracking-[0.34em] text-brand-yellow mb-2">
          P R O J E C T &nbsp; T R A N S L A T I O N
        </div>
        <h1 className="text-3xl font-extrabold mb-6"><span className="text-gradient">מנהל התרגומים</span></h1>
        {/* loading shimmer bar */}
        <div className="w-48 h-1 rounded-full overflow-hidden bg-white/10 relative">
          <div className="absolute inset-y-0 -left-1/3 w-1/3 rounded-full bg-brand-cyan"
               style={{ animation: "splash-bar 1.4s ease-in-out infinite" }} />
        </div>
      </div>

      <style>{`@keyframes splash-bar { 0% { left: -33%; } 100% { left: 100%; } }`}</style>
    </div>
  );
}
