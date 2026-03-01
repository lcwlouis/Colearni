import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  esbuild: {
    jsx: "automatic",
  },
  test: {
    environment: "node",
    include: ["lib/**/*.test.ts", "features/**/*.test.ts", "features/**/*.test.tsx", "components/**/*.test.ts", "components/**/*.test.tsx"],
  },
});
