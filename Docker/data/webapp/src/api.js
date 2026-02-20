import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

export async function getHealth() {
  const { data } = await api.get("/health");
  return data;
}

export async function getConfig() {
  const { data } = await api.get("/config");
  return data;
}

export async function updateConfig(values) {
  const { data } = await api.put("/config", { values });
  return data;
}

export async function getConfigSchema() {
  const { data } = await api.get("/config/schema");
  return data;
}

export async function getSchedule() {
  const { data } = await api.get("/schedule");
  return data;
}

export async function updateSchedule(schedule) {
  const { data } = await api.put("/schedule", { schedule });
  return data;
}

export async function runTask(task, args = "") {
  const { data } = await api.post("/task/run", { task, args });
  return data;
}

export async function getTasks() {
  const { data } = await api.get("/tasks");
  return data;
}

export async function getAuditHistory(params = {}) {
  const { data } = await api.get("/audit/history", {
    params: {
      limit: 300,
      offset: 0,
      task: "",
      status: "",
      keyword: "",
      ...params,
    },
  });
  return data;
}

export async function getAuditLogs() {
  const { data } = await api.get("/audit/logs");
  return data;
}

export async function getAuditTasks() {
  const { data } = await api.get("/audit/tasks");
  return data;
}

export async function getAuditLogContent(name) {
  const { data } = await api.get(`/audit/logs/${encodeURIComponent(name)}`);
  return data;
}

export async function getAuditLogTail(name, offset = 0, chunkSize = 8000) {
  const { data } = await api.get(`/audit/logs/${encodeURIComponent(name)}/tail`, {
    params: { offset, chunk_size: chunkSize },
  });
  return data;
}

export async function getXpMap(params) {
  const { data } = await api.get("/xp-map", { params });
  return data;
}
