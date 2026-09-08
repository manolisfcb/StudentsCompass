import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "src/api/generated"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      // Plan 08 §7: "Una única capa HTTP; ningún componente llama `fetch`
      // directamente." A lint rule is the only version of that sentence that
      // survives eight verticals and a reviewer having a bad day.
      "no-restricted-globals": [
        "error",
        {
          name: "fetch",
          message:
            "Use the HTTP layer in src/api/client.ts. Direct fetch bypasses credentials, CSRF and error mapping.",
        },
      ],
    },
  },
  {
    // The HTTP layer is the one place allowed to call fetch in application
    // code; tests are allowed too because they assert *about* it — stubbing
    // and inspecting the global is how the same-origin contract is proved.
    files: ["src/api/client.ts", "**/*.test.ts", "**/*.test.tsx"],
    rules: { "no-restricted-globals": "off" },
  },
  {
    files: ["vite.config.ts", "vitest.setup.ts"],
    languageOptions: { globals: globals.node },
  },
);
