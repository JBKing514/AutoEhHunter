<template>
          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-2">{{ t('settings.title') }}</div>
            <div class="text-body-2 text-medium-emphasis">{{ t('settings.source', { chain: configMeta.sources || 'db > json > env' }) }}</div>
            <div class="mt-2"><v-btn size="small" variant="outlined" @click="openSetupWizardManual">{{ t('setup.reopen') }}</v-btn></div>
            <v-chip class="mt-2" :color="configMeta.db_connected ? 'success' : 'warning'" variant="tonal">
              {{ configMeta.db_connected ? t('settings.db_connected') : t('settings.db_disconnected', { reason: configMeta.db_error || 'n/a' }) }}
            </v-chip>
            <v-alert v-if="limitedModeMessages.length" type="warning" variant="tonal" class="mt-3">
              {{ t('settings.limited_mode.title') }} {{ limitedModeMessages.join(' / ') }}
            </v-alert>
          </v-card>

  <v-tabs class="mb-4" color="primary">
    <v-tab value="general" :to="{ name: 'settings-general' }">{{ t("settings.tab.general") }}</v-tab>
    <v-tab value="eh" :to="{ name: 'settings-eh' }">{{ t("settings.tab.eh") }}</v-tab>
    <v-tab value="data_clean" :to="{ name: 'settings-data-clean' }">{{ t("settings.tab.data_clean") }}</v-tab>
    <v-tab value="search" :to="{ name: 'settings-search' }">{{ t("settings.tab.search") }}</v-tab>
    <v-tab value="recommend" :to="{ name: 'settings-recommend' }">{{ t("settings.tab.recommend") }}</v-tab>
    <v-tab value="llm" :to="{ name: 'settings-llm' }">{{ t("settings.tab.llm") }}</v-tab>
    <v-tab value="plugins" :to="{ name: 'settings-plugins' }">{{ t("settings.tab.plugins") }}</v-tab>
    <v-tab value="other" :to="{ name: 'settings-other' }">{{ t("settings.tab.other") }}</v-tab>
    <v-tab v-if="config.DATA_UI_DEVELOPER_MODE" value="developer" :to="{ name: 'settings-developer' }">{{ t("settings.tab.developer") }}</v-tab>
  </v-tabs>

  <RouterView />

  <v-btn color="primary" size="large" @click="saveConfig">{{ t("settings.save") }}</v-btn>
</template>

<script>
import { useSettingsStore } from "../stores/settingsStore";

export default {
  setup() {
    return useSettingsStore();
  },
};
</script>
