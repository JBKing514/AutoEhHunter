import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getInitialLang, setLang, t as tr } from "../i18n";
import brandLogo from "../ico/AutoEhHunterLogo_128.png";
import { useSettingsStore } from "./settingsStore";
import { useAppStore } from "./appStore";

const TAB_ROUTE_MAP = {
  dashboard: "/dashboard",
  chat: "/chat",
  control: "/control",
  audit: "/audit",
  xp: "/xp",
  settings: "/settings/general",
};

export const useLayoutStore = defineStore("layout", () => {
  const settingsStore = useSettingsStore();
  const appStore = useAppStore();

  const drawer = ref(true);
  const rail = ref(false);
  const tab = ref("dashboard");
  const lang = ref(getInitialLang());
  const notices = ref([]);
  const pageZoomOptions = [
    { title: "90%", value: 90 },
    { title: "100%", value: 100 },
    { title: "110%", value: 110 },
    { title: "120%", value: 120 },
    { title: "130%", value: 130 },
  ];
  const pageZoom = ref(100);

  const langOptions = [
    { title: "简体中文", value: "zh" },
    { title: "English", value: "en" },
  ];

  let _navigate = null;
  let _logout = null;

  function clampZoom(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return 100;
    return Math.max(90, Math.min(130, Math.round(n / 10) * 10));
  }

  function applyPageZoom() {
    if (typeof document === "undefined") return;
    document.documentElement.style.setProperty("--aeh-page-zoom", String(pageZoom.value / 100));
  }

  if (typeof window !== "undefined") {
    pageZoom.value = clampZoom(window.localStorage.getItem("autoeh_page_zoom") || 100);
    applyPageZoom();
  }

  const navItems = computed(() => {
    if (appStore.isRecoveryMode) {
      return [
        { key: "settings", title: "tab.settings", icon: "mdi-cog-outline" },
      ];
    }
    const base = [
      { key: "dashboard", title: "tab.dashboard", icon: "mdi-view-dashboard-outline" },
      { key: "control", title: "tab.control", icon: "mdi-console" },
      { key: "audit", title: "tab.audit", icon: "mdi-clipboard-text-clock-outline" },
      { key: "xp", title: "tab.xp_map", icon: "mdi-chart-bubble" },
      { key: "settings", title: "tab.settings", icon: "mdi-cog-outline" },
    ];
    if (settingsStore.llmReady) {
      base.splice(1, 0, { key: "chat", title: "tab.chat", icon: "mdi-chat-processing-outline" });
    }
    return base;
  });

  const currentTitleKey = computed(() => navItems.value.find((x) => x.key === tab.value)?.title || "tab.dashboard");

  const themeModeIcon = computed(() => {
    const mode = String(settingsStore.config.DATA_UI_THEME_MODE || "system");
    if (mode === "light") return "mdi-weather-sunny";
    if (mode === "dark") return "mdi-weather-night";
    return "mdi-brightness-auto";
  });

  function init(deps = {}) {
    if (typeof deps.navigate === "function") _navigate = deps.navigate;
    if (typeof deps.logout === "function") _logout = deps.logout;
  }

  function t(key, vars = {}) {
    return tr(lang.value, key, vars);
  }

  function setLangValue(next) {
    lang.value = setLang(next);
  }

  function pathForTab(key) {
    return TAB_ROUTE_MAP[key] || "/dashboard";
  }

  function routeToTab(pathname) {
    if (pathname.startsWith("/settings")) return "settings";
    if (pathname.startsWith("/chat")) return "chat";
    if (pathname.startsWith("/control")) return "control";
    if (pathname.startsWith("/audit")) return "audit";
    if (pathname.startsWith("/xp")) return "xp";
    return "dashboard";
  }

  function goTab(key) {
    tab.value = String(key || "dashboard");
    if (_navigate) _navigate(pathForTab(tab.value));
  }

  function cycleThemeMode() {
    const now = String(settingsStore.config.DATA_UI_THEME_MODE || "system");
    if (now === "system") settingsStore.config.DATA_UI_THEME_MODE = "light";
    else if (now === "light") settingsStore.config.DATA_UI_THEME_MODE = "dark";
    else settingsStore.config.DATA_UI_THEME_MODE = "system";
  }

  function setPageZoom(next) {
    pageZoom.value = clampZoom(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("autoeh_page_zoom", String(pageZoom.value));
    }
    applyPageZoom();
  }

  function pushNotice(type, title, text) {
    const id = `${type}-${Date.now()}`;
    notices.value = (notices.value || []).filter((x) => x.type !== type);
    notices.value.unshift({ id, type, title, text, ts: Date.now() });
    notices.value = notices.value.slice(0, 100);
  }

  function dismissNotice(id) {
    notices.value = (notices.value || []).filter((x) => x.id !== id);
  }

  function clearAllNotices() {
    notices.value = [];
  }

  async function logoutNow() {
    if (_logout) await _logout();
  }

  return {
    drawer,
    rail,
    tab,
    lang,
    notices,
    pageZoom,
    pageZoomOptions,
    brandLogo,
    langOptions,
    navItems,
    currentTitleKey,
    themeModeIcon,
    init,
    t,
    setLangValue,
    pathForTab,
    routeToTab,
    goTab,
    cycleThemeMode,
    setPageZoom,
    pushNotice,
    dismissNotice,
    clearAllNotices,
    logoutNow,
  };
});
