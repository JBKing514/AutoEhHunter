import "@mdi/font/css/materialdesignicons.css";
import { createApp } from "vue";
import { createVuetify } from "vuetify";
import "vuetify/styles";
import App from "./App.vue";

const vuetify = createVuetify({
  theme: {
    defaultTheme: "modernLight",
    themes: {
      modernLight: {
        colors: {
          primary: "#2563eb",
          secondary: "#0ea5e9",
          surface: "#ffffff",
          background: "#f4f7ff",
        },
      },
      modernDark: {
        dark: true,
        colors: {
          primary: "#60a5fa",
          secondary: "#22d3ee",
          surface: "#0f172a",
          background: "#020617",
        },
      },
      oceanLight: {
        colors: {
          primary: "#0f766e",
          secondary: "#0891b2",
          surface: "#f8fffe",
          background: "#eefcfb",
        },
      },
      oceanDark: {
        dark: true,
        colors: {
          primary: "#14b8a6",
          secondary: "#22d3ee",
          surface: "#082f49",
          background: "#00131f",
        },
      },
      sunsetLight: {
        colors: {
          primary: "#ea580c",
          secondary: "#e11d48",
          surface: "#fff9f7",
          background: "#fff3ed",
        },
      },
      sunsetDark: {
        dark: true,
        colors: {
          primary: "#fb923c",
          secondary: "#fb7185",
          surface: "#431407",
          background: "#1c0b05",
        },
      },
      forestLight: {
        colors: {
          primary: "#166534",
          secondary: "#0f766e",
          surface: "#f6fff8",
          background: "#ecfdf3",
        },
      },
      forestDark: {
        dark: true,
        colors: {
          primary: "#4ade80",
          secondary: "#2dd4bf",
          surface: "#0b1f16",
          background: "#05140d",
        },
      },
      slateLight: {
        colors: {
          primary: "#334155",
          secondary: "#475569",
          surface: "#ffffff",
          background: "#f1f5f9",
        },
      },
      slateDark: {
        dark: true,
        colors: {
          primary: "#cbd5e1",
          secondary: "#94a3b8",
          surface: "#111827",
          background: "#020617",
        },
      },
      customLight: {
        colors: {
          primary: "#6750A4",
          secondary: "#625B71",
          surface: "#ffffff",
          background: "#f7f2fa",
        },
      },
      customDark: {
        dark: true,
        colors: {
          primary: "#d0bcff",
          secondary: "#ccc2dc",
          surface: "#1d1b20",
          background: "#141218",
        },
      },
    },
  },
});

createApp(App).use(vuetify).mount("#app");
