import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Python FastAPI backend runs on a different port in development.
// Configure VITE_API_BASE_URL to point at the deployed backend in production.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
