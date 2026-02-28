<template>
  <v-app-bar flat color="surface" :class="{ 'app-header': safeAreaTopInset }">
    <v-app-bar-nav-icon @click="emit('toggle-drawer')" />
    <v-app-bar-title class="font-weight-bold">{{ t(currentTitleKey) }}</v-app-bar-title>
    <v-spacer />
    <v-btn :icon="themeModeIcon" variant="text" @click="handleCycleTheme()" />
    <v-menu location="bottom end">
      <template #activator="{ props }">
        <v-btn v-bind="props" icon="mdi-cog-outline" variant="text" />
      </template>
      <v-list density="compact" min-width="220">
        <v-list-subheader>{{ t('topbar.settings.language') }}</v-list-subheader>
        <v-list-item
          v-for="opt in langOptions"
          :key="opt.value"
          :title="opt.title"
          :active="lang === opt.value"
          @click="handleLanguageChange(opt.value)"
        />
        <v-divider class="my-1" />
        <v-list-subheader>{{ t('topbar.settings.zoom') }}</v-list-subheader>
        <v-list-item
          v-for="opt in zoomOptions"
          :key="`zoom-${opt.value}`"
          :title="opt.title"
          :active="Number(pageZoom) === Number(opt.value)"
          @click="emit('update:zoom', opt.value)"
        />
      </v-list>
    </v-menu>
    <v-menu location="bottom end">
      <template #activator="{ props }">
        <v-badge :content="String(notices.length)" :model-value="notices.length > 0" color="error" inline>
          <v-btn v-bind="props" icon="mdi-bell-outline" variant="text" />
        </v-badge>
      </template>
      <v-list density="compact" min-width="360" class="notice-list">
        <v-list-item v-for="n in notices" :key="n.id" class="notice-item">
          <template #title>
            <div class="notice-title">{{ n.title }}</div>
          </template>
          <template #subtitle>
            <div class="notice-text">{{ n.text }}</div>
          </template>
          <template #append>
            <v-btn
              v-if="n.actionLabel"
              size="x-small"
              variant="tonal"
              color="warning"
              class="mr-1"
              @click="emit('notice-action', n.id)"
            >
              {{ n.actionLabel }}
            </v-btn>
            <v-btn size="x-small" variant="text" icon="mdi-close" @click="emit('dismiss-notice', n.id)" />
          </template>
        </v-list-item>
        <v-list-item v-if="!notices.length" :title="t('notice.empty')" />
        <v-list-item v-if="notices.length" :title="t('notice.clear_all')" @click="emit('clear-all-notices')" />
      </v-list>
    </v-menu>
    <v-menu location="bottom end">
      <template #activator="{ props }">
        <v-btn v-bind="props" icon="mdi-account-circle-outline" variant="text" />
      </template>
      <v-list density="compact" min-width="180">
        <v-list-item :title="authUser.username || '-'">
          <template #prepend><v-icon icon="mdi-account" /></template>
        </v-list-item>
        <v-list-item :title="t('auth.menu.edit_profile')" @click="emit('go-settings')">
          <template #prepend><v-icon icon="mdi-account-cog-outline" /></template>
        </v-list-item>
        <v-list-item :title="t('auth.menu.logout')" @click="emit('logout')">
          <template #prepend><v-icon icon="mdi-logout" /></template>
        </v-list-item>
      </v-list>
    </v-menu>
  </v-app-bar>
</template>

<script setup>
import { useSettingsStore } from "../stores/settingsStore"; 

defineProps({
  currentTitleKey: { type: String, required: true },
  themeModeIcon: { type: String, required: true },
  langOptions: { type: Array, default: () => [] },
  lang: { type: String, default: "zh" },
  zoomOptions: { type: Array, default: () => [] },
  pageZoom: { type: Number, default: 100 },
  notices: { type: Array, default: () => [] },
  authUser: { type: Object, default: () => ({}) },
  t: { type: Function, required: true },
  safeAreaTopInset: { type: Boolean, default: false },
});

const emit = defineEmits([
  "toggle-drawer",
  "cycle-theme",
  "update:lang",
  "update:zoom",
  "dismiss-notice",
  "notice-action",
  "clear-all-notices",
  "go-settings",
  "logout",
]);

const settings = useSettingsStore();
const handleLanguageChange = async (newLang) => {
  emit("update:lang", newLang);
  settings.config.DATA_UI_LANG = newLang;
  try {
    await settings.saveConfig();
  } catch (e) {
    console.error("Failed to save language to DB", e);
  }
};
const handleCycleTheme = async () => {
  const current = settings.config.DATA_UI_THEME_MODE || "system";
  const next = current === "system" ? "light" : current === "light" ? "dark" : "system";
  settings.config.DATA_UI_THEME_MODE = next;
  emit("cycle-theme"); 
  try {
    await settings.saveConfig();
  } catch (e) {
    console.error("Failed to save theme to DB", e);
  }
};
</script>

<style scoped>
.app-header {
  background-color: #000000;
}

.notice-title {
  white-space: pre-wrap;
  line-height: 1.25;
  word-break: break-word;
}

.notice-text {
  white-space: pre-wrap;
  line-height: 1.3;
  word-break: break-word;
  max-width: 520px;
}

.notice-item :deep(.v-list-item-subtitle) {
  -webkit-line-clamp: unset;
  white-space: pre-wrap;
  overflow: visible;
}

@media (max-width: 959px) {
  .app-header {
    padding-top: env(safe-area-inset-top);
    padding-top: max(20px, env(safe-area-inset-top));
  }
}
</style>
