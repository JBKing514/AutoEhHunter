<template>
  <v-dialog :model-value="app.showSetupWizard" persistent fullscreen :transition="false">
    <v-card class="setup-wizard-wrap pa-4" variant="flat">
      <div v-if="step > 0" class="text-h6 font-weight-bold mb-1">{{ t('setup.title') }}</div>
      <div v-if="step > 0" class="text-body-2 text-medium-emphasis mb-4">{{ t('setup.subtitle') }}</div>

      <v-defaults-provider :defaults="wizardFieldDefaults">
      <v-window v-model="step" class="mb-3">
        <v-window-item :value="0">
          <div class="setup-welcome d-flex flex-column align-center justify-center text-center">
            <div class="hello-cloud" aria-hidden="true">
              <span v-for="(w, idx) in helloCloud" :key="`hello-${idx}`" class="hello-word" :style="helloWordStyle(w)">{{ w.text }}</span>
            </div>
            <img :src="brandLogo" alt="AutoEhHunter" class="setup-welcome-logo mb-4" />
            <div class="text-h4 font-weight-bold mb-6">AutoEhHunter</div>
            <v-btn icon size="x-large" color="primary" class="setup-welcome-next" @click="step = 1">
              <v-icon size="30">mdi-arrow-right</v-icon>
            </v-btn>
          </div>
        </v-window-item>

        <v-window-item :value="1">
          <div class="text-subtitle-1 mb-1">{{ t('setup.step.ui') }}</div>
          <div class="text-body-2 text-medium-emphasis mb-3">{{ t('setup.ui.hint') }}</div>
          <v-row>
            <v-col cols="12" md="4">
              <v-select
                v-model="setupForm.DATA_UI_LANG"
                :items="layout.langOptions"
                item-title="title"
                item-value="value"
                :label="t('settings.ui.lang')"
              />
            </v-col>
            <v-col cols="12" md="4"><v-select v-model="setupForm.DATA_UI_TIMEZONE" :items="settings.timezoneOptions" :label="t('settings.ui.timezone')" /></v-col>
            <v-col cols="12" md="4"><v-select v-model="setupForm.DATA_UI_THEME_MODE" :items="settings.themeModeOptions" item-title="title" item-value="value" :label="t('settings.ui.theme_mode')" /></v-col>
            <v-col cols="12" md="6"><v-select v-model="setupForm.DATA_UI_THEME_PRESET" :items="settings.themeOptions" item-title="title" item-value="value" :label="t('settings.ui.theme_preset')" /></v-col>
            <v-col cols="12" md="6"><v-switch v-model="setupForm.DATA_UI_THEME_OLED" :label="t('settings.ui.theme_oled')" color="primary" inset hide-details /></v-col>
          </v-row>
        </v-window-item>

        <v-window-item :value="2">
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

        <v-window-item v-if="showAdminCreateStep" :value="3">
          <div class="text-subtitle-1 mb-3">{{ t('setup.step.admin') }}</div>
          <v-alert v-if="adminAlreadyConfigured" type="info" variant="tonal" class="mb-3">{{ t('setup.admin.already_configured') }}</v-alert>
          <v-row v-else>
            <v-col cols="12"><div class="text-body-2 text-medium-emphasis">{{ t('setup.admin.hint') }}</div></v-col>
            <v-col cols="12" md="4"><v-text-field v-model="setupForm.ADMIN_USERNAME" :label="t('auth.username')" autocomplete="username" /></v-col>
            <v-col cols="12" md="4"><v-text-field v-model="setupForm.ADMIN_PASSWORD" :label="t('auth.password')" type="password" autocomplete="new-password" /></v-col>
            <v-col cols="12" md="4"><v-text-field v-model="setupForm.ADMIN_PASSWORD2" :label="t('auth.password_confirm')" type="password" autocomplete="new-password" /></v-col>
            <v-col cols="12">
              <v-checkbox v-model="setupForm.AUTO_DOWNLOAD_SIGLIP" :label="t('setup.siglip.auto_download')" color="primary" hide-details />
            </v-col>
            <v-col cols="12" v-if="!setupForm.AUTO_DOWNLOAD_SIGLIP">
              <v-alert type="warning" variant="tonal">{{ t('setup.siglip.skip_warning') }}</v-alert>
            </v-col>
            <v-col cols="12" class="d-flex ga-2 align-center">
              <v-btn color="primary" variant="outlined" :loading="setupBusy" @click="createAdminInSetup">{{ t('auth.register.submit') }}</v-btn>
              <v-chip :color="setupAdminValid ? 'success' : 'default'" variant="tonal">{{ setupAdminValid ? t('setup.valid') : t('setup.pending') }}</v-chip>
            </v-col>
          </v-row>
        </v-window-item>

        <v-window-item :value="4">
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

        <v-window-item :value="5">
          <div class="text-subtitle-1 mb-3">{{ t('setup.step.eh') }}</div>
          <v-card class="pa-4 mb-4" variant="outlined">
            <div class="text-subtitle-2 font-weight-medium mb-3">{{ t('settings.eh.cookie') }}</div>
            <v-row>
              <v-col cols="12" md="6"><v-text-field v-model="ehCookieParts.ipb_member_id" label="ipb_member_id" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="ehCookieParts.ipb_pass_hash" label="ipb_pass_hash" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="ehCookieParts.sk" label="sk" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="ehCookieParts.igneous" label="igneous" /></v-col>
            </v-row>
          </v-card>
          <v-card class="pa-4 mb-4" variant="outlined">
            <div class="text-subtitle-2 font-weight-medium mb-3">{{ t('settings.eh.filter_category') }}</div>
            <div class="category-grid">
              <v-btn
                v-for="cat in settings.ehCategoryDefs"
                :key="cat.key"
                class="category-btn font-weight-bold"
                rounded="lg"
                variant="flat"
                :style="settings.categoryStyle(cat.key, cat.color)"
                @click="settings.toggleCategory(cat.key)"
              >
                <span class="text-truncate">{{ cat.label }}</span>
              </v-btn>
            </div>
          </v-card>
          <v-row>
            <v-col cols="12" md="6"><v-text-field v-model="setupForm.EH_BASE_URL" :label="t('settings.eh.base_url')" /></v-col>
            <v-col cols="12" md="3"><v-text-field v-model="setupForm.EH_FETCH_MAX_PAGES" :label="t('settings.eh.max_pages')" type="number" /></v-col>
            <v-col cols="12" md="3"><v-text-field v-model="setupForm.EH_REQUEST_SLEEP" :label="t('settings.eh.request_sleep')" type="number" /></v-col>
            <v-col cols="12" md="3"><v-text-field v-model="setupForm.EH_SAMPLING_DENSITY" :label="t('settings.eh.sampling_density')" type="number" /></v-col>
            <v-col cols="12" md="3"><v-text-field v-model="setupForm.EH_USER_AGENT" :label="t('settings.eh.user_agent')" /></v-col>
            <v-col cols="12" md="6"><v-text-field v-model="setupForm.EH_HTTP_PROXY" :label="t('settings.eh.http_proxy')" placeholder="http://127.0.0.1:7890" /></v-col>
            <v-col cols="12" md="6"><v-text-field v-model="setupForm.EH_HTTPS_PROXY" :label="t('settings.eh.https_proxy')" placeholder="http://127.0.0.1:7890" /></v-col>
            <v-col cols="12" md="3"><v-text-field v-model="setupForm.EH_MIN_RATING" :label="t('settings.eh.min_rating')" type="number" /></v-col>
            <v-col cols="12" md="3"><v-text-field v-model="setupForm.EH_QUEUE_LIMIT" :label="t('settings.eh.queue_limit')" type="number" /></v-col>
            <v-col cols="12"><v-text-field v-model="setupForm.EH_FILTER_TAG" :label="t('settings.eh.filter_tag')" /></v-col>
          </v-row>
        </v-window-item>

        <v-window-item :value="6">
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

        <v-window-item :value="7">
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

        <v-window-item :value="8">
          <div class="text-h6 font-weight-bold mb-2">{{ t('setup.done.title') }}</div>
          <div class="text-body-2 text-medium-emphasis">{{ t('setup.done.desc') }}</div>
        </v-window-item>

        <v-window-item :value="9">
          <div class="text-h6 font-weight-bold mb-2">{{ t('setup.recovery.title') }}</div>
          <v-alert type="warning" variant="tonal" class="mb-3">{{ t('setup.recovery.warning') }}</v-alert>
          <div class="recovery-codes-list mb-3">
            <div v-for="(code, idx) in recoveryCodes" :key="idx" class="recovery-code-item">{{ code }}</div>
          </div>
          <v-btn color="primary" variant="outlined" @click="copyRecoveryCodes">{{ t('setup.recovery.copy') }}</v-btn>
        </v-window-item>
      </v-window>
      </v-defaults-provider>

      <div class="d-flex justify-space-between" v-if="step > 0">
        <div class="d-flex ga-2">
          <v-btn variant="text" :disabled="step <= 0" @click="goSetupPrev">{{ t('setup.prev') }}</v-btn>
          <v-btn v-if="canAbortWizard" variant="text" color="warning" @click="cancelSetupWizard">{{ t('setup.cancel') }}</v-btn>
        </div>
        <v-btn v-if="step < 8" color="primary" :disabled="(step === 2 && !setupDbValid) || (step === 3 && showAdminCreateStep && !setupAdminValid) || (step === 4 && !setupLrrValid)" :loading="setupBusy" @click="goSetupNext(step)">{{ t('setup.next') }}</v-btn>
        <v-btn v-else-if="step === 8" color="success" :loading="setupBusy" @click="finishSetupWizard">{{ t('setup.finish') }}</v-btn>
        <v-btn v-else color="primary" @click="closeRecoveryStep">{{ t('setup.recovery.acknowledge') }}</v-btn>
      </div>
    </v-card>
  </v-dialog>

  <v-dialog v-model="showFirstRunGuide" max-width="760">
    <v-card class="pa-4" variant="outlined">
      <div class="text-h6 font-weight-bold mb-2">{{ t('setup.after_guide.title') }}</div>
      <div class="text-body-2 text-medium-emphasis mb-4">{{ t('setup.after_guide.desc') }}</div>
      <v-alert type="info" variant="tonal" class="mb-4">{{ t('setup.after_guide.hint') }}</v-alert>
      <div class="d-flex justify-end ga-2">
        <v-btn variant="text" @click="dismissFirstRunGuide">{{ t('setup.after_guide.cancel') }}</v-btn>
        <v-btn color="primary" variant="outlined" @click="openControlAndDismiss">{{ t('setup.after_guide.open_control') }}</v-btn>
      </div>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { completeSetup, getAuthBootstrap, getProviderModels, getSetupStatus, registerAdmin, setCsrfToken, validateSetupDb, validateSetupLrr } from "../api";
