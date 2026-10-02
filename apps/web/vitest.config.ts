import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
  resolve: {
    // Mirror the `@/*` -> `src/*` alias from tsconfig.json so unit tests can
    // import modules exactly the way application code does.
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});