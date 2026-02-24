<template>
  <v-dialog :model-value="app.showSetupWizard" persistent max-width="920">
    <v-card class="pa-4" variant="flat">
      <div class="text-h6 font-weight-bold mb-1">{{ t('setup.title') }}</div>
      <div class="text-body-2 text-medium-emphasis mb-4">{{ t('setup.subtitle') }}</div>

      <v-window v-model="step" class="mb-3">
        <v-window-item :value="0">
          <div class="text-subtitle-1 mb-3">{{ t('setup.step.db') }}</div>
          <v-row>
            <v-col cols="12" md="4"><v-text-field v-model="setupForm.POSTGRES_HOST" :label="t('settings.pg.host')" /></v-col>
            <v-col cols="12" md="2"><v-text-field v-model="setupForm.POSTGRES_PORT" :label="t('settings.pg.port')" type="number" /></v-col>
            <v-col cols="12" md="3"><v-text-field v-model="setupForm.POSTGRES_DB" :label="t('settings.pg.db')" /></v-col>
            <v-col cols="12" md="3"><v-text-field v-model="setupForm.POSTGRES_USER" :label="t('settings.pg.user')" /></v-col>
            <v-col cols="12" md="6"><v-text-field v-model="setupForm.POSTGRES_PASSWORD" :label="t('settings.pg.password')" type="password" autocomplete="new-password" /></v-col>
            <v-col cols="12" md="6"><v-select v-model="setupForm.POSTGRES_SSLMODE" :items="['disable','allow','prefer','require','verify-ca','verify-full']" :label="t('settings.pg.sslmode')" /></v-col>
          </v-row>
          <div class="d-flex ga-2 align-center">
            <v-btn color="primary" variant="outlined" :loading="setupBusy" @click="validateSetupDbStep">{{ t('setup.validate_db') }}</v-btn>
            <v-chip :color="setupDbValid ? 'success' : 'default'" variant="tonal">{{ setupDbValid ? t('setup.valid') : t('setup.pending') }}</v-chip>
          </div>
        </v-window-item>

        <v-window-item :value="1">
          <div class="text-subtitle-1 mb-3">{{ t('setup.step.lrr') }}</div>
          <v-row>
            <v-col cols="12" md="8"><v-text-field v-model="setupForm.LRR_BASE" :label="t('settings.lrr.base')" /></v-col>
            <v-col cols="12" md="4"><v-text-field v-model="setupForm.LRR_API_KEY" :label="t('settings.lrr.api_key')" type="password" autocomplete="new-password" /></v-col>
          </v-row>
          <div class="d-flex ga-2 align-center">
            <v-btn color="primary" variant="outlined" :loading="setupBusy" @click="validateSetupLrrStep">{{ t('setup.validate_lrr') }}</v-btn>
            <v-chip :color="setupLrrValid ? 'success' : 'default'" variant="tonal">{{ setupLrrValid ? t('setup.valid') : t('setup.pending') }}</v-chip>
          </div>
        </v-window-item>

        <v-window-item :value="2">
          <div class="text-subtitle-1 mb-3">{{ t('setup.step.eh') }}</div>
          <v-row>
            <v-col cols="12" md="6"><v-text-field v-model="setupForm.EH_BASE_URL" :label="t('settings.eh.base_url')" /></v-col>
            <v-col cols="12" md="3"><v-text-field v-model="setupForm.EH_FETCH_MAX_PAGES" :label="t('settings.eh.max_pages')" type="number" /></v-col>
            <v-col cols="12" md="3"><v-text-field v-model="setupForm.EH_REQUEST_SLEEP" :label="t('settings.eh.req_sleep')" type="number" /></v-col>
            <v-col cols="12" md="3"><v-text-field v-model="setupForm.EH_SAMPLING_DENSITY" :label="t('settings.eh.sampling')" type="number" /></v-col>
            <v-col cols="12" md="3"><v-text-field v-model="setupForm.EH_USER_AGENT" :label="t('settings.eh.user_agent')" /></v-col>
            <v-col cols="12" md="3"><v-text-field v-model="setupForm.EH_MIN_RATING" :label="t('settings.eh.min_rating')" type="number" /></v-col>
            <v-col cols="12" md="3"><v-text-field v-model="setupForm.EH_QUEUE_LIMIT" :label="t('settings.eh.queue_limit')" type="number" /></v-col>
            <v-col cols="12"><v-text-field v-model="setupForm.EH_FILTER_TAG" :label="t('settings.eh.filter_tag')" /></v-col>
            <v-col cols="12"><v-text-field v-model="setupForm.EH_FILTER_CATEGORY" :label="t('settings.eh.filter_category')" /></v-col>
            <v-col cols="12"><v-text-field v-model="setupForm.EH_COOKIE" :label="t('settings.eh.cookie')" type="password" autocomplete="new-password" /></v-col>
          </v-row>
        </v-window-item>

        <v-window-item :value="3">
          <div class="text-subtitle-1 mb-3">{{ t('setup.step.ingest') }}</div>
          <v-alert type="warning" variant="tonal" class="mb-3">{{ t('setup.optional_limited') }}</v-alert>
          <div class="d-flex ga-2 align-center mb-3">
            <v-btn color="primary" :loading="siglipDownloading" @click="settings.downloadSiglipAction">{{ t('settings.model.siglip_download') }}</v-btn>
            <v-chip variant="tonal" :color="settings.modelStatus.siglip?.usable ? 'success' : 'warning'">{{ settings.modelStatus.siglip?.usable ? t('setup.valid') : t('setup.pending') }}</v-chip>
            <v-chip variant="outlined">{{ Number(settings.siglipDownload.progress || 0) }}%</v-chip>
          </div>
          <v-row>
            <v-col cols="12" md="6"><v-text-field v-model="setupForm.INGEST_API_BASE" :label="t('settings.provider.ingest_api_base')" /></v-col>
            <v-col cols="12" md="6"><v-text-field v-model="setupForm.INGEST_API_KEY" :label="t('settings.provider.ingest_api_key')" type="password" autocomplete="new-password" /></v-col>
            <v-col cols="12" md="6"><v-combobox v-model="setupForm.INGEST_VL_MODEL" :items="setupIngestModelOptions" :label="t('settings.provider.ingest_vl_model')" clearable /></v-col>
            <v-col cols="12" md="6"><v-combobox v-model="setupForm.INGEST_EMB_MODEL" :items="setupIngestModelOptions" :label="t('settings.provider.ingest_emb_model')" clearable /></v-col>
            <v-col cols="12" md="6"><v-text-field v-model="setupForm.INGEST_VL_MODEL_CUSTOM" :label="t('settings.provider.ingest_vl_model_custom')" /></v-col>
            <v-col cols="12" md="6"><v-text-field v-model="setupForm.INGEST_EMB_MODEL_CUSTOM" :label="t('settings.provider.ingest_emb_model_custom')" /></v-col>
          </v-row>
        </v-window-item>

        <v-window-item :value="4">
          <div class="text-subtitle-1 mb-3">{{ t('setup.step.llm') }}</div>
          <v-alert type="warning" variant="tonal" class="mb-3">{{ t('setup.optional_llm') }}</v-alert>
          <v-row>
            <v-col cols="12" md="6"><v-text-field v-model="setupForm.LLM_API_BASE" :label="t('settings.provider.llm_api_base')" /></v-col>
            <v-col cols="12" md="6"><v-text-field v-model="setupForm.LLM_API_KEY" :label="t('settings.provider.llm_api_key')" type="password" autocomplete="new-password" /></v-col>
            <v-col cols="12" md="6"><v-combobox v-model="setupForm.LLM_MODEL" :items="setupLlmModelOptions" :label="t('settings.provider.llm_model')" clearable /></v-col>
            <v-col cols="12" md="6"><v-combobox v-model="setupForm.EMB_MODEL" :items="setupLlmModelOptions" :label="t('settings.provider.emb_model')" clearable /></v-col>
            <v-col cols="12" md="6"><v-text-field v-model="setupForm.LLM_MODEL_CUSTOM" :label="t('settings.provider.llm_model_custom')" /></v-col>
            <v-col cols="12" md="6"><v-text-field v-model="setupForm.EMB_MODEL_CUSTOM" :label="t('settings.provider.emb_model_custom')" /></v-col>
          </v-row>
        </v-window-item>

        <v-window-item :value="5">
          <div class="text-h6 font-weight-bold mb-2">{{ t('setup.done.title') }}</div>
          <div class="text-body-2 text-medium-emphasis">{{ t('setup.done.desc') }}</div>
        </v-window-item>

        <v-window-item :value="6">
          <div class="text-h6 font-weight-bold mb-2">{{ t('setup.recovery.title') }}</div>
          <v-alert type="warning" variant="tonal" class="mb-3">{{ t('setup.recovery.warning') }}</v-alert>
          <div class="recovery-codes-list mb-3">
            <div v-for="(code, idx) in recoveryCodes" :key="idx" class="recovery-code-item">{{ code }}</div>
          </div>
          <v-btn color="primary" variant="outlined" @click="copyRecoveryCodes">{{ t('setup.recovery.copy') }}</v-btn>
        </v-window-item>
      </v-window>

      <div class="d-flex justify-space-between">
        <v-btn variant="text" :disabled="step <= 0" @click="step = Math.max(0, step - 1)">{{ t('setup.prev') }}</v-btn>
        <v-btn v-if="step < 5" color="primary" :disabled="(step === 0 && !setupDbValid) || (step === 1 && !setupLrrValid)" :loading="setupBusy" @click="goSetupNext(step)">{{ t('setup.next') }}</v-btn>
        <v-btn v-else-if="step === 5" color="success" :loading="setupBusy" @click="finishSetupWizard">{{ t('setup.finish') }}</v-btn>
        <v-btn v-else color="primary" @click="closeRecoveryStep">{{ t('setup.recovery.acknowledge') }}</v-btn>
      </div>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { completeSetup, getProviderModels, validateSetupDb, validateSetupLrr } from "../api";
