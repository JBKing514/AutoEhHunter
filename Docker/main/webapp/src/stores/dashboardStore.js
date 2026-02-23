import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getHomeHistory, getHomeRecommend, getHomeTagSuggest, getRecommendItems, postRecommendDislike, postRecommendImpressions, postRecommendTouchKeepalive, searchByImage, searchByImageUpload, searchByText } from "../api";

export const useDashboardStore = defineStore("dashboard", () => {
  const homeTab = ref("recommend");
  const homeViewMode = ref("wide");
  const homeSearchQuery = ref("");
  const imageSearchQuery = ref("");
  const homeSentinel = ref(null);
  const homeHistory = ref({ items: [], cursor: "", hasMore: true, loading: false, error: "" });
  const homeRecommend = ref({ items: [], cursor: "", hasMore: true, loading: false, error: "" });
  const homeRecommendDepth = ref(1);
  const homeRecommendCanExpand = ref(true);
  const homeRecommendJitterNonce = ref(0);
  const homeSearchState = ref({ items: [], cursor: "", hasMore: false, loading: false, error: "" });
  const homeFiltersOpen = ref(false);
  const homeFilters = ref({ categories: [], tags: [] });
  const filterTagInput = ref("");
  const filterTagSuggestions = ref([]);
  const lastSearchContext = ref({ mode: "", query: "", hasImage: false });
  const imageSearchDialog = ref(false);
  const imageDropActive = ref(false);
  const selectedImageFile = ref(null);
  const imageFileInputRef = ref(null);
  const mobilePreviewItem = ref(null);
  const isMobile = ref(false);
  const quickSearchOpen = ref(false);
  const showScrollQuickActions = ref(false);
  const lastWindowScrollY = ref(0);

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
  const ehCategoryMap = Object.fromEntries(ehCategoryDefs.map((x) => [String(x.key).toLowerCase(), x]));
  if (!homeFilters.value.categories.length) {
    homeFilters.value.categories = ehCategoryDefs.map((x) => x.key);
  }

  let _getConfig = () => ({});
  let _configRef = null;
  let _getLang = () => "zh";
  let _getTab = () => "dashboard";
  let _getRail = () => false;
  let _t = (k) => k;
  let _notify = () => {};
  let _formatDateMinute = (v) => String(v || "-");

  let touchPreviewTimer = null;
  let touchDislikeTriggered = false;
  let homeObserver = null;
  let recommendExposureObserver = null;
  const recommendExposureQueue = new Map();
  const recommendObservedKeys = new Set();
  let recommendExposureTimer = null;
  const recommendTouchStamp = new Map();
  const dislikedVisualMap = ref({});

  const activeHomeState = computed(() => {
    if (homeTab.value === "history") return homeHistory.value;
    if (homeTab.value === "recommend") return homeRecommend.value;
    return homeSearchState.value;
  });

  const quickFabStyle = computed(() => {
    if (isMobile.value) return {};
    return { left: `${_getRail() ? 92 : 292}px` };
  });

  const filteredHomeItems = computed(() => {
    const src = activeHomeState.value?.items || [];
    const cats = (effectiveFilterCategories() || []).map((x) => String(x).toLowerCase());
    const tags = (homeFilters.value.tags || []).map((x) => String(x).toLowerCase()).filter(Boolean);
    if (!cats.length && !tags.length) return src;
    return src.filter((it) => {
      if (cats.length) {
        const c = String(it?.category || "").toLowerCase();
        if (!cats.includes(c)) return false;
      }
      if (tags.length) {
        const all = [
          ...((it?.tags || []).map((x) => String(x).toLowerCase())),
          ...((it?.tags_translated || []).map((x) => String(x).toLowerCase())),
        ].join(" ");
        for (const t of tags) {
          if (!all.includes(t)) return false;
        }
      }
      return true;
    });
  });

  function init(deps = {}) {
    if (deps.configRef) _configRef = deps.configRef;
    if (typeof deps.getConfig === "function") _getConfig = deps.getConfig;
    if (typeof deps.getLang === "function") _getLang = deps.getLang;
    if (typeof deps.getTab === "function") _getTab = deps.getTab;
    if (typeof deps.getRail === "function") _getRail = deps.getRail;
    if (typeof deps.t === "function") _t = deps.t;
    if (typeof deps.notify === "function") _notify = deps.notify;
    if (typeof deps.formatDateMinute === "function") _formatDateMinute = deps.formatDateMinute;
  }

  const config = computed({
    get() {
      if (_configRef && typeof _configRef === "object" && "value" in _configRef) {
        return _configRef.value || {};
      }
      return _getConfig();
    },
    set(v) {
      if (_configRef && typeof _configRef === "object" && "value" in _configRef) {
        _configRef.value = v || {};
      }
    },
  });

  function t(key, vars = {}) {
    return _t(key, vars);
  }

  function searchResultLimit() {
    const config = _getConfig();
    if (config.SEARCH_RESULT_INFINITE) return 300;
    const n = Number(config.SEARCH_RESULT_SIZE || 20);
    if (n === 50 || n === 100) return n;
    return 20;
  }

  function formatEpoch(v) {
    const ep = Number(v || 0);
    if (!ep) return "-";
    return _formatDateMinute(new Date(ep * 1000).toISOString());
  }

  function categoryLabel(item) {
    const raw = String(item?.category || "").trim().toLowerCase();
    if (raw && ehCategoryMap[raw]) return ehCategoryMap[raw].label;
    if (raw) return raw;
    return "";
  }

  function itemSubtitle(item) {
    const src = item?.source === "eh_works" ? "EH" : "LRR";
    const epoch = item?.meta?.read_time || item?.meta?.posted || item?.meta?.date_added;
    const cat = categoryLabel(item);
    return `${src} · ${formatEpoch(epoch)}${cat ? ` · ${cat}` : ""}`;
  }

  function itemPrimaryLink(item) {
    return item?.link_url || item?.eh_url || item?.ex_url || "#";
  }

  function categoryBadgeStyle(item) {
    const raw = String(item?.category || "").trim().toLowerCase();
    const c = ehCategoryMap[raw]?.color || "#475569";
    return { backgroundColor: c };
  }

  function itemHoverTags(item) {
    const tags = Array.isArray(item?.tags_translated) && item.tags_translated.length ? item.tags_translated : (item?.tags || []);
    return tags.map((x) => String(x || "").trim()).filter(Boolean);
  }

  function effectiveFilterCategories() {
    const all = ehCategoryDefs.map((x) => x.key);
    const selected = homeFilters.value.categories || [];
    if (selected.length === all.length) return [];
    if (selected.length === 0) return ["__none__"];
    return selected;
  }

  function isTagFilterActive(tag) {
    const t = String(tag || "").trim().toLowerCase();
    return (homeFilters.value.tags || []).map((x) => String(x || "").trim().toLowerCase()).includes(t);
  }

  function toggleTagFilter(tag) {
    const t = String(tag || "").trim();
    if (!t) return;
    const arr = [...(homeFilters.value.tags || [])];
    const i = arr.findIndex((x) => String(x).toLowerCase() === t.toLowerCase());
    if (i >= 0) arr.splice(i, 1);
    else arr.push(t);
    homeFilters.value.tags = arr;
    if (homeTab.value === "search") rerunSearchWithFilters().catch(() => null);
  }

  function scrollToTop() {
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  function onCardTouchStart(item) {
    if (homeTab.value !== "recommend" || String(item?.source || "") !== "eh_works") {
      touchDislikeTriggered = false;
      return;
    }
    if (touchPreviewTimer) clearTimeout(touchPreviewTimer);
    touchDislikeTriggered = false;
    touchPreviewTimer = setTimeout(() => {
      touchDislikeTriggered = true;
      markRecommendDislike(item, { removeDelayMs: 650 }).catch(() => null);
    }, 500);
  }

  function onCardTouchEnd() {
    if (touchPreviewTimer) {
      clearTimeout(touchPreviewTimer);
      touchPreviewTimer = null;
    }
  }

  function onMobilePreviewToggle(v) {
    if (!v) mobilePreviewItem.value = null;
  }

  function onCoverClick(item) {
    if (touchDislikeTriggered) {
      touchDislikeTriggered = false;
      return;
    }
    if (!isMobile.value) return;
    mobilePreviewItem.value = item || null;
  }

  function onMobileDetailLinkClick() {
    mobilePreviewItem.value = null;
  }

  function setDislikedVisual(item, on = true) {
    const key = recommendExposureKey(item);
    if (!key) return;
    dislikedVisualMap.value = {
      ...(dislikedVisualMap.value || {}),
      [key]: !!on,
    };
  }

  function isRecommendDisliked(item) {
    const key = recommendExposureKey(item);
    return !!(key && dislikedVisualMap.value && dislikedVisualMap.value[key]);
  }

  function recommendExposureKey(item) {
    const gid = Number(item?.gid || 0);
    const token = String(item?.token || "").trim().toLowerCase();
    if (!gid || !token) return "";
    return `${gid}:${token}`;
  }

  function flushRecommendImpressions() {
    if (!recommendExposureQueue.size) return;
    const items = Array.from(recommendExposureQueue.values());
    recommendExposureQueue.clear();
    postRecommendImpressions({ items, weight: 1.0 }).catch(() => null);
  }

  function queueRecommendImpression(item) {
    if (String(item?.source || "") !== "eh_works") return;
    const key = recommendExposureKey(item);
    if (!key || recommendExposureQueue.has(key)) return;
    recommendExposureQueue.set(key, {
      gid: Number(item?.gid || 0),
      token: String(item?.token || ""),
      eh_url: String(item?.eh_url || ""),
      ex_url: String(item?.ex_url || ""),
    });
    if (recommendExposureTimer) clearTimeout(recommendExposureTimer);
    recommendExposureTimer = setTimeout(() => {
      flushRecommendImpressions();
      recommendExposureTimer = null;
    }, 2000);
  }

  function ensureRecommendExposureObserver() {
    if (recommendExposureObserver || typeof IntersectionObserver === "undefined") return;
    recommendExposureObserver = new IntersectionObserver((entries) => {
      for (const entry of entries || []) {
        if (!entry?.isIntersecting) continue;
        const el = entry.target;
        const payload = el?.__aehRecommendItem;
        if (payload) queueRecommendImpression(payload);
        if (recommendExposureObserver) recommendExposureObserver.unobserve(el);
      }
    }, { root: null, rootMargin: "0px", threshold: 0.35 });
  }

  function setRecommendExposureRef(el, item) {
    if (!el || !item) return;
    if (homeTab.value !== "recommend") return;
    if (String(item?.source || "") !== "eh_works") return;
    const key = recommendExposureKey(item);
    if (!key || recommendObservedKeys.has(key)) return;
    recommendObservedKeys.add(key);
    ensureRecommendExposureObserver();
    el.__aehRecommendItem = item;
    recommendExposureObserver?.observe(el);
  }

  function resetRecommendExposureObserver() {
    if (recommendExposureObserver) {
      recommendExposureObserver.disconnect();
      recommendExposureObserver = null;
    }
    recommendObservedKeys.clear();
    if (recommendExposureTimer) {
      clearTimeout(recommendExposureTimer);
      recommendExposureTimer = null;
    }
    flushRecommendImpressions();
  }

  async function onRecommendItemOpen(item) {
    const src = String(item?.source || "").trim();
    if (src !== "eh_works") return;
    const gid = Number(item?.gid || 0);
    const token = String(item?.token || "").trim();
    if (!gid || !token) return;
    const dedupeKey = `${gid}:${token.toLowerCase()}`;
    const now = Date.now();
    const prev = Number(recommendTouchStamp.get(dedupeKey) || 0);
    if (now - prev < 1500) return;
    recommendTouchStamp.set(dedupeKey, now);
    postRecommendTouchKeepalive({
      gid,
      token,
      eh_url: String(item?.eh_url || ""),
      ex_url: String(item?.ex_url || ""),
      weight: 1.0,
    }).catch(() => null);
  }

  async function markRecommendDislike(item, options = {}) {
    if (String(item?.source || "") !== "eh_works") return;
    const gid = Number(item?.gid || 0);
    const token = String(item?.token || "").trim();
    if (!gid || !token) return;
    const removeDelayMs = Math.max(150, Math.min(1500, Number(options.removeDelayMs || 450)));
    setDislikedVisual(item, true);
    try {
      await postRecommendDislike({
        gid,
        token,
        eh_url: String(item?.eh_url || ""),
        ex_url: String(item?.ex_url || ""),
        weight: 1.0,
      });
      setTimeout(() => {
        homeRecommend.value.items = (homeRecommend.value.items || []).filter((x) => {
          return !(Number(x?.gid || 0) === gid && String(x?.token || "").trim().toLowerCase() === token.toLowerCase());
        });
        setDislikedVisual(item, false);
        if (mobilePreviewItem.value && Number(mobilePreviewItem.value?.gid || 0) === gid && String(mobilePreviewItem.value?.token || "").trim().toLowerCase() === token.toLowerCase()) {
          mobilePreviewItem.value = null;
        }
      }, removeDelayMs);
      _notify(_t("home.recommend.disliked"), "info");
    } catch (e) {
      setDislikedVisual(item, false);
      _notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  async function shuffleRecommendBatch() {
    if (homeTab.value !== "recommend") return;
    homeRecommendJitterNonce.value = Number(homeRecommendJitterNonce.value || 0) + 1;
    await resetHomeFeed();
  }

  async function tryExpandRecommendDepth() {
    if (homeTab.value !== "recommend") return false;
    if (!homeRecommendCanExpand.value) return false;
    const nextDepth = Number(homeRecommendDepth.value || 1) + 1;
    if (nextDepth > 8) {
      homeRecommendCanExpand.value = false;
      return false;
    }
    homeRecommendDepth.value = nextDepth;
    _notify(_t("home.recommend.expand_loading"), "info");
    await loadHomeFeed(true);
    return true;
  }

  function updateViewportFlags() {
    if (typeof window === "undefined") return;
    isMobile.value = window.innerWidth < 960;
  }

  function onWindowScroll() {
    if (typeof window === "undefined") return;
    const y = Math.max(
      Number(window.scrollY || 0),
      Number(document?.documentElement?.scrollTop || 0),
      Number(document?.body?.scrollTop || 0),
    );
    lastWindowScrollY.value = y;
    const isDashboard = _getTab() === "dashboard";
    showScrollQuickActions.value = isDashboard && (isMobile.value ? y > 220 : y > 120);
  }

  function runQuickSearch() {
    quickSearchOpen.value = false;
    runHomeSearchPlaceholder().catch(() => null);
  }

  function quickImageSearch() {
    quickSearchOpen.value = false;
    imageSearchDialog.value = true;
  }

  function openQuickFilters() {
    quickSearchOpen.value = false;
    homeFiltersOpen.value = true;
  }

  function toggleHomeFilterCategory(key) {
    const k = String(key || "");
    const set = new Set(homeFilters.value.categories || []);
    if (set.has(k)) set.delete(k);
    else set.add(k);
    homeFilters.value.categories = Array.from(set);
  }

  function selectAllHomeFilterCategories() {
    homeFilters.value.categories = ehCategoryDefs.map((x) => x.key);
  }

  function clearAllHomeFilterCategories() {
    homeFilters.value.categories = [];
  }

  function homeFilterCategoryStyle(key, color) {
    const on = (homeFilters.value.categories || []).includes(key);
    return {
      backgroundColor: on ? color : "#424242",
      color: "#ffffff",
      opacity: on ? 1 : 0.45,
    };
  }

  function clearHomeFilters() {
    homeFilters.value = { categories: ehCategoryDefs.map((x) => x.key), tags: [] };
    filterTagInput.value = "";
    filterTagSuggestions.value = [];
  }

  async function loadTagSuggestions() {
    const q = String(filterTagInput.value || "").trim();
    if (q.length < 2) {
      filterTagSuggestions.value = [];
      return;
    }
    try {
      const res = await getHomeTagSuggest({ q, limit: 10, ui_lang: _getLang() });
      filterTagSuggestions.value = res.items || [];
    } catch {
      filterTagSuggestions.value = [];
    }
  }

  async function rerunSearchWithFilters() {
    const config = _getConfig();
    const cats = effectiveFilterCategories();
    const tags = homeFilters.value.tags || [];
    const ctx0 = lastSearchContext.value || {};
    const fallbackQ = String(homeSearchQuery.value || "").trim();
    const q = String(ctx0.query || fallbackQ || "").trim();
    if (ctx0.mode === "text" && String(ctx0.query || "").trim()) {
      const res = await searchByText({ query: q, scope: "both", limit: searchResultLimit(), use_llm: !!config.SEARCH_NL_ENABLED, ui_lang: _getLang(), include_categories: cats, include_tags: tags });
      homeSearchState.value.items = res.items || [];
      lastSearchContext.value = { mode: "text", query: q, hasImage: false };
      return;
    }
    if ((ctx0.mode === "image" || selectedImageFile.value) && selectedImageFile.value) {
      const res = await searchByImageUpload(selectedImageFile.value, {
        scope: "both",
        limit: searchResultLimit(),
        query: q,
        ui_lang: _getLang(),
        text_weight: Number(config.SEARCH_MIXED_TEXT_WEIGHT ?? 0.5),
        visual_weight: Number(config.SEARCH_MIXED_VISUAL_WEIGHT ?? 0.5),
        include_categories: cats.join(","),
        include_tags: tags.join(","),
      });
      homeSearchState.value.items = res.items || [];
      lastSearchContext.value = { mode: "image", query: q, hasImage: true };
      return;
    }
    if (q) {
      const res = await searchByText({ query: q, scope: "both", limit: searchResultLimit(), use_llm: !!config.SEARCH_NL_ENABLED, ui_lang: _getLang(), include_categories: cats, include_tags: tags });
      homeSearchState.value.items = res.items || [];
      lastSearchContext.value = { mode: "text", query: q, hasImage: false };
    }
  }

  async function applyHomeFilters() {
    homeFiltersOpen.value = false;
    if (homeTab.value === "search") {
      await rerunSearchWithFilters();
    }
  }

  async function loadHomeFeed(reset = false) {
    const state = activeHomeState.value;
    if (homeTab.value === "search") return;
    if (state.loading) return;
    if (!state.hasMore && !reset) {
      if (homeTab.value === "recommend") {
        await tryExpandRecommendDepth();
      }
      return;
    }
    state.loading = true;
    state.error = "";
    try {
      const params = { limit: 24 };
      if (!reset && state.cursor) params.cursor = state.cursor;
      if (homeTab.value === "recommend") {
        params.depth = Number(homeRecommendDepth.value || 1);
        params.jitter = Number(homeRecommendJitterNonce.value || 0) > 0;
        params.jitter_nonce = String(homeRecommendJitterNonce.value || 0);
      }
      const res = homeTab.value === "history"
        ? await getHomeHistory(params)
        : (Number(homeRecommendDepth.value || 1) > 1 ? await getRecommendItems(params) : await getHomeRecommend(params));
      const rows = res.items || [];
      state.items = reset ? rows : [...state.items, ...rows];
      state.cursor = res.next_cursor || "";
      state.hasMore = !!res.has_more;
      if (homeTab.value === "recommend") {
        const meta = res.meta || {};
        homeRecommendCanExpand.value = !!meta.can_expand_more;
      }
    } catch (e) {
      state.error = String(e?.response?.data?.detail || e);
    } finally {
      state.loading = false;
    }
  }

  async function resetHomeFeed() {
    const target = activeHomeState.value;
    if (homeTab.value === "recommend") {
      homeRecommendDepth.value = 1;
      homeRecommendCanExpand.value = true;
      resetRecommendExposureObserver();
      dislikedVisualMap.value = {};
    }
    target.items = [];
    target.cursor = "";
    target.hasMore = homeTab.value !== "search";
    if (homeTab.value !== "search") {
      await loadHomeFeed(true);
    }
  }

  async function runHomeSearchPlaceholder() {
    const config = _getConfig();
    const q = String(homeSearchQuery.value || "").trim();
    if (!q) {
      _notify(_t("home.search.placeholder"), "info");
      return;
    }
    try {
      const res = await searchByText({
        query: q,
        scope: "both",
        limit: searchResultLimit(),
        use_llm: !!config.SEARCH_NL_ENABLED,
        ui_lang: _getLang(),
        include_categories: effectiveFilterCategories(),
        include_tags: homeFilters.value.tags || [],
      });
      homeSearchState.value.items = res.items || [];
      homeSearchState.value.cursor = "";
      homeSearchState.value.hasMore = false;
      homeTab.value = "search";
      lastSearchContext.value = { mode: "text", query: q, hasImage: false };
      _notify(_t("home.search.done"), "success");
    } catch (e) {
      _notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  async function runImageSearchQuick() {
    try {
      if (!homeHistory.value.items.length) {
        await (homeTab.value === "history" ? loadHomeFeed(false) : getHomeHistory({ limit: 12 }).then((res) => {
          homeHistory.value.items = res.items || [];
          homeHistory.value.cursor = res.next_cursor || "";
          homeHistory.value.hasMore = !!res.has_more;
        }));
      }
      const refItem = (homeHistory.value.items || []).find((x) => x.source === "works" && x.arcid);
      if (!refItem?.arcid) {
        _notify(_t("home.search.camera_placeholder"), "info");
        return;
      }
      const res = await searchByImage({ arcid: refItem.arcid, scope: "both", limit: searchResultLimit() });
      homeRecommend.value.items = res.items || [];
      homeRecommend.value.cursor = "";
      homeRecommend.value.hasMore = false;
      homeTab.value = "recommend";
      _notify(_t("home.search.image_ready"), "success");
    } catch (e) {
      _notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  function triggerImagePicker() {
    if (imageFileInputRef.value) imageFileInputRef.value.click();
  }

  function onImagePickChange(event) {
    const file = event?.target?.files?.[0];
    selectedImageFile.value = file || null;
  }

  async function onImageDrop(event) {
    imageDropActive.value = false;
    const file = event?.dataTransfer?.files?.[0];
    if (!file) return;
    if (!String(file.type || "").startsWith("image/")) {
      _notify(_t("home.image_upload.only_image"), "warning");
      return;
    }
    selectedImageFile.value = file;
    if (homeTab.value === "search") {
      await runImageUploadSearch();
    }
  }

  async function runImageUploadSearch() {
    if (!selectedImageFile.value) return;
    const config = _getConfig();
    try {
      const res = await searchByImageUpload(selectedImageFile.value, {
        scope: "both",
        limit: searchResultLimit(),
        ui_lang: _getLang(),
        query: String(imageSearchQuery.value || "").trim(),
        text_weight: Number(config.SEARCH_MIXED_TEXT_WEIGHT ?? 0.5),
        visual_weight: Number(config.SEARCH_MIXED_VISUAL_WEIGHT ?? 0.5),
        include_categories: effectiveFilterCategories().join(","),
        include_tags: (homeFilters.value.tags || []).join(","),
      });
      homeSearchState.value.items = res.items || [];
      homeSearchState.value.cursor = "";
      homeSearchState.value.hasMore = false;
      homeTab.value = "search";
      lastSearchContext.value = { mode: "image", query: String(imageSearchQuery.value || "").trim(), hasImage: true };
      imageSearchDialog.value = false;
      _notify(_t("home.search.image_uploaded_ready"), "success");
    } catch (e) {
      _notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  function bindHomeInfiniteScroll() {
    clearHomeObserver();
    if (!homeSentinel.value || typeof IntersectionObserver === "undefined") return;
    homeObserver = new IntersectionObserver((entries) => {
      const first = entries[0];
      if (!first?.isIntersecting) return;
      loadHomeFeed(false).catch(() => null);
    }, { root: null, rootMargin: "600px 0px", threshold: 0.01 });
    homeObserver.observe(homeSentinel.value);
  }

  function clearHomeObserver() {
    if (homeObserver) {
      homeObserver.disconnect();
      homeObserver = null;
    }
  }

  function clearTouchPreviewTimer() {
    if (touchPreviewTimer) {
      clearTimeout(touchPreviewTimer);
      touchPreviewTimer = null;
    }
  }

  return {
    config,
    homeTab,
    homeViewMode,
    homeSearchQuery,
    imageSearchQuery,
    homeSentinel,
    homeHistory,
    homeRecommend,
    homeRecommendDepth,
    homeRecommendCanExpand,
    homeRecommendJitterNonce,
    homeSearchState,
    homeFiltersOpen,
    homeFilters,
    filterTagInput,
    filterTagSuggestions,
    lastSearchContext,
    imageSearchDialog,
    imageDropActive,
    selectedImageFile,
    imageFileInputRef,
    mobilePreviewItem,
    isMobile,
    quickSearchOpen,
    showScrollQuickActions,
    lastWindowScrollY,
    ehCategoryDefs,
    activeHomeState,
    filteredHomeItems,
    quickFabStyle,
    t,
    init,
    searchResultLimit,
    itemSubtitle,
    itemPrimaryLink,
    categoryLabel,
    categoryBadgeStyle,
    itemHoverTags,
    effectiveFilterCategories,
    isTagFilterActive,
    toggleTagFilter,
    scrollToTop,
    onCardTouchStart,
    onCardTouchEnd,
    onMobilePreviewToggle,
    onCoverClick,
    onMobileDetailLinkClick,
    onRecommendItemOpen,
    markRecommendDislike,
    isRecommendDisliked,
    setRecommendExposureRef,
    resetRecommendExposureObserver,
    tryExpandRecommendDepth,
    shuffleRecommendBatch,
    updateViewportFlags,
    onWindowScroll,
    runQuickSearch,
    quickImageSearch,
    openQuickFilters,
    toggleHomeFilterCategory,
    selectAllHomeFilterCategories,
    clearAllHomeFilterCategories,
    homeFilterCategoryStyle,
    clearHomeFilters,
    loadTagSuggestions,
    rerunSearchWithFilters,
    applyHomeFilters,
    loadHomeFeed,
    resetHomeFeed,
    runHomeSearchPlaceholder,
    runImageSearchQuick,
    triggerImagePicker,
    onImagePickChange,
    onImageDrop,
    runImageUploadSearch,
    bindHomeInfiniteScroll,
    clearHomeObserver,
    clearTouchPreviewTimer,
  };
});
