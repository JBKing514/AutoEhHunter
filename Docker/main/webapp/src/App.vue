<template>
  <v-app>
    <auth-gate
      :logo="brandLogo"
      :t="t"
    />
    <setup-wizard :t="t" />

    <RouterView />

    <v-dialog v-model="chatExploreOpen" max-width="980">
      <v-card class="pa-3" variant="flat">
        <div class="d-flex align-center justify-space-between mb-2">
          <div class="text-subtitle-1">{{ chatExplorePayload?.title || t('chat.explore.title') }}</div>
          <v-btn size="small" icon="mdi-close" variant="text" @click="chatExploreOpen=false" />
        </div>
        <v-row>
          <v-col v-for="it in (chatExplorePayload?.items || [])" :key="`chat-exp-${it.id}`" cols="6" sm="4" md="3" lg="2">
            <v-card class="home-card compact" variant="flat" @click="openChatExploreItem()">
              <div class="cover-ph">
                <div v-if="it.thumb_url" class="cover-bg-blur" :style="{ backgroundImage: `url(${it.thumb_url})` }" />
                <img v-if="it.thumb_url" :src="it.thumb_url" alt="cover" class="cover-img" loading="lazy" />
                <v-icon v-else size="24">mdi-image-outline</v-icon>
              </div>
              <div class="cover-title-overlay">{{ it.title || '-' }}</div>
            </v-card>
          </v-col>
        </v-row>
      </v-card>
    </v-dialog>

    <input ref="chatImageInputRef" type="file" accept="image/*" class="d-none" @change="onChatImagePicked" />
    <v-snackbar v-model="toast.show" :color="toast.color" timeout="3000">{{ toast.text }}</v-snackbar>
  </v-app>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import AuthGate from "./components/AuthGate.vue";
import SetupWizard from "./components/SetupWizard.vue";
import { useLayoutStore } from "./stores/layoutStore";
import { useDashboardStore } from "./stores/dashboardStore";
import { useChatStore } from "./stores/chatStore";
import { useControlStore } from "./stores/controlStore";
import { useAuditStore } from "./stores/auditStore";
import { useXpStore } from "./stores/xpStore";
import { useSettingsStore } from "./stores/settingsStore";
import { useAppStore } from "./stores/appStore";
import { useToastStore } from "./stores/useToastStore";
import { useThemeManager } from "./composables/useThemeManager";
import { formatDateMinute, formatDateTime } from "./utils/helpers";
import { getTasks, getVisualTaskStatus, stopTask, stopVisualTask } from "./api";
import brandLogo from "./ico/AutoEhHunterLogo_128.png";

const router = useRouter();
const route = useRoute();
const layoutStore = useLayoutStore();
const dashboardStore = useDashboardStore();
const chatStore = useChatStore();
const controlStore = useControlStore();
const auditStore = useAuditStore();
const xpStore = useXpStore();
const settingsStore = useSettingsStore();
const appStore = useAppStore();
const toastStore = useToastStore();

const {
  updateViewportFlags,
  onWindowScroll,
  clearTouchPreviewTimer,
  resetHomeFeed,
  bindHomeInfiniteScroll,
  clearHomeObserver,
} = dashboardStore;

const {
  config,
  settingsTab,
  llmReady,
} = storeToRefs(settingsStore);

const {
  chatFabOpen,
  chatImageInputRef,
  chatExploreOpen,
  chatExplorePayload,
} = storeToRefs(chatStore);

const {
  ensureChatSession,
  loadChatHistory,
  onChatImagePicked,
  openChatExploreItem,
} = chatStore;

const {
  showAuthGate: authGateOpen,
  authReady,
} = storeToRefs(appStore);

const toast = toastStore;
let authRequiredListener = null;
let windowScrollListener = null;
let windowResizeListener = null;
let mainScrollEl = null;
let visualTaskTimer = null;
let taskNoticeTimer = null;
let appInitialized = false;

function t(key, vars = {}) {
  return layoutStore.t(key, vars);
}

function notify(text, color = "success") {
  toastStore.open(text, color);
}

function visualTaskText(status = {}) {
  const table = String(status?.table || "");
  const current = Math.max(0, Number(status?.current || 0));
  const total = Math.max(current, Number(status?.total || 0));
  if (table === "works") return t("notice.visual_task.works_running", { current, total });
  if (table === "eh_works") return t("notice.visual_task.eh_running", { current, total });
  return t("notice.visual_task.idle");
}

function stopVisualTaskMonitor() {
  if (visualTaskTimer) {
    clearInterval(visualTaskTimer);
    visualTaskTimer = null;
  }
}

function stopTaskNoticeMonitor() {
  if (taskNoticeTimer) {
    clearInterval(taskNoticeTimer);
    taskNoticeTimer = null;
  }
}

function taskNoticeTitle(task) {
  return t("notice.task.title", { task: String(task || "") || "-" });
}