import { useAppStore } from "../stores/appStore";
import { useSettingsStore } from "../stores/settingsStore";

const { t } = defineProps({ t: { type: Function, required: true } });

const app = useAppStore();
const settings = useSettingsStore();

const step = ref(0);
const setupBusy = ref(false);
const setupDbValid = ref(false);
const setupLrrValid = ref(false);
const setupIngestModelOptions = ref([]);
const setupLlmModelOptions = ref([]);
const recoveryCodes = ref([]);
const setupForm = reactive({
  POSTGRES_HOST: "localhost",
  POSTGRES_PORT: 5432,
  POSTGRES_DB: "autoeh",
  POSTGRES_USER: "postgres",
  POSTGRES_PASSWORD: "",
  POSTGRES_SSLMODE: "prefer",
  LRR_BASE: "",
  LRR_API_KEY: "",
  EH_BASE_URL: "https://e-hentai.org",
  EH_FETCH_MAX_PAGES: 8,
  EH_REQUEST_SLEEP: 4,
  EH_SAMPLING_DENSITY: 1,
  EH_USER_AGENT: "",
  EH_MIN_RATING: 0,
  EH_QUEUE_LIMIT: 2000,
  EH_FILTER_TAG: "",
  EH_FILTER_CATEGORY: "",
  EH_COOKIE: "",
  SIGLIP_MODEL: "google/siglip-so400m-patch14-384",
  INGEST_API_BASE: "",
  INGEST_API_KEY: "",
  INGEST_VL_MODEL: "",
  INGEST_EMB_MODEL: "",
  INGEST_VL_MODEL_CUSTOM: "",
  INGEST_EMB_MODEL_CUSTOM: "",
  LLM_API_BASE: "",
  LLM_API_KEY: "",
  LLM_MODEL: "",
  EMB_MODEL: "",
  LLM_MODEL_CUSTOM: "",
  EMB_MODEL_CUSTOM: "",
});

