/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The browser must never see two origins (plan 08 §1, §3). In production that
// is Nginx; in `npm run dev` it is this proxy, aimed at the same paths Nginx
// forwards. Keeping both lists identical is the point: a path that works in dev
// and 404s behind Nginx is exactly the class of bug this task exists to avoid.
const PROXIED_PREFIXES = ["/api", "/healthz", "/readyz", "/sitemap.xml", "/robots.txt"];

const DEV_API_ORIGIN = process.env.DEV_API_ORIGIN ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      PROXIED_PREFIXES.map((prefix) => [
        prefix,
        { target: DEV_API_ORIGIN, changeOrigin: false },
      ]),
    ),
  },
  build: {
    // Nginx serves /assets/* as immutable (see nginx.conf); the hash in the
    // filename is what makes that safe.
    assetsDir: "assets",
    // Off in production: the runtime image serves everything under /assets as
    // immutable and public, and a 1.6 MB map per build is bandwidth spent on
    // nobody. A vertical that wires an error tracker can turn on "hidden"
    // sourcemaps and upload them instead of serving them.
    sourcemap: false,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
});
