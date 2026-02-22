<template>
<v-card  class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.tab.data_clean') }}</div>
            <v-row>
              <v-col cols="12" md="8"><v-text-field v-model="config.INGEST_API_BASE" :label="labelFor('INGEST_API_BASE')" /></v-col>
              <v-col cols="12" md="4" class="d-flex align-center"><v-btn variant="outlined" block @click="reloadIngestModels">{{ t('settings.models.reload') }}</v-btn></v-col>
              <v-col cols="12" md="6"><v-combobox v-model="config.INGEST_VL_MODEL" :items="ingestModelOptions" :label="labelFor('INGEST_VL_MODEL')" clearable /></v-col>
              <v-col cols="12" md="6"><v-combobox v-model="config.INGEST_EMB_MODEL" :items="ingestModelOptions" :label="labelFor('INGEST_EMB_MODEL')" clearable /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.INGEST_VL_MODEL_CUSTOM" :label="labelFor('INGEST_VL_MODEL_CUSTOM')" clearable /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.INGEST_EMB_MODEL_CUSTOM" :label="labelFor('INGEST_EMB_MODEL_CUSTOM')" clearable /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.SIGLIP_MODEL" :label="labelFor('SIGLIP_MODEL')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.WORKER_BATCH" :label="labelFor('WORKER_BATCH')" type="number" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.WORKER_SLEEP" :label="labelFor('WORKER_SLEEP')" type="number" /></v-col>
              <v-col cols="12" md="6"><v-switch v-model="config.TEXT_INGEST_PRUNE_NOT_SEEN" :label="labelFor('TEXT_INGEST_PRUNE_NOT_SEEN')" /></v-col>
              <v-col cols="12" md="6"><v-switch v-model="config.WORKER_ONLY_MISSING" :label="labelFor('WORKER_ONLY_MISSING')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.TEXT_INGEST_BATCH_SIZE" :label="labelFor('TEXT_INGEST_BATCH_SIZE')" type="number" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.TAG_TRANSLATION_REPO" :label="labelFor('TAG_TRANSLATION_REPO')" clearable :hint="t('settings.translation.repo_hint')" persistent-hint /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.TAG_TRANSLATION_AUTO_UPDATE_HOURS" :label="labelFor('TAG_TRANSLATION_AUTO_UPDATE_HOURS')" type="number" /></v-col>
              <v-col cols="12" md="6" class="d-flex align-center">
                <v-chip variant="tonal" color="info">{{ t('settings.translation.status', { repo: translationStatus.repo || '-', sha: translationStatus.head_sha || '-', fetched: translationStatus.fetched_at || '-' }) }}</v-chip>
              </v-col>
              <v-col cols="12" md="6" class="d-flex align-center">
                <v-chip variant="outlined">{{ t('settings.translation.manual', { path: translationStatus.manual_file?.path || '-', time: translationStatus.manual_file?.updated_at || '-' }) }}</v-chip>
              </v-col>
              <v-col cols="12" md="6">
                <input ref="translationUploadRef" type="file" accept=".json,.jsonl,.txt" @change="onTranslationUploadChange" />
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