const siglipDownloading = computed(() => settings.siglipDownload.status && settings.siglipDownload.status !== "done");

function applySetupFormToConfig() {
  Object.entries(setupForm).forEach(([k, v]) => {
    settings.config[k] = v;
  });
}

watch(
  () => app.showSetupWizard,
  async (open) => {
    if (!open) return;
    step.value = 0;
    setupDbValid.value = false;
    setupLrrValid.value = false;
    await settings.loadConfigData();
    Object.assign(setupForm, {
      POSTGRES_HOST: settings.config.POSTGRES_HOST || setupForm.POSTGRES_HOST,
      POSTGRES_PORT: Number(settings.config.POSTGRES_PORT || setupForm.POSTGRES_PORT),
      POSTGRES_DB: settings.config.POSTGRES_DB || setupForm.POSTGRES_DB,
      POSTGRES_USER: settings.config.POSTGRES_USER || setupForm.POSTGRES_USER,
      POSTGRES_PASSWORD: settings.config.POSTGRES_PASSWORD || "",
      POSTGRES_SSLMODE: settings.config.POSTGRES_SSLMODE || "prefer",
      LRR_BASE: settings.config.LRR_BASE || "",
      LRR_API_KEY: settings.config.LRR_API_KEY || "",
      EH_BASE_URL: settings.config.EH_BASE_URL || setupForm.EH_BASE_URL,
      EH_FETCH_MAX_PAGES: Number(settings.config.EH_FETCH_MAX_PAGES || setupForm.EH_FETCH_MAX_PAGES),
      EH_REQUEST_SLEEP: Number(settings.config.EH_REQUEST_SLEEP || setupForm.EH_REQUEST_SLEEP),
      EH_SAMPLING_DENSITY: Number(settings.config.EH_SAMPLING_DENSITY || setupForm.EH_SAMPLING_DENSITY),
      EH_USER_AGENT: settings.config.EH_USER_AGENT || "",
      EH_MIN_RATING: Number(settings.config.EH_MIN_RATING || 0),
      EH_QUEUE_LIMIT: Number(settings.config.EH_QUEUE_LIMIT || setupForm.EH_QUEUE_LIMIT),
      EH_FILTER_TAG: settings.config.EH_FILTER_TAG || "",
      EH_FILTER_CATEGORY: settings.config.EH_FILTER_CATEGORY || "",
      EH_COOKIE: settings.config.EH_COOKIE || "",
      SIGLIP_MODEL: settings.config.SIGLIP_MODEL || setupForm.SIGLIP_MODEL,
      INGEST_API_BASE: settings.config.INGEST_API_BASE || "",
      INGEST_API_KEY: settings.config.INGEST_API_KEY || "",
      INGEST_VL_MODEL: settings.config.INGEST_VL_MODEL || "",
      INGEST_EMB_MODEL: settings.config.INGEST_EMB_MODEL || "",
      INGEST_VL_MODEL_CUSTOM: settings.config.INGEST_VL_MODEL_CUSTOM || "",
      INGEST_EMB_MODEL_CUSTOM: settings.config.INGEST_EMB_MODEL_CUSTOM || "",
      LLM_API_BASE: settings.config.LLM_API_BASE || "",
      LLM_API_KEY: settings.config.LLM_API_KEY || "",
      LLM_MODEL: settings.config.LLM_MODEL || "",
      EMB_MODEL: settings.config.EMB_MODEL || "",
      LLM_MODEL_CUSTOM: settings.config.LLM_MODEL_CUSTOM || "",
      EMB_MODEL_CUSTOM: settings.config.EMB_MODEL_CUSTOM || "",
    });
  },
  { immediate: true },
);

