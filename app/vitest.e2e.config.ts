import { defineConfig } from "vitest/config";

// Real end-to-end tests: they launch the actual Electron app and the actual Python service.
export default defineConfig({
  test: {
    environment: "node",
    include: ["electron/e2e/**/*.e2e.test.ts"],
    testTimeout: 120_000,
    hookTimeout: 30_000,
    fileParallelism: false,
  },
});