function taskNoticeText(task = {}) {
  const taskName = String(task?.task || "").trim() || "-";
  const shortId = String(task?.task_id || "").slice(0, 8) || "-";
  return t("notice.task.running", { task: taskName, id: shortId });
}

function clearStaleTaskNotices(runningTaskIds = new Set()) {
  for (const n of layoutStore.notices || []) {
    const type = String(n?.type || "");
    if (!type.startsWith("task_running_")) continue;
    const id = type.slice("task_running_".length);
    if (!runningTaskIds.has(id)) {
      layoutStore.dismissNotice(n.id);
    }
  }
}

async function pollTaskNotices() {
  try {
    const data = await getTasks();
    const all = Array.isArray(data?.tasks) ? data.tasks : [];
    const running = all.filter((x) => ["running", "stopping"].includes(String(x?.status || "")));
    const runningIds = new Set(running.map((x) => String(x?.task_id || "")).filter(Boolean));
    clearStaleTaskNotices(runningIds);
    for (const task of running) {
      const tid = String(task?.task_id || "").trim();
      if (!tid) continue;
      const stopping = String(task?.status || "") === "stopping";
      layoutStore.pushNotice(`task_running_${tid}`, taskNoticeTitle(task?.task), taskNoticeText(task), {
        actionLabel: stopping ? "" : t("notice.task.stop_action"),
        onAction: stopping
          ? null
          : async () => {
              try {
                await stopTask(tid);
                notify(t("notice.task.stop_toast"), "warning");
              } catch (e) {
                notify(String(e?.response?.data?.detail || e), "warning");
              }
            },
      });
    }
  } catch {
    // ignore task polling errors
  }
}

function startTaskNoticeMonitor() {
  stopTaskNoticeMonitor();
  pollTaskNotices().catch(() => null);
  taskNoticeTimer = setInterval(() => {
    pollTaskNotices().catch(() => null);
  }, 2500);
}

async function pollVisualTaskStatus() {
  try {
    const res = await getVisualTaskStatus();
    const status = res?.status || {};
    if (status?.stopped_by_user) {
      layoutStore.dismissNoticeType("visual_task");
      const hasStoppedNotice = (layoutStore.notices || []).some((x) => x.type === "visual_task_stopped");
      if (!hasStoppedNotice) {
        layoutStore.pushNotice("visual_task_stopped", t("notice.visual_task.title"), t("notice.visual_task.stopped"));
      }
      return;
    }
    if (status?.running && status?.phase === "processing") {
      layoutStore.dismissNoticeType("visual_task_stopped");
      layoutStore.pushNotice("visual_task", t("notice.visual_task.title"), visualTaskText(status), {
        actionLabel: t("notice.visual_task.stop_action"),
        onAction: async () => {
          try {
            await stopVisualTask();
            notify(t("notice.visual_task.stop_toast"), "warning");
            layoutStore.dismissNoticeType("visual_task");
            layoutStore.pushNotice("visual_task_stopped", t("notice.visual_task.title"), t("notice.visual_task.stopped"));
          } catch (e) {
            notify(String(e?.response?.data?.detail || e), "warning");
          }
        },
      });
      return;
    }
    layoutStore.dismissNoticeType("visual_task");
  } catch {
    // ignore status polling errors
  }
}

function startVisualTaskMonitor() {
  stopVisualTaskMonitor();
  pollVisualTaskStatus().catch(() => null);
  visualTaskTimer = setInterval(() => {
    pollVisualTaskStatus().catch(() => null);
  }, 2500);
}

function formatDateTimeByUi(value) {
  return formatDateTime(value, layoutStore.lang, config.value.DATA_UI_TIMEZONE);
}

function formatDateMinuteByUi(value) {
  return formatDateMinute(value, layoutStore.lang, config.value.DATA_UI_TIMEZONE);
}

layoutStore.init({
  navigate: (target) => {
    if (route.path !== target) router.push(target).catch(() => null);
  },
  logout: async () => {
    appInitialized = false;
    await appStore.logoutNow();
  },
});

dashboardStore.init({
  configRef: config,
  getConfig: () => config.value,
  getLang: () => layoutStore.lang,
  getTab: () => layoutStore.tab,
  getRail: () => layoutStore.rail,
  t,
  notify,
  formatDateMinute: formatDateMinuteByUi,
});

chatStore.init({
  getLang: () => layoutStore.lang,
  getTab: () => layoutStore.tab,
  setTab: (next) => {
    layoutStore.tab = String(next || "dashboard");
  },
  t,
  notify,
  formatDateMinute: formatDateMinuteByUi,
});

auditStore.init({
  t,
  notify,
  formatDateTime: formatDateTimeByUi,
  onEhFetchLag: ({ title, text }) => {
    layoutStore.pushNotice("eh_fetch_lag", title, text);
  },
});

controlStore.init({
  t,
  notify,
  formatDateTime: formatDateTimeByUi,
});