watch(() => setupForm.INGEST_API_BASE, async () => {
  const base = String(setupForm.INGEST_API_BASE || "").trim();
  if (!base) {
    setupIngestModelOptions.value = [];
    return;
  }
  try {
    const r = await getProviderModels(base, String(setupForm.INGEST_API_KEY || "").trim());
    setupIngestModelOptions.value = Array.isArray(r.models) ? r.models : [];
  } catch {
    setupIngestModelOptions.value = [];
  }
});
watch(() => setupForm.INGEST_API_KEY, async () => {
  const base = String(setupForm.INGEST_API_BASE || "").trim();
  if (!base) return;
  try {
    const r = await getProviderModels(base, String(setupForm.INGEST_API_KEY || "").trim());
    setupIngestModelOptions.value = Array.isArray(r.models) ? r.models : [];
  } catch {
    setupIngestModelOptions.value = [];
  }
});
watch(() => setupForm.LLM_API_BASE, async () => {
  const base = String(setupForm.LLM_API_BASE || "").trim();
  if (!base) {
    setupLlmModelOptions.value = [];
    return;
  }
  try {
    const r = await getProviderModels(base, String(setupForm.LLM_API_KEY || "").trim());
    setupLlmModelOptions.value = Array.isArray(r.models) ? r.models : [];
  } catch {
    setupLlmModelOptions.value = [];
  }
});
watch(() => setupForm.LLM_API_KEY, async () => {
  const base = String(setupForm.LLM_API_BASE || "").trim();
  if (!base) return;
  try {
    const r = await getProviderModels(base, String(setupForm.LLM_API_KEY || "").trim());
    setupLlmModelOptions.value = Array.isArray(r.models) ? r.models : [];
  } catch {
    setupLlmModelOptions.value = [];
  }
});

