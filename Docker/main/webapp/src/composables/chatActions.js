export function createChatActions(ctx) {
  const {
    chatSessions,
    chatSessionId,
    chatInput,
    chatIntent,
    chatSending,
    chatStreaming,
    chatStreamStats,
    chatEditIndex,
    chatEditText,
    chatImageFile,
    chatImageInputRef,
    chatExploreOpen,
    chatExplorePayload,
    activeChatSession,
    lang,
    tab,
    homeTab,
    homeHistory,
    homeRecommend,
    homeSearchState,
    notify,
    t,
    nextTick,
    scrollChatToBottom,
    getChatHistory,
    streamChatMessage,
    sendChatMessageUpload,
    editChatMessage,
    deleteChatMessage,
  } = ctx;

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
        ui_lang: lang.value,
        context: { page: tab.value },
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
      notify(String(e?.response?.data?.detail || e), "warning");
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
      notify(String(e?.response?.data?.detail || e), "warning");
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
      notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  async function removeChatMessage(idx) {
    try {
      const res = await deleteChatMessage(chatSessionId.value, idx);
      const sess = activeChatSession.value;
      if (sess) sess.messages = res.history || [];
    } catch (e) {
      notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  async function copyChatMessage(text) {
    try {
      await navigator.clipboard.writeText(String(text || ""));
      notify(t("chat.msg.copied"), "success");
    } catch {
      notify(t("chat.msg.copy_failed"), "warning");
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
      homeRecommend.value.items = items;
      homeRecommend.value.cursor = "";
      homeRecommend.value.hasMore = false;
      tab.value = "dashboard";
      homeTab.value = "recommend";
    } else if (tabKey === "history") {
      homeHistory.value.items = items;
      homeHistory.value.cursor = "";
      homeHistory.value.hasMore = false;
      tab.value = "dashboard";
      homeTab.value = "history";
    } else {
      homeSearchState.value.items = items;
      homeSearchState.value.cursor = "";
      homeSearchState.value.hasMore = false;
      tab.value = "dashboard";
      homeTab.value = "search";
    }
    chatExploreOpen.value = false;
  }

  function openChatExploreItem() {
    const p = chatExplorePayload.value || {};
    const items = Array.isArray(p.items) ? p.items : [];
    if (String(p.home_tab || "") === "history") {
      homeHistory.value.items = items;
      homeHistory.value.cursor = "";
      homeHistory.value.hasMore = false;
      tab.value = "dashboard";
      homeTab.value = "history";
    }
    chatExploreOpen.value = false;
  }

  return {
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
}
