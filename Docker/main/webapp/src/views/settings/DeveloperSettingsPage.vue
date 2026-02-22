<template>
<v-card v-if="config.DATA_UI_DEVELOPER_MODE" class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.tab.developer') }}</div>
            <div class="danger-zone pa-3 rounded-lg">
              <div class="text-subtitle-2 font-weight-bold mb-2">{{ t('settings.developer.danger_title') }}</div>
              <div class="text-caption mb-3">{{ t('settings.developer.danger_desc') }}</div>
              <div class="d-flex flex-wrap ga-2 align-center mb-3">
                <v-chip variant="tonal" :color="devSchemaStatus.exists ? 'warning' : 'default'">{{ t('settings.developer.schema_status', { exists: devSchemaStatus.exists ? 'yes' : 'no', size: devSchemaStatus.size_kb || 0 }) }}</v-chip>
                <v-chip variant="outlined">{{ devSchemaStatus.updated_at || '-' }}</v-chip>
              </div>
              <div class="d-flex ga-2 align-center flex-wrap">
                <input ref="devSchemaUploadRef" type="file" accept=".sql,.txt" @change="onDevSchemaUploadChange" />
                <v-btn color="warning" variant="outlined" @click="loadDevSchemaData">{{ t('settings.developer.reload') }}</v-btn>
                <v-btn color="error" :loading="devSchemaInjecting" @click="injectDevSchemaNow">{{ t('settings.developer.inject') }}</v-btn>
              </div>
              <div class="text-caption text-medium-emphasis mt-2 mono">{{ devSchemaStatus.path || '-' }}</div>
            </div>
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
