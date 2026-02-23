import { watch } from "vue";
import { useTheme } from "vuetify";
import { asBool, ensureHexColor, shiftHex } from "../utils/helpers";

export function useThemeManager(configRef) {
  const theme = useTheme();

  let stopThemeWatch = null;
  let prefersDarkMedia = null;
  let prefersDarkListener = null;

  function applyTheme() {
    const config = configRef?.value || {};
    const modeSetting = String(config.DATA_UI_THEME_MODE || "system");
    const systemDark = typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)").matches : false;
    const dark = modeSetting === "dark" || (modeSetting === "system" && systemDark);
    const preset = String(config.DATA_UI_THEME_PRESET || "modern");
    const themes = theme.themes.value;
    const useCustom = preset === "custom";

    if (useCustom) {
      const primary = ensureHexColor(config.DATA_UI_THEME_CUSTOM_PRIMARY, "#2563eb");
      const secondary = ensureHexColor(config.DATA_UI_THEME_CUSTOM_SECONDARY, "#0ea5e9");
      const accent = ensureHexColor(config.DATA_UI_THEME_CUSTOM_ACCENT, "#f59e0b");
      themes.customLight = {
        dark: false,
        colors: {
          primary,
          secondary,
          accent,
          info: accent,
          surface: "#ffffff",
          background: shiftHex(primary, 235),
        },
      };
      themes.customDark = {
        dark: true,
        colors: {
          primary: shiftHex(primary, 72),
          secondary: shiftHex(secondary, 72),
          accent: shiftHex(accent, 72),
          info: shiftHex(accent, 72),
          surface: "#1d1b20",
          background: asBool(config.DATA_UI_THEME_OLED) ? "#000000" : "#141218",
        },
      };
    }

    const mode = dark ? "Dark" : "Light";
    const baseName = `${preset}${mode}`;
    const fallbackName = `modern${mode}`;
    const resolvedBaseName = themes[baseName] ? baseName : fallbackName;
    const oled = dark && asBool(config.DATA_UI_THEME_OLED);

    if (oled) {
      const oledName = `${resolvedBaseName}Oled`;
      const baseTheme = themes[resolvedBaseName];
      themes[oledName] = {
        ...baseTheme,
        dark: true,
        colors: {
          ...(baseTheme?.colors || {}),
          background: "#000000",
          surface: "#000000",
        },
      };
      theme.global.name.value = oledName;
      return;
    }

    theme.global.name.value = resolvedBaseName;
  }

  function initTheme() {
    if (!stopThemeWatch) {
      stopThemeWatch = watch(
        () => [
          configRef?.value?.DATA_UI_THEME_MODE,
          configRef?.value?.DATA_UI_THEME_PRESET,
          configRef?.value?.DATA_UI_THEME_OLED,
          configRef?.value?.DATA_UI_THEME_CUSTOM_PRIMARY,
          configRef?.value?.DATA_UI_THEME_CUSTOM_SECONDARY,
          configRef?.value?.DATA_UI_THEME_CUSTOM_ACCENT,
        ],
        () => applyTheme(),
        { deep: true, immediate: true },
      );
    }

    if (typeof window !== "undefined" && window.matchMedia && !prefersDarkMedia) {
      prefersDarkMedia = window.matchMedia("(prefers-color-scheme: dark)");
      prefersDarkListener = () => applyTheme();
      if (typeof prefersDarkMedia.addEventListener === "function") {
        prefersDarkMedia.addEventListener("change", prefersDarkListener);
      } else if (typeof prefersDarkMedia.addListener === "function") {
        prefersDarkMedia.addListener(prefersDarkListener);
      }
    }
  }

  function stopTheme() {
    if (stopThemeWatch) {
      stopThemeWatch();
      stopThemeWatch = null;
    }
    if (prefersDarkMedia && prefersDarkListener) {
      if (typeof prefersDarkMedia.removeEventListener === "function") {
        prefersDarkMedia.removeEventListener("change", prefersDarkListener);
      } else if (typeof prefersDarkMedia.removeListener === "function") {
        prefersDarkMedia.removeListener(prefersDarkListener);
      }
    }
    prefersDarkMedia = null;
    prefersDarkListener = null;
  }

  return {
    initTheme,
    stopTheme,
  };
}
