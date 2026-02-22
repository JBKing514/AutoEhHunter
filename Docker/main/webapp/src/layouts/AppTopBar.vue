<template>
  <v-app-bar flat color="surface">
    <v-app-bar-nav-icon @click="emit('toggle-drawer')" />
    <v-app-bar-title class="font-weight-bold">{{ t(currentTitleKey) }}</v-app-bar-title>
    <v-spacer />
    <v-btn :icon="themeModeIcon" variant="text" @click="emit('cycle-theme')" />
    <v-menu location="bottom end">
      <template #activator="{ props }">
        <v-btn v-bind="props" icon="mdi-earth" variant="text" />
      </template>
      <v-list density="compact" min-width="160">
        <v-list-item
          v-for="opt in langOptions"
          :key="opt.value"
          :title="opt.title"
          :active="lang === opt.value"
          @click="emit('update:lang', opt.value)"
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
        <v-list-item v-for="n in notices" :key="n.id" :title="n.title" :subtitle="n.text">
          <template #append>
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
defineProps({
  currentTitleKey: { type: String, required: true },
  themeModeIcon: { type: String, required: true },
  langOptions: { type: Array, default: () => [] },
  lang: { type: String, default: "zh" },
  notices: { type: Array, default: () => [] },
  authUser: { type: Object, default: () => ({}) },
  t: { type: Function, required: true },
});

const emit = defineEmits([
  "toggle-drawer",
  "cycle-theme",
  "update:lang",
  "dismiss-notice",
  "clear-all-notices",
  "go-settings",
  "logout",
]);
</script>
