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
    },
  },
});

createApp(App).use(vuetify).mount("#app");