import { useAppStore } from "../stores/appStore";
import { useLayoutStore } from "../stores/layoutStore";
import { useSettingsStore } from "../stores/settingsStore";
import brandLogo from "../ico/AutoEhHunterLogo_128.png";
import { buildCookie, parseCookie } from "../utils/helpers";

const { t } = defineProps({ t: { type: Function, required: true } });

const app = useAppStore();
const layout = useLayoutStore();
const settings = useSettingsStore();

const step = ref(0);
const setupBusy = ref(false);
const setupDbValid = ref(false);
const setupLrrValid = ref(false);
const setupIngestModelOptions = ref([]);
const setupLlmModelOptions = ref([]);
const recoveryCodes = ref([]);
const canAbortWizard = ref(false);
const showAdminCreateStep = ref(true);
const adminAlreadyConfigured = ref(false);
const setupAdminValid = ref(false);
const ehCookieParts = ref({ ipb_member_id: "", ipb_pass_hash: "", sk: "", igneous: "" });
const showFirstRunGuide = ref(false);
const siglipNoticeArmed = ref(false);
const lastSiglipStatus = ref("");
const FIRST_RUN_GUIDE_KEY = "aeh_first_run_guide_seen_v1";
const helloCloudFocus = ref({ x: 50, y: 50 });
let helloCloudRaf = 0;
let helloCloudT0 = 0;
const helloCloud = [
  "Hello", "你好", "こんにちは", "안녕하세요", "Hola", "Bonjour", "Hallo", "Ciao", "Olá", "Привет",
  "مرحبا", "नमस्ते", "שלום", "สวัสดี", "Xin chao", "Merhaba", "Hej", "Ahoj", "Szia", "Salut",
  "Sawubona", "Habari", "Jambo", "Konnichiwa", "Selam", "Buna", "Hei", "Moien", "Halo", "Selamat",
  "Mingalaba", "Shalom", "Kia ora", "Talofa", "Namaskaram", "Vanakkam", "Assalamu alaikum", "Zdravo", "Dobar dan", "God dag",
  "Yassas", "Halloj", "Tere", "Sveiki", "Labas", "Haloj", "Bok", "Pozdrav", "Servus", "Aloha",
  "Sannu", "Salve", "Ndewo", "Kamusta", "Marhaba", "Hola a todos",
].map((text, idx) => ({
  text,
  x: ((idx * 37 + 11) % 96) + 2,
  y: ((idx * 53 + 7) % 86) + 7,
  base: 12 + (idx % 5) * 2,
}));
const wizardFieldDefaults = {
  VTextField: { variant: "outlined", density: "comfortable", color: "primary" },
  VSelect: { variant: "outlined", density: "comfortable", color: "primary" },
  VCombobox: { variant: "outlined", density: "comfortable", color: "primary" },
  VTextarea: { variant: "outlined", density: "comfortable", color: "primary" },
};
const setupForm = reactive({
  DATA_UI_LANG: "zh",
  DATA_UI_TIMEZONE: "UTC",
  DATA_UI_THEME_MODE: "system",
  DATA_UI_THEME_PRESET: "modern",
  DATA_UI_THEME_OLED: false,
  POSTGRES_HOST: "localhost",
  POSTGRES_PORT: 5432,
  POSTGRES_DB: "autoeh",
  POSTGRES_USER: "postgres",
  POSTGRES_PASSWORD: "",
  POSTGRES_SSLMODE: "prefer",
  ADMIN_USERNAME: "",
  ADMIN_PASSWORD: "",
  ADMIN_PASSWORD2: "",
  AUTO_DOWNLOAD_SIGLIP: true,
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
  EH_HTTP_PROXY: "",
  EH_HTTPS_PROXY: "",
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

function syncUiPreview() {
  const lang = String(setupForm.DATA_UI_LANG || "zh").trim().toLowerCase() === "en" ? "en" : "zh";
  layout.setLangValue(lang);
  settings.config.DATA_UI_LANG = lang;
  settings.config.DATA_UI_TIMEZONE = String(setupForm.DATA_UI_TIMEZONE || "UTC");
  settings.config.DATA_UI_THEME_MODE = String(setupForm.DATA_UI_THEME_MODE || "system");
  settings.config.DATA_UI_THEME_PRESET = String(setupForm.DATA_UI_THEME_PRESET || "modern");
  settings.config.DATA_UI_THEME_OLED = !!setupForm.DATA_UI_THEME_OLED;
}

function helloWordStyle(item) {
  const fx = helloCloudFocus.value.x;
  const fy = helloCloudFocus.value.y;
  const dx = Number(item.x) - Number(fx);
  const dy = Number(item.y) - Number(fy);
  const d = Math.sqrt(dx * dx + dy * dy);
  const k = Math.max(0, 1 - d / 48);
  const size = Number(item.base) + k * 22;
  const opacity = 0.08 + k * 0.6;
  return {
    left: `${item.x}%`,
    top: `${item.y}%`,
    fontSize: `${size.toFixed(1)}px`,
    opacity: opacity.toFixed(3),
    transform: `translate(-50%, -50%) scale(${(0.9 + k * 0.24).toFixed(3)})`,
  };
}

function _tickHelloCloud(ts) {
  if (!helloCloudT0) helloCloudT0 = ts;
  const t = (ts - helloCloudT0) / 1000;
  helloCloudFocus.value = {
    x: 50 + Math.sin(t * 0.32) * 26 + Math.sin(t * 0.11) * 8,
    y: 50 + Math.cos(t * 0.27) * 20 + Math.sin(t * 0.17) * 6,
  };
  helloCloudRaf = requestAnimationFrame(_tickHelloCloud);
}

function maybeOpenFirstRunGuide() {
  if (typeof window === "undefined") return;
  if (window.localStorage.getItem(FIRST_RUN_GUIDE_KEY) === "1") return;
  showFirstRunGuide.value = true;
}

function dismissFirstRunGuide() {
  showFirstRunGuide.value = false;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(FIRST_RUN_GUIDE_KEY, "1");
  }
}

function openControlAndDismiss() {
  layout.goTab("control");
  dismissFirstRunGuide();
}

async function refreshCanAbortWizard() {
  try {
    const st = await getSetupStatus();
    canAbortWizard.value = !!st?.initialized && !!st?.user_configured;
  } catch {
    canAbortWizard.value = false;
  }
}

async function refreshAdminStepState() {
  try {
    const b = await getAuthBootstrap();
    const configured = !!b?.configured;
    const adminSession = !!b?.is_admin_session;
    showAdminCreateStep.value = !configured || adminSession;
    adminAlreadyConfigured.value = configured;
    setupAdminValid.value = configured;
  } catch {
    showAdminCreateStep.value = true;
    adminAlreadyConfigured.value = false;
    setupAdminValid.value = false;
  }
}

function goSetupPrev() {
  if (step.value === 4 && !showAdminCreateStep.value) {
    step.value = 2;
    return;
  }
  step.value = Math.max(0, step.value - 1);
}

function applySetupFormToConfig() {
  Object.entries(setupForm).forEach(([k, v]) => {
    settings.config[k] = v;
  });
  settings.config.EH_COOKIE = buildCookie(ehCookieParts.value);
  const blocked = Object.entries(settings.ehCategoryAllowMap || {})
    .filter(([, allow]) => !allow)
    .map(([key]) => key);
  settings.config.EH_FILTER_CATEGORY = blocked.join(",");
}

watch(
  () => app.showSetupWizard,
  async (open) => {
    if (!open) return;
    step.value = 0;
    setupDbValid.value = false;
    setupLrrValid.value = false;
    await refreshCanAbortWizard();
    await refreshAdminStepState();
    await settings.loadConfigData();
    Object.assign(setupForm, {
      DATA_UI_LANG: settings.config.DATA_UI_LANG || layout.lang || setupForm.DATA_UI_LANG,
      DATA_UI_TIMEZONE: settings.config.DATA_UI_TIMEZONE || setupForm.DATA_UI_TIMEZONE,
      DATA_UI_THEME_MODE: settings.config.DATA_UI_THEME_MODE || setupForm.DATA_UI_THEME_MODE,
      DATA_UI_THEME_PRESET: settings.config.DATA_UI_THEME_PRESET || setupForm.DATA_UI_THEME_PRESET,
      DATA_UI_THEME_OLED: !!settings.config.DATA_UI_THEME_OLED,
      POSTGRES_HOST: settings.config.POSTGRES_HOST || setupForm.POSTGRES_HOST,
      POSTGRES_PORT: Number(settings.config.POSTGRES_PORT || setupForm.POSTGRES_PORT),
      POSTGRES_DB: settings.config.POSTGRES_DB || setupForm.POSTGRES_DB,
      POSTGRES_USER: settings.config.POSTGRES_USER || setupForm.POSTGRES_USER,
      POSTGRES_PASSWORD: settings.config.POSTGRES_PASSWORD || "",
      POSTGRES_SSLMODE: settings.config.POSTGRES_SSLMODE || "prefer",
      ADMIN_USERNAME: String(app?.authUser?.username || "").trim(),
      ADMIN_PASSWORD: "",
      ADMIN_PASSWORD2: "",
      AUTO_DOWNLOAD_SIGLIP: true,
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
      EH_HTTP_PROXY: settings.config.EH_HTTP_PROXY || "",
      EH_HTTPS_PROXY: settings.config.EH_HTTPS_PROXY || "",
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
    ehCookieParts.value = parseCookie(setupForm.EH_COOKIE || "");
    const blocked = new Set(String(setupForm.EH_FILTER_CATEGORY || "").split(",").map((x) => String(x || "").trim().toLowerCase()).filter(Boolean));
    settings.ehCategoryAllowMap = Object.fromEntries(settings.ehCategoryDefs.map((x) => [x.key, !blocked.has(String(x.key || "").toLowerCase())]));
    syncUiPreview();
  },
  { immediate: true },
);

watch(() => setupForm.DATA_UI_LANG, syncUiPreview);
watch(() => setupForm.DATA_UI_TIMEZONE, syncUiPreview);
watch(() => setupForm.DATA_UI_THEME_MODE, syncUiPreview);
watch(() => setupForm.DATA_UI_THEME_PRESET, syncUiPreview);
watch(() => setupForm.DATA_UI_THEME_OLED, syncUiPreview);

watch(
  () => ({
    status: String(settings.siglipDownload?.status || ""),
    progress: Number(settings.siglipDownload?.progress || 0),
    error: String(settings.siglipDownload?.error || ""),
  }),
  (st) => {
    if (!st.status) return;
    if (!siglipNoticeArmed.value && st.status === "done") {
      lastSiglipStatus.value = st.status;
      return;
    }
    if (!siglipNoticeArmed.value && st.status === "failed") {
      lastSiglipStatus.value = st.status;
      return;
    }
    if (lastSiglipStatus.value === st.status && st.status === "done") return;
    if (lastSiglipStatus.value === st.status && st.status === "failed") return;
    lastSiglipStatus.value = st.status;
    if (st.status === "failed") {
      layout.pushNotice("setup-siglip", t("setup.siglip.notice_title"), t("setup.siglip.notice_failed", { error: st.error || "unknown error" }));
      settings.notify(t("setup.siglip.failed", { error: st.error || "unknown error" }), "warning");
      siglipNoticeArmed.value = false;
      return;
    }
    if (st.status === "done") {
      siglipNoticeArmed.value = false;
      if (Array.isArray(layout.notices)) {
        const it = layout.notices.find((x) => x.type === "setup-siglip");
        if (it?.id) layout.dismissNotice(it.id);
      }
      return;
    }
    siglipNoticeArmed.value = true;
    layout.pushNotice("setup-siglip", t("setup.siglip.notice_title"), t("setup.siglip.notice_running", { progress: st.progress }));
  },
  { deep: true },
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
      await refreshAdminStepState();
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

async function createAdminInSetup() {
  const username = String(setupForm.ADMIN_USERNAME || "").trim();
  const password = String(setupForm.ADMIN_PASSWORD || "");
  const password2 = String(setupForm.ADMIN_PASSWORD2 || "");
  if (!username || !password) {
    settings.notify(String(t("auth.register.hint") || "missing username/password"), "warning");
    return;
  }
  if (password !== password2) {
    settings.notify(t("auth.profile.password_mismatch"), "warning");
    return;
  }
  setupBusy.value = true;
  try {
    const res = await registerAdmin(username, password);
    setCsrfToken(res?.session?.csrf_token || "");
    setupAdminValid.value = true;
    settings.notify(t("setup.admin.created"), "success");
    await app.bootstrap();
    await refreshAdminStepState();
  } catch (e) {
    setupAdminValid.value = false;
    settings.notify(String(e?.response?.data?.detail || e), "warning");
  } finally {
    setupBusy.value = false;
  }
}

async function maybeTriggerSiglipDownload() {
  if (!setupForm.AUTO_DOWNLOAD_SIGLIP) return;
  try {
    await settings.loadModelStatus();
    const hasSiglip = !!settings.modelStatus?.siglip?.usable;
    const hasDeps = !!settings.modelStatus?.runtime_deps?.ready;
    if (hasSiglip && hasDeps) return;
    settings.notify(t("setup.siglip.downloading"), "info");
    siglipNoticeArmed.value = true;
    layout.pushNotice("setup-siglip", t("setup.siglip.notice_title"), t("setup.siglip.notice_running", { progress: Number(settings.siglipDownload.progress || 0) }));
    await settings.downloadSiglipAction();
  } catch (e) {
    settings.notify(String(e?.response?.data?.detail || e), "warning");
  }
}

async function goSetupNext(currentStep) {
  setupBusy.value = true;
  try {
    if ([5, 6, 7].includes(Number(currentStep))) {
      applySetupFormToConfig();
      await settings.saveConfig();
    }
    const cur = Number(currentStep);
    if (cur === 2 && !showAdminCreateStep.value) {
      step.value = 4;
      return;
    }
    if (cur === 3 && showAdminCreateStep.value) {
      await maybeTriggerSiglipDownload();
    }
    step.value = cur + 1;
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
      step.value = 9;
    } else {
      app.closeSetupWizard();
      settings.notify(t('setup.done.toast'), 'success');
      maybeOpenFirstRunGuide();
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
  maybeOpenFirstRunGuide();
}

async function cancelSetupWizard() {
  try {
    await settings.loadConfigData();
    if (settings.config.DATA_UI_LANG === "en" || settings.config.DATA_UI_LANG === "zh") {
      layout.setLangValue(settings.config.DATA_UI_LANG);
    }
  } catch {
    // ignore reload failures on cancel
  }
  app.closeSetupWizard();
}

function copyRecoveryCodes() {
  const text = recoveryCodes.value.join('\n');
  navigator.clipboard.writeText(text).then(() => {
    settings.notify(t('setup.recovery.copied'), 'success');
  }).catch(() => {
    settings.notify(t('setup.recovery.copy_failed'), 'warning');
  });
}

onMounted(() => {
  helloCloudRaf = requestAnimationFrame(_tickHelloCloud);
});

onBeforeUnmount(() => {
  if (helloCloudRaf) cancelAnimationFrame(helloCloudRaf);
  helloCloudRaf = 0;
});
</script>

<style scoped>
.setup-wizard-wrap {
  min-height: 100vh;
  background: linear-gradient(160deg, rgba(var(--v-theme-surface), 0.98), rgba(var(--v-theme-background), 0.98));
}

.setup-welcome {
  position: relative;
  min-height: 68vh;
  overflow: hidden;
}

.hello-cloud {
  position: absolute;
  inset: 0;
  pointer-events: none;
  user-select: none;
}

.hello-word {
  position: absolute;
  color: rgba(var(--v-theme-on-surface), 0.35);
  font-weight: 700;
  letter-spacing: 0.02em;
  transition: transform 320ms ease, opacity 320ms ease, font-size 320ms ease;
}

.setup-welcome-logo {
  width: 96px;
  height: 96px;
  border-radius: 24px;
}

.setup-welcome-next {
  box-shadow: 0 10px 26px rgba(var(--v-theme-primary), 0.35);
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 16px;
}

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
