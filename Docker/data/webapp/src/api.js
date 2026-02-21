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
      limit: 15,
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

export async function getHomeHistory(params = {}) {
  const { data } = await api.get("/home/history", { params });
  return data;
}

export async function getHomeRecommend(params = {}) {
  const { data } = await api.get("/home/recommend", { params });
  return data;
}

export async function searchByImage(payload = {}) {
  const { data } = await api.post("/home/search/image", payload);
  return data;
}

export async function searchByImageUpload(file, payload = {}) {
  const form = new FormData();
  form.append("file", file);
  Object.entries(payload || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null) form.append(k, String(v));
  });
  const { data } = await api.post("/home/search/image/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120000,
  });
  return data;
}

export async function getHomeTagSuggest(params = {}) {
  const { data } = await api.get("/home/filter/tag-suggest", { params });
  return data;
}

export async function searchByTextPlaceholder(payload = {}) {
  const { data } = await api.post("/home/search/text", payload);
  return data;
}

export async function searchByText(payload = {}) {
  const { data } = await api.post("/home/search/text", payload);
  return data;
}

export async function searchHybridPlaceholder(payload = {}) {
  const { data } = await api.post("/home/search/hybrid", payload);
  return data;
}

export async function searchHybrid(payload = {}) {
  const { data } = await api.post("/home/search/hybrid", payload);
  return data;
}

export async function getThumbCacheStats() {
  const { data } = await api.get("/cache/thumbs");
  return data;
}

export async function clearThumbCache() {
  const { data } = await api.delete("/cache/thumbs");
  return data;
}

export async function getTranslationStatus() {
  const { data } = await api.get("/translation/status");
  return data;
}

export async function uploadTranslationFile(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/translation/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120000,
  });
  return data;
}

export async function getModelStatus() {
  const { data } = await api.get("/models/status");
  return data;
}

export async function downloadSiglip(params = {}) {
  const { data } = await api.post("/models/siglip/download", null, { params });
  return data;
}

export async function getSiglipDownloadStatus(taskId) {
  const { data } = await api.get(`/models/siglip/download/${encodeURIComponent(taskId)}`);
  return data;
}

export async function clearSiglip() {
  const { data } = await api.delete("/models/siglip");
  return data;
}

export async function clearRuntimeDeps() {
  const { data } = await api.delete("/models/runtime-deps");
  return data;
}

export async function getChatHistory(params = {}) {
  const { data } = await api.get("/chat/history", { params });
  return data;
}

export async function sendChatMessage(payload = {}) {
  const { data } = await api.post("/chat/message", payload);
  return data;
}
