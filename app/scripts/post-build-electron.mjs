// The app package is ESM (Vite); the Electron main process is compiled to CommonJS, so mark its folder.
import { writeFileSync } from "node:fs";
writeFileSync(new URL("../dist-electron/package.json", import.meta.url), JSON.stringify({ type: "commonjs" }) + "\n");
