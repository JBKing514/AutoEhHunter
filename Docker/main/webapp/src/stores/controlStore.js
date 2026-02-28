import { ref } from "vue";
import { defineStore } from "pinia";
import { clearEhCheckpoint, getHealth, getSchedule, getTasks, runTask, updateSchedule } from "../api";

export const useControlStore = defineStore("control", () => {
  const health = ref({ database: {}, services: {} });
  const healthLoading = ref(false);
  const schedule = ref({});
  const tasks = ref([]);

  let _t = (k) => k;
  let _notify = () => {};
  let _formatDateTime = (v) => String(v || "-");
  let dashboardTimer = null;
  let tasksEventSource = null;
  const taskStatusSeen = new Map();

  function init(deps = {}) {
    if (typeof deps.t === "function") _t = deps.t;
    if (typeof deps.notify === "function") _notify = deps.notify;
    if (typeof deps.formatDateTime === "function") _formatDateTime = deps.formatDateTime;
  }

  function t(key, vars = {}) {
    return _t(key, vars);
  }

  function formatDateTime(value) {
    return _formatDateTime(value);
  }

  function formatDateMinute(value) {
    if (!value || value === "-") return "-";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value).slice(0, 16).replace("T", " ");
    return d.toLocaleString(undefined, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }

  function short(id) {
    return id ? String(id).slice(0, 8) : "-";
  }

  function schedulerLabel(key) {
    return t(`scheduler.${key}`);
  }

  function statusColor(status) {
    if (status === "running") return "warning";
    if (status === "stopping") return "warning";
    if (status === "stopped") return "info";
    if (status === "success") return "success";
    return "error";
  }

  function statusText(status) {
    if (status === "running") return t("task.running");
    if (status === "stopping") return t("task.stopping");
    if (status === "stopped") return t("task.stopped");
    if (status === "success") return t("task.success");
    if (status === "timeout") return t("task.timeout");
    return t("task.failed");
  }

  async function loadDashboard() {
    healthLoading.value = true;
    try {
      health.value = await getHealth();
    } catch (e) {
      const reason = String(e?.response?.data?.detail || e?.message || e || "unreachable");
      health.value = {
        ...(health.value || {}),
        services: {
          ...(health.value?.services || {}),
          lrr: {
            ok: false,
            message: reason,
          },
          llm: {
            ok: false,
            message: reason,
          },
        },
      };
    } finally {
      healthLoading.value = false;
    }
  }

  async function loadScheduleData() {
    const data = await getSchedule();
    schedule.value = data.schedule || {};
  }

  async function saveSchedule() {
    await updateSchedule(schedule.value);
    _notify(t("control.scheduler.saved"));
  }

  async function triggerTask(task, args = "") {
    await runTask(task, args);
    _notify(`${t("task.start")}: ${task}`);
  }

  async function clearEhCheckpointNow() {
    try {
      const res = await clearEhCheckpoint();
      _notify(res.removed ? t("control.checkpoint.cleared") : t("control.checkpoint.none"), res.removed ? "success" : "info");
    } catch (e) {
      _notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  async function loadTasks() {
    const data = await getTasks();
    tasks.value = data.tasks || [];
  }

  async function setupTaskStream() {
    if (tasksEventSource) tasksEventSource.close();
    tasksEventSource = new EventSource("/api/tasks/stream");
    tasksEventSource.onmessage = (evt) => {
      try {
        const payload = JSON.parse(evt.data || "{}");
        const next = (payload.tasks || []).sort((a, b) => String(b.started_at || "").localeCompare(String(a.started_at || ""))).slice(0, 200);
        tasks.value = next;
        next.forEach((task) => {
          const id = String(task?.task_id || "");
          if (!id) return;
          const status = String(task?.status || "");
          const prev = taskStatusSeen.get(id) || "";
          if (prev !== status && (status === "failed" || status === "timeout")) {
            const hint = String(task?.hint || "").trim();
            const summary = String(task?.task_summary || task?.error || "").trim();
            _notify(`${t("task.failed")} ${task?.task || ""}${hint ? `\n${hint}` : ""}${summary ? `\n${summary}` : ""}`, "warning");
          }
          taskStatusSeen.set(id, status);
        });
      } catch {
        // ignore
      }
    };
  }

  function closeTaskStream() {
    if (tasksEventSource) {
      tasksEventSource.close();
      tasksEventSource = null;
    }
  }

  async function startControlPolling() {
    await Promise.all([loadDashboard(), loadScheduleData(), loadTasks()]);
    await setupTaskStream();
    if (dashboardTimer) clearInterval(dashboardTimer);
    dashboardTimer = setInterval(() => {
      loadDashboard().catch(() => null);
    }, 10000);
  }

  function stopControlPolling() {
    if (dashboardTimer) {
      clearInterval(dashboardTimer);
      dashboardTimer = null;
    }
    closeTaskStream();
  }

  return {
    health,
    healthLoading,
    schedule,
    tasks,
    init,
    t,
    formatDateTime,
    formatDateMinute,
    short,
    schedulerLabel,
    statusColor,
    statusText,
    loadDashboard,
    loadScheduleData,
    saveSchedule,
    triggerTask,
    clearEhCheckpointNow,
    loadTasks,
    setupTaskStream,
    closeTaskStream,
    startControlPolling,
    stopControlPolling,
  };
});
