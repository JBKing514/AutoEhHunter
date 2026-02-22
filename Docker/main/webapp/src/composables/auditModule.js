export function createAuditModule(ctx) {
  const {
    auditRows,
    auditLogs,
    taskOptions,
    selectedLog,
    selectedLogContent,
    logOffset,
    logAutoStream,
    auditFilter,
    auditPage,
    auditTotal,
    notify,
    t,
    getAuditHistory,
    getAuditLogs,
    getAuditTasks,
    getAuditLogContent,
    getAuditLogTail,
    clearAuditLogs,
    detectEhFetchLagNotice,
  } = ctx;

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

  async function clearAuditLogsNow() {
    try {
      const res = await clearAuditLogs();
      notify(t("audit.log.cleared", { n: Number(res.deleted || 0) }), "success");
      selectedLog.value = "";
      selectedLogContent.value = "";
      await loadAudit();
    } catch (e) {
      notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  function resetAuditFilter() {
    auditFilter.value = { task: "", status: "", keyword: "", start_date: "", end_date: "", limit: 15, offset: 0 };
    auditPage.value = 1;
    loadAudit();
  }

  function applyAuditFilter() {
    auditPage.value = 1;
    loadAudit();
  }

  function logNameFromPath(logFile) {
    if (!logFile) return "";
    return String(logFile).split(/[\\/]/).pop() || "";
  }

  async function selectAuditRow(row) {
    if (!row) return;
    const name = logNameFromPath(row.log_file);
    if (!name) return;
    selectedLog.value = name;
    await loadLog(name);
  }

  async function loadLog(name = "") {
    const target = name || selectedLog.value;
    if (!target) return;
    selectedLog.value = target;
    const data = await getAuditLogContent(target);
    selectedLogContent.value = data.content || "";
    logOffset.value = selectedLogContent.value.length;
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

  return {
    loadAudit,
    clearAuditLogsNow,
    resetAuditFilter,
    applyAuditFilter,
    logNameFromPath,
    selectAuditRow,
    loadLog,
    pollLogTail,
  };
}
