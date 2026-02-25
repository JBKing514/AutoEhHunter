import { computed, ref, watch } from "vue";
import { defineStore } from "pinia";
import {
  clearRecommendProfile,
  clearRecommendTouches,
  clearRuntimeDeps,
  clearSiglip,
  clearThumbCache,
  downloadSiglip,
  getConfig,
  getConfigSchema,
  getDevSchemaStatus,
  getModelStatus,
  getHomeTagSuggest,
  getProviderModels,
  getSiglipDownloadStatus,
  getSkills,
  getThumbCacheStats,
  getTranslationStatus,
  injectDevSchema,
  updateConfig,
  uploadDevSchema,
  uploadSkillPlugin,
  uploadTranslationFile,
} from "../api";
import { useToastStore } from "./useToastStore";
import { useControlStore } from "./controlStore";
import { useAppStore } from "./appStore";
import { buildCookie, parseCookie, parseCsv } from "../utils/helpers";

export const useSettingsStore = defineStore("settings", () => {
  const toast = useToastStore();
  const controlStore = useControlStore();
  const appStore = useAppStore();

  const config = ref({});
  const schema = ref({});
  const configMeta = ref({});
  const secretState = ref({});
  const settingsTab = ref("general");
  const llmModelOptions = ref([]);
  const ingestModelOptions = ref([]);
  const builtinSkills = ref([]);
  const userSkills = ref([]);
  const pluginFiles = ref([]);
  const pluginUploadRef = ref(null);
  const devSchemaUploadRef = ref(null);
  const devSchemaStatus = ref({ exists: false, size_kb: 0, path: "", updated_at: "" });
  const devSchemaInjecting = ref(false);
  const thumbCacheStats = ref({ files: 0, mb: 0, latest_at: "-" });
  const translationStatus = ref({ repo: "", head_sha: "", fetched_at: "-", manual_file: { path: "", exists: false, size: 0, updated_at: "-" } });
  const translationUploadRef = ref(null);
  const modelStatus = ref({
    siglip: { path: "", size_mb: 0, usable: false },
    runtime_deps: { path: "", size_mb: 0, ready: false },
  });
  const siglipDownload = ref({ task_id: "", status: "", progress: 0, stage: "", error: "", logs: [] });
  const cookieParts = ref({ ipb_member_id: "", ipb_pass_hash: "", sk: "", igneous: "" });
  const ehFilterTags = ref([]);
  const newEhTag = ref("");
  const ehTagSuggestions = ref([]);
  const ehCategoryDefs = [
    { key: "doujinshi", label: "Doujinshi", color: "#ff5252" },
    { key: "manga", label: "Manga", color: "#fdb813" },
    { key: "image set", label: "Image Set", color: "#4f54d1" },
    { key: "game cg", label: "Game CG", color: "#00c700" },
    { key: "artist cg", label: "Artist CG", color: "#d7e600" },
    { key: "cosplay", label: "Cosplay", color: "#8756e6" },
    { key: "non-h", label: "Non-H", color: "#66bcd3" },
    { key: "asian porn", label: "Asian Porn", color: "#de7de5" },
    { key: "western", label: "Western", color: "#18e61f" },
    { key: "misc", label: "Misc", color: "#473f3f" },
  ];
  const ehCategoryAllowMap = ref(Object.fromEntries(ehCategoryDefs.map((x) => [x.key, true])));
  const themeOptions = [
    { title: "Modern", value: "modern" },
    { title: "Ocean", value: "ocean" },
    { title: "Sunset", value: "sunset" },
    { title: "Forest", value: "forest" },
    { title: "Slate", value: "slate" },
    { title: "Custom", value: "custom" },
  ];
  const timezoneOptions = ref(["UTC", "Asia/Shanghai", "Asia/Tokyo", "America/New_York", "Europe/Berlin"]);

  let _t = (k, _vars = {}) => k;
  let _setLang = null;
  let siglipPollTimer = null;
  let syncing = false;

  const themeModeOptions = computed(() => [
    { title: _t("theme.mode.system"), value: "system" },
    { title: _t("theme.mode.light"), value: "light" },
    { title: _t("theme.mode.dark"), value: "dark" },
  ]);

  const llmReady = computed(() => {
    const llmBase = String(config.value.LLM_API_BASE || "").trim();
    const llmModel = String(config.value.LLM_MODEL_CUSTOM || config.value.LLM_MODEL || "").trim();
    return !!(llmBase && llmModel);
  });

  const limitedModeMessages = computed(() => {
    const out = [];
    const ingestBase = String(config.value.INGEST_API_BASE || "").trim();
    const ingestVl = String(config.value.INGEST_VL_MODEL_CUSTOM || config.value.INGEST_VL_MODEL || "").trim();
    const ingestEmb = String(config.value.INGEST_EMB_MODEL_CUSTOM || config.value.INGEST_EMB_MODEL || "").trim();
    if (!ingestBase || !ingestVl || !ingestEmb) out.push(_t("settings.limited_mode.ingest"));
    const llmBase = String(config.value.LLM_API_BASE || "").trim();
    const llmModel = String(config.value.LLM_MODEL_CUSTOM || config.value.LLM_MODEL || "").trim();
    const embModel = String(config.value.EMB_MODEL_CUSTOM || config.value.EMB_MODEL || "").trim();
    if (!llmBase || !llmModel || !embModel) out.push(_t("settings.limited_mode.llm"));
    return out;
  });

  const health = computed(() => controlStore.health || { database: {}, services: {} });
  const accountForm = computed(() => appStore.accountForm);

  function init(deps = {}) {
    if (typeof deps.t === "function") _t = deps.t;
    if (typeof deps.setLang === "function") _setLang = deps.setLang;
  }

  function t(key, vars = {}) {
    return _t(key, vars);
  }

  function notify(text, color = "success") {
    toast.open(text, color);
  }

  function toggleCategory(key) {
    ehCategoryAllowMap.value[key] = !ehCategoryAllowMap.value[key];
  }

  function categoryStyle(key, color) {
    const on = !!ehCategoryAllowMap.value[key];
    return { backgroundColor: on ? color : "#424242", color: "#ffffff", opacity: on ? 1 : 0.45 };
  }

  function addEhTag() {
    const v = String(newEhTag.value || "").trim().toLowerCase();
    if (!v) return;
    if (!ehFilterTags.value.includes(v)) ehFilterTags.value.push(v);
    newEhTag.value = "";
  }

  function removeEhTag(tag) {
    ehFilterTags.value = ehFilterTags.value.filter((x) => x !== tag);
  }

  async function loadEhTagSuggestions() {
    const q = String(newEhTag.value || "").trim();
    if (q.length < 2) {
      ehTagSuggestions.value = [];
      return;
    }
    try {
      const res = await getHomeTagSuggest({
        q,
        limit: 10,
        ui_lang: String(config.value.DATA_UI_LANG || "zh"),
      });
      ehTagSuggestions.value = Array.isArray(res?.items) ? res.items : [];
    } catch {
      ehTagSuggestions.value = [];
    }
  }

  function labelFor(key) {
    const map = {
      POSTGRES_HOST: "settings.pg.host",
      POSTGRES_PORT: "settings.pg.port",
      POSTGRES_DB: "settings.pg.db",
      POSTGRES_USER: "settings.pg.user",
      POSTGRES_PASSWORD: "settings.pg.password",
      POSTGRES_SSLMODE: "settings.pg.sslmode",
      LRR_BASE: "settings.lrr.base",
      OPENAI_HEALTH_URL: "settings.openai.health",
      LRR_API_KEY: "settings.lrr.api_key",
      INGEST_API_KEY: "settings.provider.ingest_api_key",
      DATA_UI_TIMEZONE: "settings.ui.timezone",
      DATA_UI_THEME_MODE: "settings.ui.theme_mode",
      DATA_UI_THEME_PRESET: "settings.ui.theme_preset",
      DATA_UI_THEME_OLED: "settings.ui.theme_oled",
      DATA_UI_DEVELOPER_MODE: "settings.ui.developer_mode",
      DATA_UI_THEME_CUSTOM_PRIMARY: "settings.ui.custom_primary",
      DATA_UI_THEME_CUSTOM_SECONDARY: "settings.ui.custom_secondary",
      DATA_UI_THEME_CUSTOM_ACCENT: "settings.ui.custom_accent",
      REC_PROFILE_DAYS: "settings.rec.profile_days",
      REC_CANDIDATE_HOURS: "settings.rec.candidate_hours",
      REC_CLUSTER_K: "settings.rec.cluster_k",
      REC_CLUSTER_CACHE_TTL_S: "settings.rec.cache_ttl",
      REC_TAG_WEIGHT: "settings.rec.tag_weight",
      REC_VISUAL_WEIGHT: "settings.rec.visual_weight",
      REC_FEEDBACK_WEIGHT: "settings.rec.feedback_weight",
      REC_PROFILE_WEIGHT: "settings.rec.profile_weight",
      REC_TEMPERATURE: "settings.rec.temperature",
      REC_CANDIDATE_LIMIT: "settings.rec.candidate_limit",
      REC_TAG_FLOOR_SCORE: "settings.rec.tag_floor",
      REC_TOUCH_PENALTY_PCT: "settings.rec.touch_penalty_pct",
      REC_IMPRESSION_PENALTY_PCT: "settings.rec.impression_penalty_pct",
      REC_DYNAMIC_EXPAND_ENABLED: "settings.rec.dynamic_expand_enabled",
      REC_SHOW_JPN_TITLE: "settings.rec.show_jpn_title",
      REC_USE_TRANSLATED_TAGS: "settings.rec.use_translated_tags",
      SEARCH_TEXT_WEIGHT: "settings.search.text_weight",
      SEARCH_VISUAL_WEIGHT: "settings.search.visual_weight",
      SEARCH_MIXED_TEXT_WEIGHT: "settings.search.mixed_text_weight",
      SEARCH_MIXED_VISUAL_WEIGHT: "settings.search.mixed_visual_weight",
      SEARCH_NL_ENABLED: "settings.search.nl_enabled",
      SEARCH_TAG_SMART_ENABLED: "settings.search.tag_smart_enabled",
      SEARCH_TAG_HARD_FILTER: "settings.search.tag_hard_filter",
      SEARCH_RESULT_SIZE: "settings.search.result_size",
      SEARCH_RESULT_INFINITE: "settings.search.result_infinite",
      SEARCH_WEIGHT_VISUAL: "settings.search.weight_visual",
      SEARCH_WEIGHT_EH_VISUAL: "settings.search.weight_eh_visual",
      SEARCH_WEIGHT_DESC: "settings.search.weight_desc",
      SEARCH_WEIGHT_TEXT: "settings.search.weight_text",
      SEARCH_WEIGHT_EH_TEXT: "settings.search.weight_eh_text",
      SEARCH_WEIGHT_PLOT_VISUAL: "settings.search.weight_plot_visual",
      SEARCH_WEIGHT_PLOT_EH_VISUAL: "settings.search.weight_plot_eh_visual",
      SEARCH_WEIGHT_PLOT_DESC: "settings.search.weight_plot_desc",
      SEARCH_WEIGHT_PLOT_TEXT: "settings.search.weight_plot_text",
      SEARCH_WEIGHT_PLOT_EH_TEXT: "settings.search.weight_plot_eh_text",
      SEARCH_WEIGHT_MIXED_VISUAL: "settings.search.weight_mixed_visual",
      SEARCH_WEIGHT_MIXED_EH_VISUAL: "settings.search.weight_mixed_eh_visual",
      SEARCH_WEIGHT_MIXED_DESC: "settings.search.weight_mixed_desc",
      SEARCH_WEIGHT_MIXED_TEXT: "settings.search.weight_mixed_text",
      SEARCH_WEIGHT_MIXED_EH_TEXT: "settings.search.weight_mixed_eh_text",
      SEARCH_TAG_FUZZY_THRESHOLD: "settings.search.fuzzy_threshold",
      TEXT_INGEST_PRUNE_NOT_SEEN: "settings.text_ingest.prune",
      WORKER_ONLY_MISSING: "settings.worker.only_missing",
      TAG_TRANSLATION_REPO: "settings.translation.repo",
      TAG_TRANSLATION_AUTO_UPDATE_HOURS: "settings.translation.auto_update_hours",
      LRR_READS_HOURS: "settings.lrr.reads_hours",
      EH_BASE_URL: "settings.eh.base_url",
      EH_FETCH_MAX_PAGES: "settings.eh.max_pages",
      EH_REQUEST_SLEEP: "settings.eh.request_sleep",
      EH_SAMPLING_DENSITY: "settings.eh.sampling_density",
      EH_USER_AGENT: "settings.eh.user_agent",
      EH_HTTP_PROXY: "settings.eh.http_proxy",
      EH_HTTPS_PROXY: "settings.eh.https_proxy",
      EH_MIN_RATING: "settings.eh.min_rating",
      EH_FILTER_TAG: "settings.eh.filter_tag",
      TEXT_INGEST_BATCH_SIZE: "settings.text_ingest.batch",
      EH_QUEUE_LIMIT: "settings.eh.queue_limit",
      LLM_API_BASE: "settings.provider.llm_api_base",
      LLM_API_KEY: "settings.provider.llm_api_key",
      LLM_TIMEOUT_S: "settings.provider.llm_timeout_s",
      LLM_MAX_TOKENS_CHAT: "settings.provider.llm_max_tokens_chat",
      LLM_MAX_TOKENS_INTENT: "settings.provider.llm_max_tokens_intent",
      LLM_MAX_TOKENS_TAG_EXTRACT: "settings.provider.llm_max_tokens_tag_extract",
      LLM_MAX_TOKENS_PROFILE: "settings.provider.llm_max_tokens_profile",
      LLM_MAX_TOKENS_REPORT: "settings.provider.llm_max_tokens_report",
      LLM_MAX_TOKENS_SEARCH_NARRATIVE: "settings.provider.llm_max_tokens_search_narrative",
      LLM_MODEL: "settings.provider.llm_model",
      LLM_MODEL_CUSTOM: "settings.provider.llm_model_custom",
      EMB_MODEL: "settings.provider.emb_model",
      EMB_MODEL_CUSTOM: "settings.provider.emb_model_custom",
      INGEST_API_BASE: "settings.provider.ingest_api_base",
      INGEST_VL_MODEL: "settings.provider.ingest_vl_model",
      INGEST_EMB_MODEL: "settings.provider.ingest_emb_model",
      INGEST_VL_MODEL_CUSTOM: "settings.provider.ingest_vl_model_custom",
      INGEST_EMB_MODEL_CUSTOM: "settings.provider.ingest_emb_model_custom",
      SIGLIP_MODEL: "settings.provider.siglip_model",
      WORKER_BATCH: "settings.provider.worker_batch",
      WORKER_SLEEP: "settings.provider.worker_sleep",
      MEMORY_SHORT_TERM_ENABLED: "settings.memory.short_term_enabled",
      MEMORY_LONG_TERM_ENABLED: "settings.memory.long_term_enabled",
      MEMORY_SEMANTIC_ENABLED: "settings.memory.semantic_enabled",
      MEMORY_SHORT_TERM_LIMIT: "settings.memory.short_term_limit",
      MEMORY_LONG_TERM_TOP_TAGS: "settings.memory.long_term_top_tags",
      MEMORY_SEMANTIC_TOP_FACTS: "settings.memory.semantic_top_facts",
    };
    const tk = map[key];
    return tk ? t(tk) : key;
  }

  function secretHint(key) {
    return secretState.value[key] ? t("settings.secret.present") : t("settings.secret.empty");
  }

  function getGalleryTitle(item) {
    if (config.value.REC_SHOW_JPN_TITLE && item.subtitle) {
      return item.subtitle;
    }
    return item.title || "-";
  }

  function normalizeSearchWeights(prefixA, prefixB, changedKey) {
    const a = Number(config.value[prefixA] ?? 0.5);
    const b = Number(config.value[prefixB] ?? 0.5);
    const ca = Number.isFinite(a) ? Math.max(0, Math.min(1, a)) : 0.5;
    const cb = Number.isFinite(b) ? Math.max(0, Math.min(1, b)) : 0.5;
    if (changedKey === prefixA) {
      config.value[prefixA] = ca;
      config.value[prefixB] = Number((1 - ca).toFixed(4));
    } else if (changedKey === prefixB) {
      config.value[prefixB] = cb;
      config.value[prefixA] = Number((1 - cb).toFixed(4));
    } else {
      const sum = ca + cb;
      config.value[prefixA] = sum <= 0 ? 0.5 : Number((ca / sum).toFixed(4));
      config.value[prefixB] = sum <= 0 ? 0.5 : Number((cb / sum).toFixed(4));
    }
  }

  function normalizeAgentChannelWeights(changedKey, keys = ["SEARCH_WEIGHT_VISUAL", "SEARCH_WEIGHT_EH_VISUAL", "SEARCH_WEIGHT_DESC", "SEARCH_WEIGHT_TEXT", "SEARCH_WEIGHT_EH_TEXT"]) {
    if (syncing) return;
    syncing = true;
    try {
      const vals = keys.map((k) => {
        const n = Number(config.value[k] ?? 0);
        return Number.isFinite(n) ? Math.max(0, Math.min(5, n)) : 0;
      });
      const idx = keys.indexOf(changedKey);
      const target = idx >= 0 ? vals[idx] : vals[0];
      const restSum = vals.reduce((a, b, i) => a + (i === idx ? 0 : b), 0);
      const budget = Math.max(0, 5 - target);
      const scaled = vals.map((v, i) => {
        if (i === idx) return target;
        if (restSum <= 1e-9) return budget / Math.max(1, keys.length - 1);
        return (v / restSum) * budget;
      });
      keys.forEach((k, i) => {
        config.value[k] = Number(scaled[i].toFixed(4));
      });
    } finally {
      syncing = false;
    }
  }

  function normalizeRecommendWeights(changedKey) {
    const a = Number(config.value.REC_TAG_WEIGHT ?? 0.55);
    const b = Number(config.value.REC_VISUAL_WEIGHT ?? 0.45);
    const c = Number(config.value.REC_FEEDBACK_WEIGHT ?? 0.0);
    const ca = Number.isFinite(a) ? Math.max(0, Math.min(1, a)) : 0.55;
    const cb = Number.isFinite(b) ? Math.max(0, Math.min(1, b)) : 0.45;
    const cc = Number.isFinite(c) ? Math.max(0, Math.min(1, c)) : 0.0;

    if (changedKey === "REC_TAG_WEIGHT") {
      const remaining = 1 - ca;
      config.value.REC_TAG_WEIGHT = ca;
      config.value.REC_VISUAL_WEIGHT = Number((remaining * cb / (cb + cc || 1)).toFixed(4));
      config.value.REC_FEEDBACK_WEIGHT = Number((remaining * cc / (cb + cc || 1)).toFixed(4));
    } else if (changedKey === "REC_VISUAL_WEIGHT") {
      const remaining = 1 - cb;
      config.value.REC_VISUAL_WEIGHT = cb;
      config.value.REC_TAG_WEIGHT = Number((remaining * ca / (ca + cc || 1)).toFixed(4));
      config.value.REC_FEEDBACK_WEIGHT = Number((remaining * cc / (ca + cc || 1)).toFixed(4));
    } else if (changedKey === "REC_FEEDBACK_WEIGHT") {
      const remaining = 1 - cc;
      config.value.REC_FEEDBACK_WEIGHT = cc;
      config.value.REC_TAG_WEIGHT = Number((remaining * ca / (ca + cb || 1)).toFixed(4));
      config.value.REC_VISUAL_WEIGHT = Number((remaining * cb / (ca + cb || 1)).toFixed(4));
    } else {
      const sum = ca + cb + cc;
      if (sum <= 0) {
        config.value.REC_TAG_WEIGHT = 0.55;
        config.value.REC_VISUAL_WEIGHT = 0.45;
        config.value.REC_FEEDBACK_WEIGHT = 0.0;
      } else {
        config.value.REC_TAG_WEIGHT = Number((ca / sum).toFixed(4));
        config.value.REC_VISUAL_WEIGHT = Number((cb / sum).toFixed(4));
        config.value.REC_FEEDBACK_WEIGHT = Number((cc / sum).toFixed(4));
      }
    }
  }

  function resetSearchWeightPresets() {
    config.value.SEARCH_WEIGHT_VISUAL = 2.0;
    config.value.SEARCH_WEIGHT_EH_VISUAL = 1.6;
    config.value.SEARCH_WEIGHT_DESC = 0.8;
    config.value.SEARCH_WEIGHT_TEXT = 0.7;
    config.value.SEARCH_WEIGHT_EH_TEXT = 0.7;
    config.value.SEARCH_WEIGHT_PLOT_VISUAL = 0.6;
    config.value.SEARCH_WEIGHT_PLOT_EH_VISUAL = 0.5;
    config.value.SEARCH_WEIGHT_PLOT_DESC = 2.0;
    config.value.SEARCH_WEIGHT_PLOT_TEXT = 0.9;
    config.value.SEARCH_WEIGHT_PLOT_EH_TEXT = 0.9;
    config.value.SEARCH_WEIGHT_MIXED_VISUAL = 1.2;
    config.value.SEARCH_WEIGHT_MIXED_EH_VISUAL = 1.0;
    config.value.SEARCH_WEIGHT_MIXED_DESC = 1.4;
    config.value.SEARCH_WEIGHT_MIXED_TEXT = 0.9;
    config.value.SEARCH_WEIGHT_MIXED_EH_TEXT = 0.9;
  }

  function resetRecommendPreset() {
    config.value.REC_TEMPERATURE = 0.3;
    config.value.REC_TAG_WEIGHT = 0.55;
    config.value.REC_VISUAL_WEIGHT = 0.45;
    config.value.REC_FEEDBACK_WEIGHT = 0.0;
    normalizeRecommendWeights();
  }

  async function loadConfigData() {
    const [cfg, sch] = await Promise.all([getConfig(), getConfigSchema()]);
    const schemaMap = sch.schema || {};
    const normalized = {};
    Object.entries(cfg.values || {}).forEach(([key, val]) => {
      normalized[key] = schemaMap[key]?.type === "bool" ? String(val).toLowerCase() === "1" || String(val).toLowerCase() === "true" : val;
    });
    config.value = normalized;
    secretState.value = cfg.secret_state || {};
    configMeta.value = cfg.meta || {};
    schema.value = schemaMap;
    cookieParts.value = parseCookie(config.value.EH_COOKIE || "");
    ehFilterTags.value = parseCsv(config.value.EH_FILTER_TAG || "");
    const blocked = new Set(parseCsv(config.value.EH_FILTER_CATEGORY || "").map((x) => x.toLowerCase()));
    ehCategoryAllowMap.value = Object.fromEntries(ehCategoryDefs.map((x) => [x.key, !blocked.has(x.key)]));
    if (_setLang && (config.value.DATA_UI_LANG === "en" || config.value.DATA_UI_LANG === "zh")) _setLang(config.value.DATA_UI_LANG);
    if (!config.value.DATA_UI_THEME_MODE) config.value.DATA_UI_THEME_MODE = "system";
    if (!config.value.DATA_UI_THEME_PRESET) config.value.DATA_UI_THEME_PRESET = "modern";
    if (config.value.DATA_UI_DEVELOPER_MODE === undefined) config.value.DATA_UI_DEVELOPER_MODE = false;
    if (!config.value.DATA_UI_TIMEZONE) config.value.DATA_UI_TIMEZONE = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    if (!config.value.DATA_UI_THEME_CUSTOM_PRIMARY) config.value.DATA_UI_THEME_CUSTOM_PRIMARY = "#2563eb";
    if (!config.value.DATA_UI_THEME_CUSTOM_SECONDARY) config.value.DATA_UI_THEME_CUSTOM_SECONDARY = "#0ea5e9";
    if (!config.value.DATA_UI_THEME_CUSTOM_ACCENT) config.value.DATA_UI_THEME_CUSTOM_ACCENT = "#f59e0b";
    if (config.value.REC_TEMPERATURE === undefined || config.value.REC_TEMPERATURE === null || config.value.REC_TEMPERATURE === "") {
      config.value.REC_TEMPERATURE = 0.3;
    }
    if (config.value.REC_PROFILE_WEIGHT === undefined || config.value.REC_PROFILE_WEIGHT === null || config.value.REC_PROFILE_WEIGHT === "") {
      config.value.REC_PROFILE_WEIGHT = 0.18;
    }
    if (config.value.REC_TOUCH_PENALTY_PCT === undefined || config.value.REC_TOUCH_PENALTY_PCT === null || config.value.REC_TOUCH_PENALTY_PCT === "") {
      config.value.REC_TOUCH_PENALTY_PCT = 35;
    }
    if (config.value.REC_IMPRESSION_PENALTY_PCT === undefined || config.value.REC_IMPRESSION_PENALTY_PCT === null || config.value.REC_IMPRESSION_PENALTY_PCT === "") {
      config.value.REC_IMPRESSION_PENALTY_PCT = 3;
    }
    if (config.value.REC_DYNAMIC_EXPAND_ENABLED === undefined) {
      config.value.REC_DYNAMIC_EXPAND_ENABLED = true;
    }
    if (config.value.REC_USE_TRANSLATED_TAGS === undefined) {
      config.value.REC_USE_TRANSLATED_TAGS = false;
    }
    // Memory defaults
    if (config.value.MEMORY_SHORT_TERM_ENABLED === undefined) config.value.MEMORY_SHORT_TERM_ENABLED = true;
    if (config.value.MEMORY_LONG_TERM_ENABLED === undefined) config.value.MEMORY_LONG_TERM_ENABLED = true;
    if (config.value.MEMORY_SEMANTIC_ENABLED === undefined) config.value.MEMORY_SEMANTIC_ENABLED = true;
    if (!config.value.MEMORY_SHORT_TERM_LIMIT) config.value.MEMORY_SHORT_TERM_LIMIT = 12;
    if (config.value.MEMORY_LONG_TERM_TOP_TAGS === undefined || config.value.MEMORY_LONG_TERM_TOP_TAGS === null || config.value.MEMORY_LONG_TERM_TOP_TAGS === "") config.value.MEMORY_LONG_TERM_TOP_TAGS = 8;
    if (config.value.MEMORY_SEMANTIC_TOP_FACTS === undefined || config.value.MEMORY_SEMANTIC_TOP_FACTS === null || config.value.MEMORY_SEMANTIC_TOP_FACTS === "") config.value.MEMORY_SEMANTIC_TOP_FACTS = 8;
    if (typeof Intl.supportedValuesOf === "function") {
      try {
        const zones = Intl.supportedValuesOf("timeZone");
        if (Array.isArray(zones) && zones.length) timezoneOptions.value = zones;
      } catch {
        // ignore
      }
    }
    await Promise.all([reloadIngestModels(), reloadLlmModels(), loadSkillsData(), loadDevSchemaData()]);
  }

  async function saveConfig() {
    const blocked = Object.entries(ehCategoryAllowMap.value).filter(([, allow]) => !allow).map(([key]) => key);
    const payload = {
      ...config.value,
      EH_COOKIE: buildCookie(cookieParts.value),
      EH_FILTER_TAG: ehFilterTags.value.join(","),
      EH_FILTER_CATEGORY: blocked.join(","),
    };
    const res = await updateConfig(payload);
    notify(res.saved_db ? t("settings.saved_db") : t("settings.saved_db_failed", { reason: res.db_error || "n/a" }), res.saved_db ? "success" : "warning");
    await loadConfigData();
  }

  async function reloadIngestModels() {
    const base = String(config.value.INGEST_API_BASE || "").trim();
    if (!base) {
      ingestModelOptions.value = [];
      return;
    }
    try {
      const res = await getProviderModels(base, String(config.value.INGEST_API_KEY || "").trim());
      ingestModelOptions.value = Array.isArray(res.models) ? res.models : [];
    } catch {
      ingestModelOptions.value = [];
    }
  }

  async function reloadLlmModels() {
    const base = String(config.value.LLM_API_BASE || "").trim();
    if (!base) {
      llmModelOptions.value = [];
      return;
    }
    try {
      const res = await getProviderModels(base, String(config.value.LLM_API_KEY || "").trim());
      llmModelOptions.value = Array.isArray(res.models) ? res.models : [];
    } catch {
      llmModelOptions.value = [];
    }
  }

  async function loadThumbCacheStats() {
    thumbCacheStats.value = await getThumbCacheStats();
  }

  async function clearThumbCacheAction() {
    try {
      const res = await clearThumbCache();
      notify(t("settings.cache.cleared", { n: res.deleted || 0 }), "success");
      await loadThumbCacheStats();
    } catch (e) {
      notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  async function loadTranslationStatus() {
    translationStatus.value = await getTranslationStatus();
  }

  async function onTranslationUploadChange(event) {
    const file = event?.target?.files?.[0];
    if (!file) return;
    try {
      await uploadTranslationFile(file);
      notify(t("settings.translation.uploaded"), "success");
      await loadTranslationStatus();
    } catch (e) {
      notify(String(e?.response?.data?.detail || e), "warning");
    } finally {
      if (translationUploadRef.value) translationUploadRef.value.value = "";
    }
  }

  async function loadModelStatus() {
    const res = await getModelStatus();
    if (res && typeof res === "object" && res.model) {
      modelStatus.value = res.model || modelStatus.value;
      if (res.download && typeof res.download === "object") {
        siglipDownload.value = { ...siglipDownload.value, ...res.download };
      }
      return;
    }
    modelStatus.value = res || modelStatus.value;
  }

  async function pollSiglipTask(taskId) {
    if (!taskId) return;
    if (siglipPollTimer) clearInterval(siglipPollTimer);
    siglipPollTimer = setInterval(async () => {
      try {
        const res = await getSiglipDownloadStatus(taskId);
        const st = res.status || {};
        siglipDownload.value = { ...siglipDownload.value, ...st };
        modelStatus.value = res.model || modelStatus.value;
        if (st.status === "done" || st.status === "failed") {
          clearInterval(siglipPollTimer);
          siglipPollTimer = null;
          notify(st.status === "done" ? t("settings.model.siglip_downloaded") : String(st.error || "download failed"), st.status === "done" ? "success" : "warning");
        }
      } catch {
        // ignore
      }
    }, 1800);
  }

  async function downloadSiglipAction() {
    try {
      const res = await downloadSiglip({ model_id: String(config.value.SIGLIP_MODEL || "google/siglip-so400m-patch14-384") });
      const tid = String(res.task_id || "");
      if (tid) {
        siglipDownload.value = { ...(res.status || {}), task_id: tid };
        await pollSiglipTask(tid);
      }
    } catch (e) {
      notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  async function clearRuntimeDepsAction() {
    try {
      const res = await clearRuntimeDeps();
      notify(t("settings.model.runtime_deps_cleared", { mb: res.freed_mb ?? 0 }), "success");
      await loadModelStatus();
    } catch (e) {
      notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  async function clearSiglipAction() {
    try {
      const res = await clearSiglip();
      notify(t("settings.model.siglip_cleared", { mb: res.freed_mb ?? 0 }), "success");
      await loadModelStatus();
    } catch (e) {
      notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  async function clearRecommendTouchesAction() {
    try {
      const res = await clearRecommendTouches();
      notify(t("settings.recommend.touch_cleared", { n: Number(res.deleted || 0) }), "success");
    } catch (e) {
      notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  async function clearRecommendProfileAction() {
    try {
      const res = await clearRecommendProfile();
      notify(t("settings.recommend.profile_cleared", { n: Number(res.deleted || 0) }), "success");
    } catch (e) {
      notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  async function loadSkillsData() {
    try {
      const res = await getSkills();
      builtinSkills.value = Array.isArray(res.builtin) ? res.builtin : [];
      userSkills.value = Array.isArray(res.user) ? res.user : [];
      pluginFiles.value = Array.isArray(res.files) ? res.files : [];
    } catch {
      builtinSkills.value = [];
      userSkills.value = [];
      pluginFiles.value = [];
    }
  }

  async function onPluginUploadChange(event) {
    const file = event?.target?.files?.[0];
    if (!file) return;
    try {
      await uploadSkillPlugin(file);
      notify(t("skills.uploaded"), "success");
      await loadSkillsData();
    } catch (e) {
      notify(String(e?.response?.data?.detail || e), "warning");
    } finally {
      if (pluginUploadRef.value) pluginUploadRef.value.value = "";
    }
  }

  async function loadDevSchemaData() {
    if (!config.value.DATA_UI_DEVELOPER_MODE) {
      devSchemaStatus.value = { exists: false, size_kb: 0, path: "", updated_at: "" };
      return;
    }
    try {
      const res = await getDevSchemaStatus();
      devSchemaStatus.value = res.status || { exists: false, size_kb: 0, path: "", updated_at: "" };
    } catch {
      devSchemaStatus.value = { exists: false, size_kb: 0, path: "", updated_at: "" };
    }
  }

  async function onDevSchemaUploadChange(event) {
    const file = event?.target?.files?.[0];
    if (!file) return;
    try {
      await uploadDevSchema(file);
      notify(t("settings.developer.uploaded"), "success");
      await loadDevSchemaData();
    } catch (e) {
      notify(String(e?.response?.data?.detail || e), "warning");
    } finally {
      if (devSchemaUploadRef.value) devSchemaUploadRef.value.value = "";
    }
  }

  async function injectDevSchemaNow() {
    devSchemaInjecting.value = true;
    try {
      await injectDevSchema();
      notify(t("settings.developer.injected"), "success");
    } catch (e) {
      notify(String(e?.response?.data?.detail || e), "warning");
    } finally {
      devSchemaInjecting.value = false;
      await loadDevSchemaData();
    }
  }

  function openSetupWizardManual() {
    appStore.openSetupWizardManual();
  }

  async function updateAccountUsername() {
    await appStore.updateAccountUsername();
  }

  async function updateAccountPassword() {
    await appStore.updateAccountPassword();
  }

  async function deleteAccountNow() {
    await appStore.deleteAccountNow();
  }

  watch(() => config.value.INGEST_API_BASE, () => reloadIngestModels().catch(() => null));
  watch(() => config.value.INGEST_API_KEY, () => reloadIngestModels().catch(() => null));
  watch(() => config.value.LLM_API_BASE, () => reloadLlmModels().catch(() => null));
  watch(() => config.value.LLM_API_KEY, () => reloadLlmModels().catch(() => null));

  watch(() => config.value.SEARCH_TEXT_WEIGHT, () => normalizeSearchWeights("SEARCH_TEXT_WEIGHT", "SEARCH_VISUAL_WEIGHT", "SEARCH_TEXT_WEIGHT"));
  watch(() => config.value.SEARCH_VISUAL_WEIGHT, () => normalizeSearchWeights("SEARCH_TEXT_WEIGHT", "SEARCH_VISUAL_WEIGHT", "SEARCH_VISUAL_WEIGHT"));
  watch(() => config.value.SEARCH_MIXED_TEXT_WEIGHT, () => normalizeSearchWeights("SEARCH_MIXED_TEXT_WEIGHT", "SEARCH_MIXED_VISUAL_WEIGHT", "SEARCH_MIXED_TEXT_WEIGHT"));
  watch(() => config.value.SEARCH_MIXED_VISUAL_WEIGHT, () => normalizeSearchWeights("SEARCH_MIXED_TEXT_WEIGHT", "SEARCH_MIXED_VISUAL_WEIGHT", "SEARCH_MIXED_VISUAL_WEIGHT"));
  watch(() => config.value.SEARCH_WEIGHT_VISUAL, () => normalizeAgentChannelWeights("SEARCH_WEIGHT_VISUAL"));
  watch(() => config.value.SEARCH_WEIGHT_EH_VISUAL, () => normalizeAgentChannelWeights("SEARCH_WEIGHT_EH_VISUAL"));
  watch(() => config.value.SEARCH_WEIGHT_DESC, () => normalizeAgentChannelWeights("SEARCH_WEIGHT_DESC"));
  watch(() => config.value.SEARCH_WEIGHT_TEXT, () => normalizeAgentChannelWeights("SEARCH_WEIGHT_TEXT"));
  watch(() => config.value.SEARCH_WEIGHT_EH_TEXT, () => normalizeAgentChannelWeights("SEARCH_WEIGHT_EH_TEXT"));
  watch(() => config.value.SEARCH_WEIGHT_PLOT_VISUAL, () => normalizeAgentChannelWeights("SEARCH_WEIGHT_PLOT_VISUAL", ["SEARCH_WEIGHT_PLOT_VISUAL", "SEARCH_WEIGHT_PLOT_EH_VISUAL", "SEARCH_WEIGHT_PLOT_DESC", "SEARCH_WEIGHT_PLOT_TEXT", "SEARCH_WEIGHT_PLOT_EH_TEXT"]));
  watch(() => config.value.SEARCH_WEIGHT_PLOT_EH_VISUAL, () => normalizeAgentChannelWeights("SEARCH_WEIGHT_PLOT_EH_VISUAL", ["SEARCH_WEIGHT_PLOT_VISUAL", "SEARCH_WEIGHT_PLOT_EH_VISUAL", "SEARCH_WEIGHT_PLOT_DESC", "SEARCH_WEIGHT_PLOT_TEXT", "SEARCH_WEIGHT_PLOT_EH_TEXT"]));
  watch(() => config.value.SEARCH_WEIGHT_PLOT_DESC, () => normalizeAgentChannelWeights("SEARCH_WEIGHT_PLOT_DESC", ["SEARCH_WEIGHT_PLOT_VISUAL", "SEARCH_WEIGHT_PLOT_EH_VISUAL", "SEARCH_WEIGHT_PLOT_DESC", "SEARCH_WEIGHT_PLOT_TEXT", "SEARCH_WEIGHT_PLOT_EH_TEXT"]));
  watch(() => config.value.SEARCH_WEIGHT_PLOT_TEXT, () => normalizeAgentChannelWeights("SEARCH_WEIGHT_PLOT_TEXT", ["SEARCH_WEIGHT_PLOT_VISUAL", "SEARCH_WEIGHT_PLOT_EH_VISUAL", "SEARCH_WEIGHT_PLOT_DESC", "SEARCH_WEIGHT_PLOT_TEXT", "SEARCH_WEIGHT_PLOT_EH_TEXT"]));
  watch(() => config.value.SEARCH_WEIGHT_PLOT_EH_TEXT, () => normalizeAgentChannelWeights("SEARCH_WEIGHT_PLOT_EH_TEXT", ["SEARCH_WEIGHT_PLOT_VISUAL", "SEARCH_WEIGHT_PLOT_EH_VISUAL", "SEARCH_WEIGHT_PLOT_DESC", "SEARCH_WEIGHT_PLOT_TEXT", "SEARCH_WEIGHT_PLOT_EH_TEXT"]));
  watch(() => config.value.SEARCH_WEIGHT_MIXED_VISUAL, () => normalizeAgentChannelWeights("SEARCH_WEIGHT_MIXED_VISUAL", ["SEARCH_WEIGHT_MIXED_VISUAL", "SEARCH_WEIGHT_MIXED_EH_VISUAL", "SEARCH_WEIGHT_MIXED_DESC", "SEARCH_WEIGHT_MIXED_TEXT", "SEARCH_WEIGHT_MIXED_EH_TEXT"]));
  watch(() => config.value.SEARCH_WEIGHT_MIXED_EH_VISUAL, () => normalizeAgentChannelWeights("SEARCH_WEIGHT_MIXED_EH_VISUAL", ["SEARCH_WEIGHT_MIXED_VISUAL", "SEARCH_WEIGHT_MIXED_EH_VISUAL", "SEARCH_WEIGHT_MIXED_DESC", "SEARCH_WEIGHT_MIXED_TEXT", "SEARCH_WEIGHT_MIXED_EH_TEXT"]));
  watch(() => config.value.SEARCH_WEIGHT_MIXED_DESC, () => normalizeAgentChannelWeights("SEARCH_WEIGHT_MIXED_DESC", ["SEARCH_WEIGHT_MIXED_VISUAL", "SEARCH_WEIGHT_MIXED_EH_VISUAL", "SEARCH_WEIGHT_MIXED_DESC", "SEARCH_WEIGHT_MIXED_TEXT", "SEARCH_WEIGHT_MIXED_EH_TEXT"]));
  watch(() => config.value.SEARCH_WEIGHT_MIXED_TEXT, () => normalizeAgentChannelWeights("SEARCH_WEIGHT_MIXED_TEXT", ["SEARCH_WEIGHT_MIXED_VISUAL", "SEARCH_WEIGHT_MIXED_EH_VISUAL", "SEARCH_WEIGHT_MIXED_DESC", "SEARCH_WEIGHT_MIXED_TEXT", "SEARCH_WEIGHT_MIXED_EH_TEXT"]));
  watch(() => config.value.SEARCH_WEIGHT_MIXED_EH_TEXT, () => normalizeAgentChannelWeights("SEARCH_WEIGHT_MIXED_EH_TEXT", ["SEARCH_WEIGHT_MIXED_VISUAL", "SEARCH_WEIGHT_MIXED_EH_VISUAL", "SEARCH_WEIGHT_MIXED_DESC", "SEARCH_WEIGHT_MIXED_TEXT", "SEARCH_WEIGHT_MIXED_EH_TEXT"]));
  watch(() => config.value.REC_TAG_WEIGHT, () => normalizeRecommendWeights("REC_TAG_WEIGHT"));
  watch(() => config.value.REC_VISUAL_WEIGHT, () => normalizeRecommendWeights("REC_VISUAL_WEIGHT"));
  watch(() => config.value.REC_FEEDBACK_WEIGHT, () => normalizeRecommendWeights("REC_FEEDBACK_WEIGHT"));
  watch(() => config.value.REC_TEMPERATURE, () => {
    const v = Number(config.value.REC_TEMPERATURE ?? 0.3);
    config.value.REC_TEMPERATURE = Number((Number.isFinite(v) ? Math.max(0.05, Math.min(2.0, v)) : 0.3).toFixed(2));
  });
  watch(() => config.value.REC_PROFILE_WEIGHT, () => {
    const v = Number(config.value.REC_PROFILE_WEIGHT ?? 0.18);
    config.value.REC_PROFILE_WEIGHT = Number((Number.isFinite(v) ? Math.max(0, Math.min(1, v)) : 0.18).toFixed(4));
  });
  watch(() => config.value.REC_TOUCH_PENALTY_PCT, () => {
    const v = Number(config.value.REC_TOUCH_PENALTY_PCT ?? 35);
    config.value.REC_TOUCH_PENALTY_PCT = Number.isFinite(v) ? Math.max(0, Math.min(100, Math.round(v))) : 35;
  });
  watch(() => config.value.REC_IMPRESSION_PENALTY_PCT, () => {
    const v = Number(config.value.REC_IMPRESSION_PENALTY_PCT ?? 3);
    config.value.REC_IMPRESSION_PENALTY_PCT = Number.isFinite(v) ? Math.max(0, Math.min(100, Math.round(v))) : 3;
  });

  watch(() => config.value.DATA_UI_DEVELOPER_MODE, (enabled) => {
    if (!enabled && settingsTab.value === "developer") settingsTab.value = "other";
    loadDevSchemaData().catch(() => null);
  });

  watch(() => newEhTag.value, () => {
    loadEhTagSuggestions().catch(() => null);
  });

  return {
    config,
    schema,
    configMeta,
    secretState,
    settingsTab,
    llmModelOptions,
    ingestModelOptions,
    builtinSkills,
    userSkills,
    pluginFiles,
    pluginUploadRef,
    devSchemaUploadRef,
    devSchemaStatus,
    devSchemaInjecting,
    thumbCacheStats,
    translationStatus,
    translationUploadRef,
    modelStatus,
    siglipDownload,
    cookieParts,
    ehFilterTags,
    newEhTag,
    ehTagSuggestions,
    ehCategoryDefs,
    ehCategoryAllowMap,
    themeOptions,
    themeModeOptions,
    timezoneOptions,
    llmReady,
    limitedModeMessages,
    health,
    accountForm,
    init,
    t,
    notify,
    labelFor,
    secretHint,
    getGalleryTitle,
    parseCookie,
    buildCookie,
    parseCsv,
    toggleCategory,
    categoryStyle,
    addEhTag,
    removeEhTag,
    loadEhTagSuggestions,
    normalizeSearchWeights,
    normalizeAgentChannelWeights,
    normalizeRecommendWeights,
    resetSearchWeightPresets,
    resetRecommendPreset,
    loadConfigData,
    saveConfig,
    reloadIngestModels,
    reloadLlmModels,
    loadThumbCacheStats,
    clearThumbCacheAction,
    loadTranslationStatus,
    onTranslationUploadChange,
    loadModelStatus,
    pollSiglipTask,
    downloadSiglipAction,
    clearRuntimeDepsAction,
    clearSiglipAction,
    clearRecommendTouchesAction,
    clearRecommendProfileAction,
    loadSkillsData,
    onPluginUploadChange,
    loadDevSchemaData,
    onDevSchemaUploadChange,
    injectDevSchemaNow,
    openSetupWizardManual,
    updateAccountUsername,
    updateAccountPassword,
    deleteAccountNow,
  };
});
