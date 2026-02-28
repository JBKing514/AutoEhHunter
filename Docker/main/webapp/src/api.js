import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

let csrfToken = "";

export function setCsrfToken(token) {
  csrfToken = String(token || "");
}

api.interceptors.request.use((config) => {
  const method = String(config?.method || "get").toUpperCase();
  if (csrfToken && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const headers = config.headers || {};
    headers["x-csrf-token"] = csrfToken;
    config.headers = headers;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("aeh-auth-required"));
    }
    try {
      const data = error?.response?.data;
      if (data && typeof data === "object") {
        const detailObj = data.detail;
        const detail = String(
          (detailObj && typeof detailObj === "object" && detailObj.message) || detailObj || error?.message || "request failed",
        ).trim();
        const tb = String(
          data.traceback || (detailObj && typeof detailObj === "object" ? detailObj.traceback : "") || "",
        ).trim();
        if (tb) {
          data.detail = `${detail}\n\nTraceback:\n${tb}`;
          error.message = data.detail;
        } else if (detail) {
          error.message = detail;
        }
      }
    } catch {
      // ignore error decoration failures
    }
    return Promise.reject(error);
  },
);

export async function getHealth() {
  const { data } = await api.get("/health", {
    timeout: 8000,
    params: { t: Date.now() },
    headers: { "Cache-Control": "no-cache" },
  });
  return data;
}

export async function getAuthBootstrap() {
  const { data } = await api.get("/auth/bootstrap");
  return data;
}

export async function registerAdmin(username, password) {
  const { data } = await api.post("/auth/register-admin", { username, password });
  return data;
}

export async function login(username, password) {
  const { data } = await api.post("/auth/login", { username, password });
  return data;
}

export async function logout() {
  const { data } = await api.post("/auth/logout");
  return data;
}

export async function getMe() {
  const { data } = await api.get("/auth/me");
  return data;
}

export async function getCsrfToken() {
  const { data } = await api.get("/auth/csrf");
  return data;
}

export async function updateProfile(username) {
  const { data } = await api.put("/auth/profile", { username });
  return data;
}

export async function changePassword(oldPassword, newPassword, username = "") {
  const { data } = await api.put("/auth/password", { old_password: oldPassword, new_password: newPassword, username });
  return data;
}

export async function verifyPassword(username, password) {
  const { data } = await api.post("/auth/verify-password", { username, password });
  return data;
}

export async function deleteAccount(password) {
  const { data } = await api.delete("/auth/account", { data: { password } });
  return data;
}

export async function getSetupStatus() {
  const { data } = await api.get("/setup/status");
  return data;
}

export async function validateSetupDb(payload = {}) {
  const { data } = await api.post("/setup/validate-db", payload);
  return data;
}

export async function validateSetupLrr(payload = {}) {
  const { data } = await api.post("/setup/validate-lrr", payload);
  return data;
}

export async function completeSetup() {
  const { data } = await api.post("/setup/complete");
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

export async function downloadAppConfigBackup() {
  const res = await api.get("/config/app-config/download", { responseType: "blob" });
  return res.data;
}

export async function restoreAppConfigBackup(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/config/app-config/restore", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120000,
  });
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

export async function stopTask(taskId) {
  const { data } = await api.post("/task/stop", { task_id: String(taskId || "") });
  return data;
}

export async function clearEhCheckpoint() {
  const { data } = await api.delete("/eh/checkpoint");
  return data;
}

export async function clearWorksDuplicates() {
  const { data } = await api.post("/db/works/deduplicate");
  return data;
}

export async function clearReadEvents() {
  const { data } = await api.delete("/db/read-events");
  return data;
}

export async function getDevSchemaStatus() {
  const { data } = await api.get("/dev/schema");
  return data;
}

export async function uploadDevSchema(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/dev/schema/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120000,
  });
  return data;
}

export async function injectDevSchema() {
  const { data } = await api.post("/dev/schema/inject");
  return data;
}

export async function getTasks() {
  const { data } = await api.get("/tasks");
  return data;
}

