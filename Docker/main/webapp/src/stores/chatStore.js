import { computed, nextTick, ref } from "vue";
import { defineStore } from "pinia";
import { deleteChatMessage, editChatMessage, getChatHistory, sendChatMessageUpload, streamChatMessage } from "../api";
import { useDashboardStore } from "./dashboardStore";

export const useChatStore = defineStore("chat", () => {
  const chatFabOpen = ref(false);
  const chatSessions = ref([{ id: "default", title: "New Chat", messages: [] }]);
  const chatSessionId = ref("default");
  const chatInput = ref("");
  const chatIntent = ref("auto");
  const chatSending = ref(false);
  const chatStreaming = ref(false);
  const chatStreamStats = ref(null);
  const chatEditIndex = ref(-1);
  const chatEditText = ref("");
  const chatLogRef = ref(null);
  const chatImageFile = ref(null);
  const chatImageInputRef = ref(null);
  const chatExploreOpen = ref(false);
  const chatExplorePayload = ref(null);
  const chatSidebarCollapsed = ref(false);

  const dashboardStore = useDashboardStore();

  let _getLang = () => "zh";
  let _getTab = () => "dashboard";
  let _setTab = null;
  let _t = (k) => k;
  let _notify = () => {};
  let _formatDateMinute = (v) => String(v || "-");

  const activeChatSession = computed(() => {
    const found = (chatSessions.value || []).find((s) => s.id === chatSessionId.value);
    return found || chatSessions.value[0];
  });

  const chatIntentOptions = computed(() => ([
    { title: _t("chat.intent.auto"), value: "auto" },
    { title: _t("chat.intent.chat"), value: "chat" },
    { title: _t("chat.intent.profile"), value: "profile" },
    { title: _t("chat.intent.search"), value: "search" },
    { title: _t("chat.intent.report"), value: "report" },
    { title: _t("chat.intent.recommendation"), value: "recommendation" },
  ]));

  function init(deps = {}) {
    if (typeof deps.getLang === "function") _getLang = deps.getLang;
    if (typeof deps.getTab === "function") _getTab = deps.getTab;
    if (typeof deps.setTab === "function") _setTab = deps.setTab;
    if (typeof deps.t === "function") _t = deps.t;
    if (typeof deps.notify === "function") _notify = deps.notify;
    if (typeof deps.formatDateMinute === "function") _formatDateMinute = deps.formatDateMinute;
  }

  const tab = computed({
    get: () => _getTab(),
    set: (v) => {
      if (_setTab) _setTab(v);
    },
  });

  const homeTab = computed({
    get: () => dashboardStore.homeTab,
    set: (v) => {
      dashboardStore.homeTab = String(v || "history");
    },
  });

  function t(key, vars = {}) {
    return _t(key, vars);
  }

  function itemHoverTags(item) {
    if (typeof dashboardStore.itemHoverTags === "function") {
      return dashboardStore.itemHoverTags(item);
    }
    return [];
  }

  function formatDateMinute(value) {
    return _formatDateMinute(value);
  }

  function scrollChatToBottom(force = false) {
    const el = chatLogRef.value;
    if (!el) return;
    const nearBottom = (el.scrollHeight - el.scrollTop - el.clientHeight) < 80;
    if (force || nearBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }

  function ensureChatSession() {
    if (!chatSessions.value.length) {
      chatSessions.value = [{ id: "default", title: "New Chat", messages: [] }];
      chatSessionId.value = "default";
    }
    if (!chatSessions.value.find((s) => s.id === chatSessionId.value)) {
      chatSessionId.value = chatSessions.value[0].id;
    }
  }

  function createChatSession() {
    const id = `s-${Date.now()}`;
    chatSessions.value.unshift({ id, title: "New Chat", messages: [] });
    chatSessionId.value = id;
  }

  async function loadChatHistory() {
    ensureChatSession();
    try {
      const res = await getChatHistory({ session_id: chatSessionId.value });
      const sess = activeChatSession.value;
      if (sess) sess.messages = res.messages || [];
    } catch {
      // ignore
    }
  }

  async function sendChat(mode = "chat") {
    if (chatSending.value) return;
    const text = String(chatInput.value || "").trim();
    if (!text && !chatImageFile.value && mode === "chat") return;
    ensureChatSession();
    chatSending.value = true;
    chatStreamStats.value = null;
    try {
      const payload = {
        session_id: chatSessionId.value,
        text,
        mode,
        intent: chatIntent.value,
        ui_lang: _getLang(),
        context: { page: _getTab() },
      };
      let res = null;
      if (!chatImageFile.value) {
        const sess = activeChatSession.value;
        const tempUser = { role: "user", text, time: new Date().toISOString() };
        const tempAssistant = { role: "assistant", text: "", time: new Date().toISOString(), stats: null };
        if (sess) {
          sess.messages = [...(sess.messages || []), tempUser, tempAssistant];
          nextTick(() => scrollChatToBottom(true));
        }
        chatStreaming.value = true;
        await streamChatMessage(payload, (evt) => {
          const s = activeChatSession.value;
          if (!s) return;
          const last = s.messages[s.messages.length - 1];
          if (!last || last.role !== "assistant") return;
          if (evt.event === "delta") {
            last.text = `${last.text || ""}${String(evt.delta || "")}`;
            nextTick(() => scrollChatToBottom());
          } else if (evt.event === "done") {
            s.messages = evt.history || s.messages;
            chatStreamStats.value = evt.stats || evt.message?.stats || null;
            nextTick(() => scrollChatToBottom(true));
            res = { history: s.messages };
          }
        });
        chatStreaming.value = false;
      } else {
        res = await sendChatMessageUpload(chatImageFile.value, payload);
      }
      const sess = activeChatSession.value;
      if (sess) {
        sess.messages = (res && res.history) ? res.history : (sess.messages || []);
        if (text && sess.title === "New Chat") sess.title = text.slice(0, 24);
        nextTick(() => scrollChatToBottom(true));
      }
      chatInput.value = "";
      chatImageFile.value = null;
      if (chatImageInputRef.value) chatImageInputRef.value.value = "";
    } catch (e) {
      _notify(String(e?.response?.data?.detail || e), "warning");
    } finally {
      chatStreaming.value = false;
      chatSending.value = false;
    }
  }

  function _escapeHtml(s) {
    return String(s || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function renderMarkdown(raw) {
    let s = _escapeHtml(raw || "");
    s = s.replace(/```([\s\S]*?)```/g, (_m, c) => `<pre><code>${c}</code></pre>`);
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    s = s.replace(/\n/g, "<br>");
    return s;
  }

  function startChatEdit(idx, text) {
    chatEditIndex.value = Number(idx);
    chatEditText.value = String(text || "");
  }

  function cancelChatEdit() {
    chatEditIndex.value = -1;
    chatEditText.value = "";
  }

  async function saveChatEdit(idx) {
    try {
      const res = await editChatMessage({ session_id: chatSessionId.value, index: idx, text: chatEditText.value, regenerate: false });
      const sess = activeChatSession.value;
      if (sess) sess.messages = res.history || [];
      cancelChatEdit();
    } catch (e) {
      _notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  async function regenerateFromMessage(idx) {
    try {
      const sess = activeChatSession.value;
      const list = [...(sess?.messages || [])];
      if (!list.length) return;
      let userIdx = Number(idx);
      if (String((list[idx] || {}).role || "") === "assistant") {
        for (let i = idx - 1; i >= 0; i -= 1) {
          if (String((list[i] || {}).role || "") === "user") {
            userIdx = i;
            break;
          }
        }
      }
      const source = list[userIdx] || {};
      const userText = String(source.text || "").trim();
      if (!userText) return;

      let current = list;
      while (current.length > userIdx) {
        const res = await deleteChatMessage(chatSessionId.value, userIdx);
        current = res.history || [];
        if (sess) sess.messages = current;
      }
      chatInput.value = userText;
      await sendChat("chat");
    } catch (e) {
      _notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  async function removeChatMessage(idx) {
    try {
      const res = await deleteChatMessage(chatSessionId.value, idx);
      const sess = activeChatSession.value;
      if (sess) sess.messages = res.history || [];
    } catch (e) {
      _notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  async function copyChatMessage(text) {
    try {
      await navigator.clipboard.writeText(String(text || ""));
      _notify(_t("chat.msg.copied"), "success");
    } catch {
      _notify(_t("chat.msg.copy_failed"), "warning");
    }
  }

  function triggerChatImagePick() {
    if (chatImageInputRef.value) chatImageInputRef.value.click();
  }

  function onChatImagePicked(event) {
    const file = event?.target?.files?.[0] || null;
    chatImageFile.value = file;
  }

  function clearChatImage() {
    chatImageFile.value = null;
    if (chatImageInputRef.value) chatImageInputRef.value.value = "";
  }

  function openChatExplore(payload) {
    chatExplorePayload.value = payload || null;
    chatExploreOpen.value = true;
  }

  function openChatPayloadResult(payload) {
    const p = payload || {};
    if (String(p.type || "") === "profile" || String(p.type || "") === "report") {
      openChatExplore(p);
      return;
    }
    const items = Array.isArray(p.items) ? p.items : [];
    const tabKey = String(p.home_tab || "").trim();
    if (tabKey === "recommend") {
      dashboardStore.homeRecommend.items = items;
      dashboardStore.homeRecommend.cursor = "";
      dashboardStore.homeRecommend.hasMore = false;
      if (_setTab) _setTab("dashboard");
      dashboardStore.homeTab = "recommend";
    } else if (tabKey === "history") {
      dashboardStore.homeHistory.items = items;
      dashboardStore.homeHistory.cursor = "";
      dashboardStore.homeHistory.hasMore = false;
      if (_setTab) _setTab("dashboard");
      dashboardStore.homeTab = "history";
    } else {
      dashboardStore.homeSearchState.items = items;
      dashboardStore.homeSearchState.cursor = "";
      dashboardStore.homeSearchState.hasMore = false;
      if (_setTab) _setTab("dashboard");
      dashboardStore.homeTab = "search";
    }
    chatExploreOpen.value = false;
  }

  function openChatExploreItem() {
    const p = chatExplorePayload.value || {};
    const items = Array.isArray(p.items) ? p.items : [];
    if (String(p.home_tab || "") === "history") {
      dashboardStore.homeHistory.items = items;
      dashboardStore.homeHistory.cursor = "";
      dashboardStore.homeHistory.hasMore = false;
      if (_setTab) _setTab("dashboard");
      dashboardStore.homeTab = "history";
    }
    chatExploreOpen.value = false;
  }

  return {
    tab,
    homeTab,
    t,
    chatFabOpen,
    chatSessions,
    chatSessionId,
    chatInput,
    chatIntent,
    chatSending,
    chatStreaming,
    chatStreamStats,
    chatEditIndex,
    chatEditText,
    chatLogRef,
    chatImageFile,
    chatImageInputRef,
    chatExploreOpen,
    chatExplorePayload,
    chatSidebarCollapsed,
    activeChatSession,
    chatIntentOptions,
    itemHoverTags,
    init,
    formatDateMinute,
    scrollChatToBottom,
    ensureChatSession,
    createChatSession,
    loadChatHistory,
    sendChat,
    _escapeHtml,
    renderMarkdown,
    startChatEdit,
    cancelChatEdit,
    saveChatEdit,
    regenerateFromMessage,
    removeChatMessage,
    copyChatMessage,
    triggerChatImagePick,
    onChatImagePicked,
    clearChatImage,
    openChatExplore,
    openChatPayloadResult,
    openChatExploreItem,
  };
});
