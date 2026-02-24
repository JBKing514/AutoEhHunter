<template>
  <v-card class="pa-4 mb-4">
    <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.tab.other') }}</div>
    <v-row>
      <v-col cols="12" md="6">
        <v-switch v-model="config.DATA_UI_DEVELOPER_MODE" :label="t('settings.ui.developer_mode')" color="primary" inset hide-details />
      </v-col>
      <v-col cols="12">
        <div class="text-body-2 text-medium-emphasis">{{ t('settings.developer_mode.hint') }}</div>
      </v-col>
    </v-row>
  </v-card>
</template>

<script>
import { useSettingsStore } from "../../stores/settingsStore";

export default {
  setup() {
    return useSettingsStore();
  },
};
</script>
