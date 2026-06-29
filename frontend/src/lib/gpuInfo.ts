// GPU acceleration probe — the DECISIVE diagnostic for "the app is never smooth".
// Reads the real WebGL renderer (WEBGL_debug_renderer_info → UNMASKED_RENDERER).
// If it's SwiftShader/software, Chromium is NOT GPU-accelerated → that is the
// jank root cause (and a Chromium-flag / Qt problem, not CSS). If it names the
// real GPU (e.g. "Radeon RX 9070"), accel is ON and jank is elsewhere (paint).
import { jsLog } from "./eel";

export interface GpuInfo {
  renderer:    string;   // raw UNMASKED_RENDERER (or RENDERER fallback)
  vendor:      string;
  accelerated: boolean;  // false ⇒ software (SwiftShader/llvmpipe/Basic/Mesa)
}

let cached: GpuInfo | null = null;

export function detectGpu(): GpuInfo {
  if (cached) return cached;
  let renderer = "", vendor = "";
  try {
    const c = document.createElement("canvas");
    const gl = (c.getContext("webgl") || c.getContext("experimental-webgl")) as WebGLRenderingContext | null;
    if (gl) {
      const dbg = gl.getExtension("WEBGL_debug_renderer_info");
      if (dbg) {
        renderer = String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) || "");
        vendor   = String(gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL)   || "");
      }
      if (!renderer) renderer = String(gl.getParameter(gl.RENDERER) || "");
      if (!vendor)   vendor   = String(gl.getParameter(gl.VENDOR)   || "");
    }
  } catch { /* WebGL unavailable */ }
  const software = !renderer ||
    /swiftshader|software|microsoft basic|llvmpipe|mesa offscreen|generic/i.test(renderer);
  cached = { renderer: renderer || "unknown", vendor: vendor || "unknown", accelerated: !software };
  return cached;
}

/** Probe once on boot and write the result to the Python launcher.log so a
 *  non-smooth report can be diagnosed from the log without the user digging. */
export function logGpuOnce(): void {
  const g = detectGpu();
  const line = `[gpu-probe] accelerated=${g.accelerated} renderer="${g.renderer}" vendor="${g.vendor}"`;
  try { jsLog(line); } catch { /* */ }
  // eslint-disable-next-line no-console
  try { console.log(line); } catch { /* */ }
}
