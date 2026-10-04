import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { port: 1420, strictPort: true, host: "127.0.0.1", fs: { allow: ["..", "../.."] } },
  build: {
    target: "es2022",
    rollupOptions: {
      input: { orb: resolve(__dirname, "index.html"), panel: resolve(__dirname, "panel.html") },
    },
  },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
