import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Local: 127.0.0.1:8000. Docker Compose: http://backend:8000 via VITE_PROXY_TARGET.
const proxyTarget = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    // Allow Cloudflare tunnel / Docker to reach the Vite dev server.
    host: true,
    port: 5173,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: proxyTarget,
        changeOrigin: true,
      },
      "/health": {
        target: proxyTarget,
        changeOrigin: true,
      },
      // Prefer direct WS in the browser (see src/api.ts).
      // Keep this proxy only as a fallback.
      "/ws": {
        target: proxyTarget,
        changeOrigin: true,
        ws: true,
        rewriteWsOrigin: true,
      },
    },
  },
});
