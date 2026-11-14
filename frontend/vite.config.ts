import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  // The env file lives at the repo root, one level up from frontend/.
  // Empty prefix: read plain names too (PORT, FRONTEND_PORT), not just VITE_*.
  const env = loadEnv(mode, path.resolve(import.meta.dirname, ".."), "");
  const backendPort = env.PORT || "8000";
  const frontendPort = Number(env.FRONTEND_PORT || 5173);

  return {
    plugins: [
      tanstackRouter({ target: "react", autoCodeSplitting: true }),
      react(),
      tailwindcss(),
    ],
    resolve: {
      alias: {
        "@": path.resolve(import.meta.dirname, "./src"),
      },
    },
    server: {
      // strictPort: a clash fails loudly instead of drifting to another port,
      // which would silently point at the wrong worktree.
      port: frontendPort,
      strictPort: true,
      proxy: {
        "/api": { target: `http://127.0.0.1:${backendPort}`, changeOrigin: true },
      },
    },
  };
});
