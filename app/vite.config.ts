import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { defineConfig } from "vitest/config";
import type { Plugin } from "vite";

// The built pages are loaded from disk by Electron, so the policy is baked into the HTML (dev server excluded).
const CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'";
const csp = (): Plugin => ({
  name: "jarvis-csp",
  apply: "build",
  transformIndexHtml: (html) => html.replace("<head>", `<head>\n    <meta http-equiv="Content-Security-Policy" content="${CSP}" />`),
});

export default defineConfig({
  base: "./",
  plugins: [react(), csp()],
  clearScreen: false,
  server: { port: 1420, strictPort: true, host: "127.0.0.1", fs: { allow: ["..", "../.."] } },
  build: {
    target: "es2022",
    rollupOptions: {
      input: { orb: resolve(__dirname, "index.html"), panel: resolve(__dirname, "panel.html") },
    },
  },
  test: { environment: "node", include: ["src/**/*.test.ts", "electron/**/*.test.ts"], exclude: ["electron/e2e/**", "**/node_modules/**"] },
});
