<template>
  <v-card class="pa-4 mb-4">
    <div class="d-flex align-center justify-space-between mb-3">
      <div class="text-subtitle-1 font-weight-medium">{{ t('settings.tab.data_clean') }}</div>
      <v-btn size="small" variant="tonal" color="primary" :prepend-icon="settingsLocked ? 'mdi-lock' : 'mdi-lock-open-variant'" @click="settingsLocked = !settingsLocked">
        {{ settingsLocked ? t('settings.lock.unlock') : t('settings.lock.lock') }}
      </v-btn>
    </div>
    <v-alert v-if="settingsLocked" type="warning" variant="tonal" class="mb-3">{{ t('settings.lock.hint') }}</v-alert>
    <div :class="{ 'settings-locked': settingsLocked }">
    <v-row>
      <v-col cols="12" md="8"><v-text-field v-model="config.INGEST_API_BASE" :label="t('settings.provider.ingest_api_base')" variant="outlined" density="compact" color="primary" /></v-col>
      <v-col cols="12" md="4" class="d-flex align-center"><v-btn variant="outlined" block @click="reloadIngestModels">{{ t('settings.models.reload') }}</v-btn></v-col>
      <v-col cols="12" md="6"><v-combobox v-model="config.INGEST_VL_MODEL" :items="ingestModelOptions" :label="t('settings.provider.ingest_vl_model')" clearable variant="outlined" density="compact" color="primary" /></v-col>
      <v-col cols="12" md="6"><v-combobox v-model="config.INGEST_EMB_MODEL" :items="ingestModelOptions" :label="t('settings.provider.ingest_emb_model')" clearable variant="outlined" density="compact" color="primary" /></v-col>
      <v-col cols="12" md="6"><v-text-field v-model="config.INGEST_VL_MODEL_CUSTOM" :label="t('settings.provider.ingest_vl_model_custom')" clearable variant="outlined" density="compact" color="primary" /></v-col>
      <v-col cols="12" md="6"><v-text-field v-model="config.INGEST_EMB_MODEL_CUSTOM" :label="t('settings.provider.ingest_emb_model_custom')" clearable variant="outlined" density="compact" color="primary" /></v-col>
      <v-col cols="12" md="6"><v-text-field v-model="config.SIGLIP_MODEL" :label="t('settings.provider.siglip_model')" variant="outlined" density="compact" color="primary" /></v-col>

      <v-col cols="12"><v-divider class="my-2" /></v-col>

      <v-col cols="12" md="6"><v-text-field v-model="config.WORKER_BATCH" :label="t('settings.provider.worker_batch')" type="number" variant="outlined" density="compact" color="primary" /></v-col>
      <v-col cols="12" md="6"><v-text-field v-model="config.WORKER_SLEEP" :label="t('settings.provider.worker_sleep')" type="number" variant="outlined" density="compact" color="primary" /></v-col>
      <v-col cols="12" md="6"><v-switch v-model="config.TEXT_INGEST_PRUNE_NOT_SEEN" :label="t('settings.text_ingest.prune')" color="primary" inset hide-details /></v-col>
      <v-col cols="12" md="6"><v-switch v-model="config.WORKER_ONLY_MISSING" :label="t('settings.worker.only_missing')" color="primary" inset hide-details /></v-col>
      <v-col cols="12" md="6"><v-text-field v-model="config.TEXT_INGEST_BATCH_SIZE" :label="t('settings.text_ingest.batch')" type="number" variant="outlined" density="compact" color="primary" /></v-col>
      <v-col cols="12" md="6"><v-text-field v-model="config.LRR_READS_HOURS" :label="t('settings.lrr.reads_hours')" type="number" variant="outlined" density="compact" color="primary" /></v-col>
      <v-col cols="12" md="6"><v-btn block color="warning" variant="tonal" @click="clearWorksDuplicatesAction">{{ t('settings.data_clean.dedup_works') }}</v-btn></v-col>
      <v-col cols="12" md="6"><v-btn block color="warning" variant="tonal" @click="openReadEventsConfirm">{{ t('settings.data_clean.clear_read_events') }}</v-btn></v-col>

      <v-col cols="12"><v-divider class="my-2" /></v-col>

      <v-col cols="12" md="6"><v-text-field v-model="config.TAG_TRANSLATION_REPO" :label="t('settings.translation.repo')" clearable :hint="t('settings.translation.repo_hint')" persistent-hint variant="outlined" density="compact" color="primary" /></v-col>
      <v-col cols="12" md="6"><v-text-field v-model="config.TAG_TRANSLATION_AUTO_UPDATE_HOURS" :label="t('settings.translation.auto_update_hours')" type="number" variant="outlined" density="compact" color="primary" /></v-col>
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
    </div>

    <v-dialog v-model="confirmReadEventsDialog" max-width="460">
      <v-card>
        <v-card-title class="text-h6">{{ t('settings.data_clean.clear_read_events') }}</v-card-title>
        <v-card-text>{{ t('settings.data_clean.clear_read_events_confirm') }}</v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="confirmReadEventsDialog = false">{{ t('settings.unlock.cancel') }}</v-btn>
          <v-btn color="error" @click="confirmClearReadEventsNow">{{ t('settings.unlock.confirm') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script>
import { ref } from "vue";
import { useSettingsStore } from "../../stores/settingsStore";

export default {
  setup() {
    const store = useSettingsStore();
    const confirmReadEventsDialog = ref(false);

    function openReadEventsConfirm() {
      confirmReadEventsDialog.value = true;
    }

    async function confirmClearReadEventsNow() {
      confirmReadEventsDialog.value = false;
      await store.clearReadEventsAction();
    }

    return {
      ...store,
      settingsLocked: ref(true),
      confirmReadEventsDialog,
      openReadEventsConfirm,
      confirmClearReadEventsNow,
    };
  },
};
</script>

<style scoped>
.settings-locked {
  pointer-events: none;
  opacity: 0.58;
}
</style>
