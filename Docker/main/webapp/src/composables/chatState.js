import { computed, ref } from "vue";

export function createChatState() {
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

  const activeChatSession = computed(() => {
    const found = (chatSessions.value || []).find((s) => s.id === chatSessionId.value);
    return found || chatSessions.value[0];
  });

  function scrollChatToBottom(force = false) {
    const el = chatLogRef.value;
    if (!el) return;
    const nearBottom = (el.scrollHeight - el.scrollTop - el.clientHeight) < 80;
    if (force || nearBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }

  return {
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
    scrollChatToBottom,
  };
}
