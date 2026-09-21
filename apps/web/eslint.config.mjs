import { defineConfig, globalIgnores } from "eslint/config";
import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat({
  baseDirectory: import.meta.dirname,
});

export default defineConfig([
  ...compat.config({
    extends: [
      "next/core-web-vitals",
      "next/typescript",
    ],
  }),

  {
    files: ["e2e/**/*.js"],
    rules: {
      "@typescript-eslint/no-require-imports": "off",
    },
  },

  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);
