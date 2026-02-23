import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import vuetify from "vite-plugin-vuetify";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    vue(),
    vuetify({ autoImport: true }),
    VitePWA({
      registerType: "autoUpdate",
      workbox: {
        maximumFileSizeToCacheInBytes: 6 * 1024 * 1024,
      },
      manifest: {
        name: "AutoEhHunter",
        short_name: "AEH",
        description: "AutoEhHunter dashboard",
        theme_color: "#2563eb",
        background_color: "#f4f7ff",
        display: "standalone",
        start_url: "/",
        icons: [
          {
            src: "/src/ico/AutoEhHunterLogo_128.png",
            sizes: "128x128",
            type: "image/png",
          },
        ],
      },
    }),
  ],
  build: {
    outDir: "dist",
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8501",
    },
  },
});
