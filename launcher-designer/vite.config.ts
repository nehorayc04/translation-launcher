import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// `@fe` → the real launcher source. The /preview page imports the REAL App
// (@fe/App); the `designer-mock-eel` plugin swaps the eel backend module
// (../frontend/src/lib/eel) for ./src/mock/eel so the app renders with sample
// data and NO Qt/Eel runtime. Multi-page: index.html (the inspector chrome) +
// preview.html (the real app, embedded as an iframe).
const FE_SRC   = fileURLToPath(new URL("../frontend/src", import.meta.url));
const MOCK_EEL = fileURLToPath(new URL("./src/mock/eel.ts", import.meta.url));

function mockEelPlugin() {
  return {
    name: "designer-mock-eel",
    enforce: "pre" as const,
    resolveId(source: string) {
      // any import resolving to the launcher's eel backend → the mock
      if (/(?:^|[\\/])lib[\\/]eel(?:\.tsx?)?$/.test(source) || source === "@fe/lib/eel") {
        return MOCK_EEL;
      }
      return null;
    },
  };
}

export default defineConfig({
  plugins: [mockEelPlugin(), react()],
  resolve: {
    alias: { "@fe": FE_SRC },
  },
  server: {
    port: 5180,
    strictPort: false,
    fs: { allow: [".."] },
  },
  build: {
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL("./index.html", import.meta.url)),
        preview: fileURLToPath(new URL("./preview.html", import.meta.url)),
      },
    },
  },
});
