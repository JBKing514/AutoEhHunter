<template>
  <v-card class="chat-shell d-flex" variant="outlined" style="height: calc(100dvh - 120px); overflow: hidden;">
    
    <v-navigation-drawer
      :model-value="mobile ? mobileDrawerOpen : true"
      @update:model-value="mobileDrawerOpen = $event"
      :permanent="!mobile" 
      :temporary="mobile"
      :rail="!mobile && chatStore.chatSidebarCollapsed"
      width="280"
      class="bg-surface border-r"
    >
      <div class="pa-3 d-flex align-center justify-space-between border-b">
        <div v-if="!mobile && chatStore.chatSidebarCollapsed" class="pa-2 d-flex justify-center border-b">
        <v-btn size="small" variant="text" icon="mdi-chevron-right" @click="chatStore.chatSidebarCollapsed = false" />
        </div>
      
        <div v-else class="pa-3 d-flex align-center justify-space-between border-b">
          <div class="text-subtitle-2 font-weight-bold text-truncate">{{ chatStore.t('chat.sessions') }}</div>
          <div class="d-flex ga-1 flex-shrink-0">
            <v-btn size="small" variant="text" icon="mdi-plus" @click="chatStore.createChatSession" />
            <v-btn v-if="!mobile" size="small" variant="text" icon="mdi-chevron-left" @click="chatStore.chatSidebarCollapsed = true" />
          </div>
        </div>
      </div>

      <v-list density="compact" nav class="chat-session-list pa-2">
        <v-list-item
          v-for="s in chatStore.chatSessions"
          :key="s.id"
          :title="!(!mobile && chatStore.chatSidebarCollapsed) ? s.title : ''"
          :prepend-icon="(!mobile && chatStore.chatSidebarCollapsed) ? 'mdi-message-text-outline' : undefined"
          :active="chatStore.chatSessionId === s.id"
          color="primary"
          rounded="lg"
          @click="selectSession(s.id)"
        >
          <template #append v-if="!(!mobile && chatStore.chatSidebarCollapsed)">
            <v-btn
              size="x-small"
              icon="mdi-delete-outline"
              variant="text"
              color="error"
              @click.stop="chatStore.removeChatSession(s.id)"
            />
          </template>
        </v-list-item>
      </v-list>
    </v-navigation-drawer>

    <div class="chat-main bg-background d-flex flex-column flex-grow-1 overflow-hidden" style="min-width: 0;">
      
      <v-toolbar v-if="mobile" density="compact" color="surface" class="border-b flex-shrink-0">
        <v-btn icon="mdi-menu" variant="text" @click="mobileDrawerOpen = !mobileDrawerOpen" />
        <v-toolbar-title class="text-subtitle-1 font-weight-bold text-truncate">
          {{ chatStore.activeChatSession?.title || chatStore.t('chat.sessions') }}
        </v-toolbar-title>
      </v-toolbar>

      <div class="chat-log flex-grow-1 pa-4 overflow-y-auto" ref="chatLogRef">
        <div v-for="(m, idx) in (chatStore.activeChatSession?.messages || [])" :key="`${idx}-${m.time || ''}`" :class="['chat-bubble', m.role === 'assistant' ? 'assistant' : 'user']">
          
          <div v-if="chatStore.chatEditIndex === idx" class="mb-2">
            <v-textarea v-model="chatStore.chatEditText" rows="2" auto-grow density="compact" />
            <div class="d-flex ga-1 mt-1">
              <v-btn size="x-small" variant="tonal" color="primary" @click="chatStore.saveChatEdit(idx)">{{ chatStore.t('chat.msg.save') }}</v-btn>
              <v-btn size="x-small" variant="text" @click="chatStore.cancelChatEdit">{{ chatStore.t('chat.msg.cancel') }}</v-btn>
            </div>
          </div>
          
          <div v-else class="text-body-2 chat-md" v-html="chatStore.renderMarkdown(m.text)" />
          
          <v-card v-if="m.role === 'assistant' && m.payload && Array.isArray(m.payload.items) && m.payload.items.length" class="mt-2 pa-2" variant="outlined">
            <v-row v-if="Array.isArray(m.payload.items) && m.payload.items.length" class="mt-1">
              <v-col v-for="it in m.payload.items.slice(0, 6)" :key="`chat-${idx}-${it.id}`" cols="6" sm="4" md="3">
                <v-menu open-on-hover location="top" :open-delay="700" :close-delay="120" max-width="360">
                  <template #activator="{ props }">
                    <v-card v-bind="props" class="home-card compact" variant="flat" @click="chatStore.openChatPayloadResult(m.payload)">
                      <div class="cover-ph">
                        <div v-if="it.thumb_url" class="cover-bg-blur" :style="{ backgroundImage: `url(${it.thumb_url})` }" />
                        <img v-if="it.thumb_url" :src="it.thumb_url" alt="cover" class="cover-img" loading="lazy" />
                        <v-icon v-else size="24">mdi-image-outline</v-icon>
                      </div>
                      <div class="cover-title-overlay">{{ it.title || '-' }}</div>
                    </v-card>
                  </template>
                  <v-card class="pa-2 hover-preview-card" variant="flat">
                    <div class="text-body-2 font-weight-medium mb-1">{{ it.title || '-' }}</div>
                    <div class="d-flex flex-wrap ga-1">
                      <v-chip v-for="tag in chatStore.itemHoverTags(it)" :key="`chat-tag-${tag}`" size="x-small" variant="outlined" class="hover-tag">{{ tag }}</v-chip>
                    </div>
                  </v-card>
                </v-menu>
              </v-col>
            </v-row>
            <div class="d-flex ga-2 mt-2" v-if="Array.isArray(m.payload.items) && m.payload.items.length > 6">
              <v-btn size="x-small" variant="tonal" @click="chatStore.openChatExplore(m.payload)">{{ chatStore.t('chat.explore.more') }}</v-btn>
            </div>
          </v-card>
          
          <div class="d-flex align-center justify-space-between mt-1">
            <div class="text-caption text-medium-emphasis">{{ m.role }} · {{ chatStore.formatDateMinute(m.time) }}</div>
            <div class="d-flex ga-1">
              <v-btn size="x-small" icon="mdi-content-copy" variant="text" @click="chatStore.copyChatMessage(m.text)" />
              <v-btn size="x-small" icon="mdi-pencil-outline" variant="text" @click="chatStore.startChatEdit(idx, m.text)" />
              <v-btn size="x-small" icon="mdi-refresh" variant="text" @click="chatStore.regenerateFromMessage(idx)" />
              <v-btn size="x-small" icon="mdi-delete-outline" variant="text" @click="chatStore.removeChatMessage(idx)" />
            </div>
          </div>
          
          <div v-if="m.role==='assistant' && m.stats && Number(m.stats.tokens || 0) > 0" class="text-caption text-medium-emphasis mt-1">
            {{ chatStore.t('chat.stats', { tps: m.stats.tps, tokens: m.stats.tokens, sec: m.stats.elapsed_s }) }}
          </div>
        </div>
        
        <div v-if="chatStore.chatStreaming" class="text-caption text-medium-emphasis mt-2 text-center">{{ chatStore.t('chat.streaming') }}</div>
        <div v-if="chatStore.chatStreamStats" class="text-caption text-medium-emphasis mt-1 text-center">{{ chatStore.t('chat.stats', { tps: chatStore.chatStreamStats.tps, tokens: chatStore.chatStreamStats.tokens, sec: chatStore.chatStreamStats.elapsed_s }) }}</div>
      </div>

      <div class="chat-input-area pa-3 border-t bg-surface flex-shrink-0">
        <div v-if="chatStore.chatImageFile" class="d-flex ga-2 align-center mb-2">
          <v-chip color="secondary" variant="tonal" prepend-icon="mdi-image">{{ chatStore.chatImageFile.name }}</v-chip>
          <v-btn size="x-small" variant="text" icon="mdi-close" @click="chatStore.clearChatImage" />
        </div>

        <div class="d-flex ga-2 align-end">
          <v-btn icon="mdi-image-plus" variant="text" class="mb-1" @click="chatStore.triggerChatImagePick" />
          
          <v-textarea
            v-model="chatStore.chatInput"
            auto-grow
            rows="1"
            max-rows="5"
            density="compact"
            :label="chatStore.t('chat.input')"
            variant="outlined"
            hide-details
            @keyup.enter.exact.prevent="chatStore.sendChat('chat')"
          />
          
          <v-btn 
            :loading="chatStore.chatSending" 
            color="primary" 
            icon="mdi-send" 
            variant="flat" 
            class="mb-1"
            :disabled="!chatStore.chatInput.trim() && !chatStore.chatImageFile"
            @click="chatStore.sendChat('chat')" 
          />
        </div>
        
        <div class="d-flex ga-2 mt-2" v-if="!chatStore.chatSending">
          <v-btn size="small" variant="tonal" @click="chatStore.sendChat('search_text')">{{ chatStore.t('chat.action.search_text') }}</v-btn>
          <v-btn size="small" variant="tonal" @click="chatStore.tab='dashboard'; chatStore.homeTab='recommend'">{{ chatStore.t('chat.action.open_recommend') }}</v-btn>
          <v-btn size="small" variant="tonal" @click="chatStore.tab='xp'; chatStore.chatInput=chatStore.t('chat.prompt.xp'); chatStore.sendChat('chat')">{{ chatStore.t('chat.action.explain_xp') }}</v-btn>
        </div>
      </div>
    </div>
  </v-card>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { useDisplay } from 'vuetify';
