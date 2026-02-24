<template>
  <div v-if="ui.t">
    <app-sidebar
      v-if="!appStore.isRecoveryMode"
      :model-value="ui.drawer"
      :rail="ui.rail"
      :brand-logo="ui.brandLogo"
      :nav-items="ui.navItems"
      :tab="ui.tab"
      :t="ui.t"
      @update:model-value="ui.drawer = $event"
      @update:rail="ui.rail = $event"
      @go-tab="ui.goTab"
    />

    <app-top-bar
      :current-title-key="ui.currentTitleKey"
      :theme-mode-icon="ui.themeModeIcon"
      :lang-options="ui.langOptions"
      :lang="ui.lang"
      :zoom-options="ui.pageZoomOptions"
      :page-zoom="ui.pageZoom"
      :notices="ui.notices"
      :auth-user="appStore.authUser"
      :t="ui.t"
      @toggle-drawer="ui.drawer = !ui.drawer"
      @cycle-theme="ui.cycleThemeMode"
      @update:lang="ui.setLangValue($event)"
      @update:zoom="ui.setPageZoom($event)"
      @dismiss-notice="ui.dismissNotice"
      @clear-all-notices="ui.clearAllNotices"
      @go-settings="ui.goTab('settings')"
      @logout="ui.logoutNow"
    />

    <v-main>
      <v-container fluid :class="['pa-6', ui.tab === 'chat' ? 'chat-page-container' : '']">
        <RouterView />
      </v-container>
    </v-main>

    <div v-if="ui.tab === 'dashboard' && dashboardStore.showScrollQuickActions" class="quick-fab-wrap" :style="dashboardStore.quickFabStyle">
      <v-btn color="secondary" icon="mdi-magnify" size="large" class="quick-fab" @click="dashboardStore.quickSearchOpen = true" />
      <v-btn color="info" icon="mdi-filter-variant" size="large" class="quick-fab" @click="dashboardStore.homeFiltersOpen = true" />
      <v-btn color="primary" icon="mdi-arrow-up" size="large" class="quick-fab" @click="dashboardStore.scrollToTop" />
    </div>

    <chat-fab-panel
      :llm-ready="settingsStore.llmReady"
      :tab="ui.tab"
      :chat-fab-open="chatStore.chatFabOpen"
      :active-chat-session="chatStore.activeChatSession"
      :chat-image-file="chatStore.chatImageFile"
      :chat-input="chatStore.chatInput"
      :chat-intent="chatStore.chatIntent"
      :chat-intent-options="chatStore.chatIntentOptions"
      :chat-sending="chatStore.chatSending"
      :t="ui.t"
      @toggle-open="chatStore.chatFabOpen = !chatStore.chatFabOpen"
      @close="chatStore.chatFabOpen = false"
      @clear-chat-image="chatStore.clearChatImage"
      @trigger-chat-image-pick="chatStore.triggerChatImagePick"
      @update:chat-input="chatStore.chatInput = $event"
      @update:chat-intent="chatStore.chatIntent = $event"
      @send-chat="chatStore.sendChat('chat')"
    />
  </div>
</template>

<script setup>
import { useLayoutStore } from "../stores/layoutStore";
import { useDashboardStore } from "../stores/dashboardStore";
import { useChatStore } from "../stores/chatStore";
import { useSettingsStore } from "../stores/settingsStore";
import { useAppStore } from "../stores/appStore";
import AppSidebar from "./AppSidebar.vue";
import AppTopBar from "./AppTopBar.vue";
import ChatFabPanel from "./ChatFabPanel.vue";

const ui = useLayoutStore();
const dashboardStore = useDashboardStore();
const chatStore = useChatStore();
const settingsStore = useSettingsStore();
const appStore = useAppStore();
</script>
