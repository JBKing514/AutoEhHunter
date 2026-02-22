import { computed, ref, watch } from "vue";
import { defineStore } from "pinia";
import { clearAuditLogs, getAuditHistory, getAuditLogContent, getAuditLogTail, getAuditLogs, getAuditTasks } from "../api";

export const useAuditStore = defineStore("audit", () => {
  const auditRows = ref([]);
  const auditLogs = ref([]);
  const taskOptions = ref([]);
  const selectedLog = ref("");
  const selectedLogContent = ref("");
  const logOffset = ref(0);
  const logAutoStream = ref(true);
  const logHighlight = ref("");
  const auditFilter = ref({ task: "", status: "", keyword: "", start_date: "", end_date: "", limit: 15, offset: 0 });
  const auditPage = ref(1);
  const auditTotal = ref(0);

  let _t = (k, _vars = {}) => k;
  let _notify = () => {};
  let _formatDateTime = (v) => String(v || "-");
  let _onEhFetchLag = null;
  let logTimer = null;

  const auditPages = computed(() => {
    const per = Math.max(1, Number(auditFilter.value.limit || 15));
    return Math.max(1, Math.ceil(Number(auditTotal.value || 0) / per));
  });

  const highlightedLogHtml = computed(() => {
    const raw = String(selectedLogContent.value || "");
    const escaped = escapeHtml(raw);
    const kw = String(logHighlight.value || "").trim();
    if (!kw) return escaped.replace(/\n/g, "<br>");
    const re = new RegExp(escapeRegExp(kw), "gi");
    return escaped.replace(re, (m) => `<mark>${m}</mark>`).replace(/\n/g, "<br>");
  });

  function init(deps = {}) {
    if (typeof deps.t === "function") _t = deps.t;
    if (typeof deps.notify === "function") _notify = deps.notify;
    if (typeof deps.formatDateTime === "function") _formatDateTime = deps.formatDateTime;
    if (typeof deps.onEhFetchLag === "function") _onEhFetchLag = deps.onEhFetchLag;
  }

  function t(key, vars = {}) {
    return _t(key, vars);
  }

  function formatDateTime(value) {
    return _formatDateTime(value);
  }

  function escapeHtml(s) {
    return String(s || "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
  }

  function escapeRegExp(s) {
    return String(s || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function logNameFromPath(logFile) {
    if (!logFile) return "";
    return String(logFile).split(/[\\/]/).pop() || "";
  }

  async function loadLog(name = "") {
    const target = name || selectedLog.value;
    if (!target) return;
    selectedLog.value = target;
    const data = await getAuditLogContent(target);
    selectedLogContent.value = data.content || "";
    logOffset.value = selectedLogContent.value.length;
  }

  async function selectAuditRow(row) {
    if (!row) return;
    const name = logNameFromPath(row.log_file);
    if (!name) return;
    selectedLog.value = name;
    await loadLog(name);
  }

  function detectEhFetchLagNotice() {
    const rows = (auditRows.value || []).filter((r) => String(r.task || "") === "eh_fetch").slice(0, 8);
    if (!rows.length) return;
    let hit = 0;
    rows.forEach((r) => {
      const s = `${r.stdout_tail || ""}\n${r.stderr_tail || ""}\n${r.task_summary || ""}`;
      if (/checkpoint_reached\s*=\s*False/i.test(s) && /checkpoint_advanced\s*=\s*False/i.test(s) && /stop_reason\s*=\s*max_pages/i.test(s)) {
        hit += 1;
      }
    });
    if (hit >= 2) {
      _notify(_t("notice.eh_fetch_lag.toast"), "warning");
      if (_onEhFetchLag) {
        _onEhFetchLag({
          title: _t("notice.eh_fetch_lag.title"),
          text: _t("notice.eh_fetch_lag.body"),
        });
      }
    }
  }

  async function loadAudit() {
    const page = Math.max(1, Number(auditPage.value || 1));
    const limit = Math.max(1, Number(auditFilter.value.limit || 15));
    const offset = (page - 1) * limit;
    const history = await getAuditHistory({ ...auditFilter.value, limit, offset });
    auditRows.value = history.rows || [];
    auditTotal.value = Number(history.total || 0);

    const logs = await getAuditLogs();
    auditLogs.value = logs.logs || [];
    const tasksRes = await getAuditTasks();
    taskOptions.value = tasksRes.tasks || [];

    if (!selectedLog.value && auditRows.value.length) {
      await selectAuditRow(auditRows.value[0]);
    } else if (!selectedLog.value && auditLogs.value.length) {
      selectedLog.value = auditLogs.value[0];
      await loadLog(selectedLog.value);
    }
    detectEhFetchLagNotice();
  }

  function resetAuditFilter() {
    auditFilter.value = { task: "", status: "", keyword: "", start_date: "", end_date: "", limit: 15, offset: 0 };
    auditPage.value = 1;
    loadAudit().catch(() => null);
  }

  function applyAuditFilter() {
    auditPage.value = 1;
    loadAudit().catch(() => null);
  }

  async function clearAuditLogsNow() {
    try {
      const res = await clearAuditLogs();
      _notify(_t("audit.log.cleared", { n: Number(res.deleted || 0) }), "success");
      selectedLog.value = "";
      selectedLogContent.value = "";
      await loadAudit();
    } catch (e) {
      _notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  async function pollLogTail() {
    if (!logAutoStream.value || !selectedLog.value) return;
    const data = await getAuditLogTail(selectedLog.value, logOffset.value, 12000);
    if (data.chunk) {
      selectedLogContent.value += data.chunk;
      if (selectedLogContent.value.length > 200000) {
        selectedLogContent.value = selectedLogContent.value.slice(-200000);
      }
    }
    logOffset.value = Number(data.next_offset || logOffset.value);
  }

  function startLogTailPolling() {
    if (!logAutoStream.value) return;
    if (logTimer) return;
    logTimer = setInterval(() => {
      pollLogTail().catch(() => null);
    }, 1200);
  }

  function stopLogTailPolling() {
    if (!logTimer) return;
    clearInterval(logTimer);
    logTimer = null;
  }

  watch(auditPage, () => {
    loadAudit().catch(() => null);
  });

  watch(logAutoStream, (enabled) => {
    if (enabled) startLogTailPolling();
    else stopLogTailPolling();
  });

  return {
    auditRows,
    auditLogs,
    taskOptions,
    selectedLog,
    selectedLogContent,
    logOffset,
    logAutoStream,
    logHighlight,
    auditFilter,
    auditPage,
    auditTotal,
    auditPages,
    highlightedLogHtml,
    init,
    t,
    formatDateTime,
    loadAudit,
    clearAuditLogsNow,
    resetAuditFilter,
    applyAuditFilter,
    logNameFromPath,
    selectAuditRow,
    loadLog,
    pollLogTail,
    startLogTailPolling,
    stopLogTailPolling,
  };
});
