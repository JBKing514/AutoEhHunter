export function createControlModule(ctx) {
  const {
    schedule,
    tasks,
    t,
    notify,
    formatDateTime,
    getSchedule,
    updateSchedule,
    runTask,
    getTasks,
  } = ctx;

  let tasksEventSource = null;

  function short(id) {
    return id ? String(id).slice(0, 8) : "-";
  }

  function schedulerLabel(key) {
    return t(`scheduler.${key}`);
  }

  function statusColor(status) {
    if (status === "running") return "warning";
    if (status === "success") return "success";
    return "error";
  }

  function statusText(status) {
    if (status === "running") return t("task.running");
    if (status === "success") return t("task.success");
    if (status === "timeout") return t("task.timeout");
    return t("task.failed");
  }

  async function loadScheduleData() {
    const data = await getSchedule();
    schedule.value = data.schedule || {};
  }

  async function saveSchedule() {
    await updateSchedule(schedule.value);
    notify(t("control.scheduler.saved"));
  }

  async function triggerTask(task, args = "") {
    await runTask(task, args);
    notify(`${t("task.start")}: ${task}`);
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
        tasks.value = (payload.tasks || []).sort((a, b) => String(b.started_at || "").localeCompare(String(a.started_at || ""))).slice(0, 200);
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

  return {
    schedule,
    tasks,
    t,
    formatDateTime,
    short,
    schedulerLabel,
    statusColor,
    statusText,
    loadScheduleData,
    saveSchedule,
    triggerTask,
    loadTasks,
    setupTaskStream,
    closeTaskStream,
  };
}
