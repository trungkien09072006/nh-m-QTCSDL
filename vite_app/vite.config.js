import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
      },
      "/admin": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
      },
      "/parent": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
      },
      "/teacher": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
      },
      "/login": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
      },
      "/logout": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
      },
      "/static": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
      },
    },
  },
});