import { useChatStore } from "../stores/chatStore";
const chatStore = useChatStore();
const { mobile } = useDisplay();
const mobileDrawerOpen = ref(false);

const chatLogRef = ref(null);
const selectSession = (id) => {
  chatStore.chatSessionId = id;
  if (mobile.value) {
    mobileDrawerOpen.value = false;
  }
};
onMounted(() => {
  document.body.style.overflow = 'hidden';
  document.body.style.overscrollBehaviorY = 'none';

  if (typeof chatStore.loadChatSessions === "function") {
    chatStore.loadChatSessions().catch(() => null);
  }
});

onUnmounted(() => {
  document.body.style.overflow = '';
  document.body.style.overscrollBehaviorY = '';
});

watch(() => chatStore.chatSessionId, () => {
  if (typeof chatStore.loadChatHistory === "function") {
    chatStore.loadChatHistory().catch(() => null);
  }
}, { immediate: true });
watch(() => chatStore.activeChatSession?.messages, () => {
  nextTick(() => {
    if (chatLogRef.value) {
      chatLogRef.value.scrollTop = chatLogRef.value.scrollHeight;
    }
  });
}, { deep: true });
</script>

<style scoped>
.chat-shell {
  border-radius: 12px;
}
.chat-log {
  scroll-behavior: smooth;
}
.chat-bubble {
  max-width: 85%;
  margin-bottom: 16px;
  padding: 12px 16px;
  border-radius: 16px;
}
.chat-bubble.user {
  margin-left: auto;
  background-color: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
  border-bottom-right-radius: 4px;
}
.chat-bubble.assistant {
  margin-right: auto;
  background-color: rgb(var(--v-theme-surface-variant));
  color: rgb(var(--v-theme-on-surface-variant));
  border-bottom-left-radius: 4px;
}
.hover-preview-card {
  overflow: hidden;
}
</style>