export async function getVisualTaskStatus() {
  const { data } = await api.get("/visual-task/status");
  return data;
}

export async function stopVisualTask() {
  const { data } = await api.post("/visual-task/stop");
  return data;
}

export async function enableVisualTask() {
  const { data } = await api.post("/visual-task/enable");
  return data;
}

export async function disableVisualTask() {
  const { data } = await api.post("/visual-task/disable");
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

export async function clearAuditLogs() {
  const { data } = await api.delete("/audit/logs");
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

export async function getHomeLocal(params = {}) {
  const { data } = await api.get("/home/local", { params });
  return data;
}

export async function getHomeRecommend(params = {}) {
  const { data } = await api.get("/home/recommend", { params });
  return data;
}

export async function getRecommendItems(params = {}) {
  const { data } = await api.get("/recommend/items", { params });
  return data;
}

export async function postRecommendTouch(payload = {}) {
  const { data } = await api.post("/home/recommend/touch", payload || {});
  return data;
}

export async function postRecommendTouchKeepalive(payload = {}) {
  try {
    const res = await fetch("/api/home/recommend/touch", {
      method: "POST",
      credentials: "include",
      keepalive: true,
      headers: {
        "Content-Type": "application/json",
        "x-csrf-token": csrfToken || "",
      },
      body: JSON.stringify(payload || {}),
    });
    if (res.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("aeh-auth-required"));
    }
    if (!res.ok) {
      throw new Error(`touch failed: HTTP ${res.status}`);
    }
    return await res.json();
  } catch {
    return postRecommendTouch(payload);
  }
}

export async function clearRecommendTouches() {
  const { data } = await api.delete("/home/recommend/touch");
  return data;
}

export async function clearRecommendProfile() {
  const { data } = await api.delete("/home/recommend/profile");
  return data;
}

export async function postRecommendImpressions(payload = {}) {
  const { data } = await api.post("/home/recommend/impressions", payload || {});
  return data;
}

export async function postRecommendDislike(payload = {}) {
  const { data } = await api.post("/home/recommend/dislike", payload || {});
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

export async function getReaderManifest(arcid) {
  const { data } = await api.get(`/reader/${encodeURIComponent(String(arcid || ""))}/manifest`);
  return data;
}

export async function postReaderReadEvent(payload = {}) {
  const { data } = await api.post("/reader/read-event", payload || {});
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

export async function getProviderModels(baseUrl, apiKey = "") {
  const { data } = await api.post("/provider/models", { base_url: baseUrl || "", api_key: apiKey || "" });
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

export async function streamChatMessage(payload = {}, onEvent) {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "x-csrf-token": csrfToken || "",
    },
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok || !res.body) {
    throw new Error(`stream failed: HTTP ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const raw = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 2);
      if (!raw.startsWith("data:")) continue;
      const txt = raw.slice(5).trim();
      if (!txt) continue;
      try {
        const evt = JSON.parse(txt);
        if (typeof onEvent === "function") onEvent(evt);
      } catch {
        // ignore malformed chunk
      }
    }
  }
}

export async function editChatMessage(payload = {}) {
  const { data } = await api.put("/chat/message/edit", payload);
  return data;
}

export async function deleteChatMessage(session_id, index) {
  const { data } = await api.delete("/chat/message", { data: { session_id, index } });
  return data;
}

export async function listChatSessions() {
  const { data } = await api.get("/chat/sessions");
  return data;
}

export async function deleteChatSession(session_id) {
  const { data } = await api.delete("/chat/session", { params: { session_id } });
  return data;
}

export async function sendChatMessageUpload(file, payload = {}) {
  const form = new FormData();
  form.append("file", file);
  Object.entries(payload || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null) form.append(k, String(v));
  });
  const { data } = await api.post("/chat/message/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 180000,
  });
  return data;
}

export async function getSkills() {
  const { data } = await api.get("/skills");
  return data;
}

export async function uploadSkillPlugin(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/skills/plugins", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120000,
  });
  return data;
}