xpStore.init({
  t,
  getLang: () => layoutStore.lang,
});

settingsStore.init({
  t,
  setLang: layoutStore.setLangValue,
});

appStore.init({
  t,
  afterAuthOk: async () => {
    await initializeAppData();
    if (appStore.isRecoveryMode) {
      router.push("/settings/general");
    }
  },
  afterLogout: () => {
    appInitialized = false;
    controlStore.stopControlPolling();
    stopVisualTaskMonitor();
    stopTaskNoticeMonitor();
  },
});

const { initTheme, stopTheme } = useThemeManager(config);

async function initializeAppData() {
  if (appInitialized) return;
  appInitialized = true;
  ensureChatSession();
  await Promise.all([
    settingsStore.loadConfigData(),
    controlStore.loadDashboard(),
    resetHomeFeed(),
    settingsStore.loadThumbCacheStats(),
    settingsStore.loadTranslationStatus(),
    settingsStore.loadModelStatus(),
    loadChatHistory(),
  ]);
  startVisualTaskMonitor();
  startTaskNoticeMonitor();
  await nextTick();
  bindHomeInfiniteScroll();
}

const settingsPathMap = {
  general: "general",
  eh: "eh",
  data_clean: "data-clean",
  search: "search",
  recommend: "recommend",
  llm: "llm",
  reader: "reader",
  other: "other",
  developer: "developer",
};

const pathSettingsMap = {
  general: "general",
  eh: "eh",
  "data-clean": "data_clean",
  search: "search",
  recommend: "recommend",
  llm: "llm",
  reader: "reader",
  other: "other",
  developer: "developer",
};

watch(llmReady, (ready) => {
  if (ready) return;
  if (layoutStore.tab === "chat") layoutStore.goTab("dashboard");
  chatFabOpen.value = false;
});

watch(
  () => layoutStore.tab,
  (next) => {
    onWindowScroll();
    if (String(route.path || "").startsWith("/login")) return;
    const target = layoutStore.pathForTab(next);
    const inSettings = String(route.path || "").startsWith("/settings");
    if (!(next === "settings" && inSettings) && route.path !== target) {
      router.push(target).catch(() => null);
    }
  },
);

watch(
  () => route.path,
  (pathname) => {
    if (String(pathname || "").startsWith("/login")) return;
    const nextTab = layoutStore.routeToTab(pathname || "");
    if (layoutStore.tab !== nextTab) layoutStore.tab = nextTab;
    if (nextTab === "settings") {
      const seg = String(pathname || "").split("/")[2] || "general";
      settingsTab.value = pathSettingsMap[seg] || "general";
    }
  },
  { immediate: true },
);

watch(settingsTab, (next) => {
  if (layoutStore.tab !== "settings") return;
  const seg = settingsPathMap[next] || "general";
  const target = `/settings/${seg}`;
  if (route.path !== target) router.push(target).catch(() => null);
});

onMounted(async () => {
  initTheme();
  try {
    updateViewportFlags();
    onWindowScroll();
    if (typeof window !== "undefined") {
      windowScrollListener = () => onWindowScroll();
      windowResizeListener = () => updateViewportFlags();
      window.addEventListener("scroll", windowScrollListener, { passive: true });
      window.addEventListener("resize", windowResizeListener);
      mainScrollEl = document?.querySelector?.(".v-main") || null;
      if (mainScrollEl) {
        mainScrollEl.addEventListener("scroll", windowScrollListener, { passive: true });
      }
    }
    await appStore.bootstrap();
    if (typeof window !== "undefined") {
      authRequiredListener = () => appStore.onAuthRequiredEvent();
      window.addEventListener("aeh-auth-required", authRequiredListener);
    }
    if (authReady.value && !authGateOpen.value) {
      await initializeAppData();
    }
  } catch (e) {
    notify(String(e), "error");
  }
});

onBeforeUnmount(() => {
  stopTheme();
  controlStore.stopControlPolling();
  stopVisualTaskMonitor();
  stopTaskNoticeMonitor();
  auditStore.stopLogTailPolling();
  xpStore.clearXpTimer();
  clearTouchPreviewTimer();
  clearHomeObserver();
  if (typeof window !== "undefined" && authRequiredListener) {
    window.removeEventListener("aeh-auth-required", authRequiredListener);
    authRequiredListener = null;
  }
  if (typeof window !== "undefined" && windowScrollListener) {
    window.removeEventListener("scroll", windowScrollListener);
    if (mainScrollEl) {
      mainScrollEl.removeEventListener("scroll", windowScrollListener);
      mainScrollEl = null;
    }
    windowScrollListener = null;
  }
  if (typeof window !== "undefined" && windowResizeListener) {
    window.removeEventListener("resize", windowResizeListener);
    windowResizeListener = null;
  }
});
</script>

<style src="./styles/app.css"></style>
