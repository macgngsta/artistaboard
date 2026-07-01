import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// Dev proxy forwards API paths to the FastAPI backend so the browser talks to a
// single same-origin (localhost:5173), keeping the httpOnly SameSite=Lax session
// cookie in play. CORS on the backend is a belt-and-suspenders fallback.
const API_TARGET = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";
const API_PREFIXES = ["/auth", "/scenes", "/preview", "/boards", "/pipelines", "/health"];

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      API_PREFIXES.map((p) => [p, { target: API_TARGET, changeOrigin: true }]),
    ),
  },
});
