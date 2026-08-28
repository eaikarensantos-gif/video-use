import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend defaults to http://127.0.0.1:8756 — see webapp/backend/main.py.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8756",
      "/media": "http://127.0.0.1:8756",
    },
  },
  build: {
    outDir: "dist",
  },
});
