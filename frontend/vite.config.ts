import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// The Python server (python -m sat_web) serves the built app in production.
// During development run `npm run dev`; API, media and visualisation requests
// are proxied to the Python server on port 8000.
const backend = process.env.WIZSAT_BACKEND ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: backend, ws: true, changeOrigin: true },
      "/media": { target: backend, changeOrigin: true },
      "/visualisations": { target: backend, changeOrigin: true },
    },
    fs: { allow: [".."] },
  },
  build: {
    outDir: "dist",
    chunkSizeWarningLimit: 1600,
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ["echarts"],
          cytoscape: ["cytoscape"],
          mantine: ["@mantine/core", "@mantine/hooks", "@mantine/notifications", "@mantine/dropzone"],
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
