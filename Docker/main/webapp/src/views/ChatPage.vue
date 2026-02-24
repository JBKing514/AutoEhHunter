<template>
          <v-row class="chat-shell" no-gutters>
            <v-col cols="12" class="pr-md-2 h-100 chat-sidebar-col" :class="{ collapsed: chatSidebarCollapsed }">
              <v-card class="pa-3 chat-sidebar" variant="flat">
                <div v-if="chatSidebarCollapsed" class="d-flex align-center justify-center fill-height">
                  <v-btn size="small" variant="text" icon="mdi-chevron-right" @click="chatSidebarCollapsed = false" />
                </div>
                <template v-else>
                  <div class="d-flex align-center justify-space-between mb-2">
                    <div class="text-subtitle-2">{{ t('chat.sessions') }}</div>
                    <div class="d-flex ga-1">
                      <v-btn size="small" variant="text" icon="mdi-plus" @click="createChatSession" />
                      <v-btn size="small" variant="text" icon="mdi-chevron-left" @click="chatSidebarCollapsed = true" />
                    </div>
                  </div>
                  <v-list density="compact" nav class="chat-session-list">
                    <v-list-item
                      v-for="s in chatSessions"
                      :key="s.id"
                      :title="s.title"
                      :active="chatSessionId === s.id"
                      @click="chatSessionId = s.id"
                    >
                      <template #append>
                        <v-btn
                          size="x-small"
                          icon="mdi-delete-outline"
                          variant="text"
                          color="error"
                          @click.stop="removeChatSession(s.id)"
                        />
                      </template>
                    </v-list-item>
                  </v-list>
                </template>
              </v-card>
            </v-col>
            <v-col cols="12" class="chat-main-col" :class="{ expanded: chatSidebarCollapsed }">
              <v-card
                class="pa-3 chat-main"
                variant="flat"
                :class="{ 'chat-drop-active': chatImageDropActive }"
                @dragover.prevent="chatImageDropActive = true"
                @dragleave.prevent="chatImageDropActive = false"
                @drop.prevent="onChatImageDrop"
              >
                <div class="d-flex justify-end mb-2" v-if="chatSidebarCollapsed">
                  <v-btn size="small" variant="text" prepend-icon="mdi-format-list-bulleted" @click="chatSidebarCollapsed = false">{{ t('chat.sessions') }}</v-btn>
                </div>
                <div ref="chatLogRef" class="chat-log mb-3">
                  <div v-for="(m, idx) in (activeChatSession?.messages || [])" :key="`${idx}-${m.time || ''}`" :class="['chat-bubble', m.role === 'assistant' ? 'assistant' : 'user']">
                    <div v-if="chatEditIndex === idx" class="mb-2">
                      <v-textarea v-model="chatEditText" rows="2" auto-grow density="compact" />
                      <div class="d-flex ga-1 mt-1">
                        <v-btn size="x-small" variant="tonal" color="primary" @click="saveChatEdit(idx)">{{ t('chat.msg.save') }}</v-btn>
                        <v-btn size="x-small" variant="text" @click="cancelChatEdit">{{ t('chat.msg.cancel') }}</v-btn>
                      </div>
                    </div>
                    <div v-else class="text-body-2 chat-md" v-html="renderMarkdown(m.text)" />
                    <v-card v-if="m.role === 'assistant' && m.payload && Array.isArray(m.payload.items) && m.payload.items.length" class="mt-2 pa-2" variant="outlined">
                      <v-row v-if="Array.isArray(m.payload.items) && m.payload.items.length" class="mt-1">
                        <v-col v-for="it in m.payload.items.slice(0, 6)" :key="`chat-${idx}-${it.id}`" cols="6" sm="4" md="3">
                          <v-menu open-on-hover location="top" :open-delay="700" :close-delay="120" max-width="360">
                            <template #activator="{ props }">
                              <v-card v-bind="props" class="home-card compact" variant="flat" @click="openChatPayloadResult(m.payload)">
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
                                <v-chip v-for="tag in itemHoverTags(it)" :key="`chat-tag-${tag}`" size="x-small" variant="outlined" class="hover-tag">{{ tag }}</v-chip>
                              </div>
                            </v-card>
                          </v-menu>
                        </v-col>
                      </v-row>
                      <div class="d-flex ga-2 mt-2" v-if="Array.isArray(m.payload.items) && m.payload.items.length > 6">
                        <v-btn size="x-small" variant="tonal" @click="openChatExplore(m.payload)">{{ t('chat.explore.more') }}</v-btn>
                      </div>
                    </v-card>
                    <div class="d-flex align-center justify-space-between mt-1">
                      <div class="text-caption text-medium-emphasis">{{ m.role }} · {{ formatDateMinute(m.time) }}</div>
                      <div class="d-flex ga-1">
                        <v-btn size="x-small" icon="mdi-content-copy" variant="text" @click="copyChatMessage(m.text)" />
                        <v-btn size="x-small" icon="mdi-pencil-outline" variant="text" @click="startChatEdit(idx, m.text)" />
                        <v-btn size="x-small" icon="mdi-refresh" variant="text" @click="regenerateFromMessage(idx)" />
                        <v-btn size="x-small" icon="mdi-delete-outline" variant="text" @click="removeChatMessage(idx)" />
                      </div>
                    </div>
                    <div v-if="m.role==='assistant' && m.stats && Number(m.stats.tokens || 0) > 0" class="text-caption text-medium-emphasis mt-1">
                      {{ t('chat.stats', { tps: m.stats.tps, tokens: m.stats.tokens, sec: m.stats.elapsed_s }) }}
                    </div>
                  </div>
                </div>
                <div class="d-flex ga-2 align-center">
                  <v-btn icon="mdi-image-plus" variant="text" @click="triggerChatImagePick" />
                  <v-text-field v-model="chatInput" hide-details density="comfortable" :label="t('chat.input')" variant="outlined" @keyup.enter="sendChat('chat')" />
                  <v-select v-model="chatIntent" :items="chatIntentOptions" variant="outlined" item-title="title" item-value="value" density="comfortable" hide-details style="max-width: 180px" />
                  <v-btn :loading="chatSending" color="primary" @click="sendChat('chat')">{{ t('chat.send') }}</v-btn>
                </div>
                <div v-if="chatImageFile" class="d-flex ga-2 align-center mt-2">
                  <v-chip color="secondary" variant="tonal" prepend-icon="mdi-image">{{ chatImageFile.name }}</v-chip>
                  <v-btn size="x-small" variant="text" icon="mdi-close" @click="clearChatImage" />
                </div>
                <div class="d-flex ga-2 mt-2">
                  <v-btn size="small" variant="tonal" @click="sendChat('search_text')">{{ t('chat.action.search_text') }}</v-btn>
                  <v-btn size="small" variant="tonal" @click="tab='dashboard'; homeTab='recommend'">{{ t('chat.action.open_recommend') }}</v-btn>
                  <v-btn size="small" variant="tonal" @click="tab='xp'; chatInput=t('chat.prompt.xp'); sendChat('chat')">{{ t('chat.action.explain_xp') }}</v-btn>
                </div>
                <div v-if="chatStreaming" class="text-caption text-medium-emphasis mt-2">{{ t('chat.streaming') }}</div>
                <div v-if="chatStreamStats" class="text-caption text-medium-emphasis mt-1">{{ t('chat.stats', { tps: chatStreamStats.tps, tokens: chatStreamStats.tokens, sec: chatStreamStats.elapsed_s }) }}</div>
              </v-card>
            </v-col>
          </v-row>
</template>

<script>
import { useChatStore } from "../stores/chatStore";

export default {
  setup() {
    return useChatStore();
  },
  mounted() {
    if (typeof this.loadChatSessions === "function") {
      this.loadChatSessions().catch(() => null);
    }
  },
  watch: {
    chatSessionId: {
      immediate: true,
      handler() {
        if (typeof this.loadChatHistory === "function") {
          this.loadChatHistory().catch(() => null);
        }
      },
    },
  },
};
</script>