async function validateSetupDbStep() {
  setupBusy.value = true;
  try {
    const r = await validateSetupDb({
      host: setupForm.POSTGRES_HOST,
      port: Number(setupForm.POSTGRES_PORT || 5432),
      db: setupForm.POSTGRES_DB,
      user: setupForm.POSTGRES_USER,
      password: setupForm.POSTGRES_PASSWORD,
      sslmode: setupForm.POSTGRES_SSLMODE || "prefer",
    });
    setupDbValid.value = !!r.ok;
    settings.notify(r.ok ? t('setup.valid') : String(r.message || 'invalid'), r.ok ? 'success' : 'warning');
    if (r.ok) {
      applySetupFormToConfig();
      await settings.saveConfig();
    }
  } catch (e) {
    setupDbValid.value = false;
    settings.notify(String(e?.response?.data?.detail || e), 'warning');
  } finally {
    setupBusy.value = false;
  }
}

async function validateSetupLrrStep() {
  setupBusy.value = true;
  try {
    const r = await validateSetupLrr({ base: setupForm.LRR_BASE, api_key: setupForm.LRR_API_KEY });
    setupLrrValid.value = !!r.ok;
    settings.notify(r.ok ? t('setup.valid') : String(r.message || 'invalid'), r.ok ? 'success' : 'warning');
    if (r.ok) {
      applySetupFormToConfig();
      await settings.saveConfig();
    }
  } catch (e) {
    setupLrrValid.value = false;
    settings.notify(String(e?.response?.data?.detail || e), 'warning');
  } finally {
    setupBusy.value = false;
  }
}

async function goSetupNext(currentStep) {
  setupBusy.value = true;
  try {
    if ([2, 3, 4].includes(Number(currentStep))) {
      applySetupFormToConfig();
      await settings.saveConfig();
    }
    step.value = Number(currentStep) + 1;
  } finally {
    setupBusy.value = false;
  }
}

async function finishSetupWizard() {
  setupBusy.value = true;
  try {
    applySetupFormToConfig();
    await settings.saveConfig();
    const result = await completeSetup();
    if (result.recovery_codes && result.recovery_codes.length > 0) {
      recoveryCodes.value = result.recovery_codes;
      step.value = 6;
    } else {
      app.closeSetupWizard();
      settings.notify(t('setup.done.toast'), 'success');
    }
  } catch (e) {
    settings.notify(String(e?.response?.data?.detail || e), 'warning');
  } finally {
    setupBusy.value = false;
  }
}

function closeRecoveryStep() {
  recoveryCodes.value = [];
  app.closeSetupWizard();
  settings.notify(t('setup.done.toast'), 'success');
}

function copyRecoveryCodes() {
  const text = recoveryCodes.value.join('\n');
  navigator.clipboard.writeText(text).then(() => {
    settings.notify(t('setup.recovery.copied'), 'success');
  }).catch(() => {
    settings.notify(t('setup.recovery.copy_failed'), 'warning');
  });
}
</script>

<style scoped>
.recovery-codes-list {
  background: rgba(var(--v-theme-surface), 0.35);
  border: 1px solid rgba(255, 255, 255, 0.55);
  padding: 12px;
  border-radius: 8px;
  max-height: 200px;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.recovery-code-item {
  font-family: monospace;
  font-size: 15px;
  font-weight: 700;
  color: rgb(var(--v-theme-on-surface));
  background: rgba(var(--v-theme-surface-variant), 0.55);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.16);
  border-radius: 8px;
  padding: 10px 12px;
  word-break: break-all;
}

@media (max-width: 700px) {
  .recovery-codes-list {
    grid-template-columns: 1fr;
  }
}
</style>
