<template>
  <div v-if="llmReady && tab !== 'chat'" class="chat-fab-wrap">
    <v-btn color="primary" icon="mdi-chat" size="large" class="chat-fab" @click="emit('toggle-open')" />
    <v-card v-if="chatFabOpen" class="chat-fab-panel pa-3" variant="flat">
      <div class="d-flex align-center justify-space-between mb-2">
        <div class="text-subtitle-2">{{ t('chat.fab.title') }}</div>
        <v-btn size="x-small" icon="mdi-close" variant="text" @click="emit('close')" />
      </div>
      <div class="chat-fab-log mb-2">
        <div
          v-for="(m, idx) in (activeChatSession?.messages || []).slice(-6)"
          :key="`fab-${idx}-${m.time || ''}`"
          :class="['chat-bubble mini', m.role === 'assistant' ? 'assistant' : 'user']"
        >
          <div class="text-caption">{{ m.text }}</div>
        </div>
      </div>
      <div v-if="chatImageFile" class="d-flex ga-2 align-center mb-2">
        <v-chip size="small" color="secondary" variant="tonal" prepend-icon="mdi-image">{{ chatImageFile.name }}</v-chip>
        <v-btn size="x-small" variant="text" icon="mdi-close" @click="emit('clear-chat-image')" />
      </div>
      <div class="d-flex ga-2 align-center">
        <v-btn icon="mdi-image-plus" size="small" variant="text" @click="emit('trigger-chat-image-pick')" />
        <v-text-field
          :model-value="chatInput"
          hide-details
          density="compact"
          :label="t('chat.input')"
          variant="outlined"
          @update:model-value="emit('update:chatInput', $event)"
          @keyup.enter="emit('send-chat')"
        />
        <v-select
          :model-value="chatIntent"
          :items="chatIntentOptions"
          item-title="title"
          item-value="value"
          density="compact"
          hide-details
          style="max-width: 150px"
          @update:model-value="emit('update:chatIntent', $event)"
        />
        <v-btn size="small" :loading="chatSending" color="primary" @click="emit('send-chat')">{{ t('chat.send') }}</v-btn>
      </div>
    </v-card>
  </div>
</template>

<script setup>
defineProps({
  llmReady: { type: Boolean, default: false },
  tab: { type: String, default: "dashboard" },
  chatFabOpen: { type: Boolean, default: false },
  activeChatSession: { type: Object, default: null },
  chatImageFile: { type: Object, default: null },
  chatInput: { type: String, default: "" },
  chatIntent: { type: String, default: "auto" },
  chatIntentOptions: { type: Array, default: () => [] },
  chatSending: { type: Boolean, default: false },
  t: { type: Function, required: true },
});

const emit = defineEmits([
  "toggle-open",
  "close",
  "clear-chat-image",
  "trigger-chat-image-pick",
  "update:chatInput",
  "update:chatIntent",
  "send-chat",
]);
</script>
