export function createDashboardActions(ctx) {
  const {
    homeTab,
    homeSearchQuery,
    homeHistory,
    homeRecommend,
    homeSearchState,
    homeFiltersOpen,
    homeFilters,
    filterTagInput,
    filterTagSuggestions,
    lastSearchContext,
    imageSearchQuery,
    imageSearchDialog,
    imageDropActive,
    selectedImageFile,
    imageFileInputRef,
    ehCategoryDefs,
    config,
    lang,
    activeHomeState,
    notify,
    t,
    searchResultLimit,
    getHomeTagSuggest,
    searchByText,
    searchByImage,
    searchByImageUpload,
    getHomeHistory,
    getHomeRecommend,
  } = ctx;

  function effectiveFilterCategories() {
    const all = ehCategoryDefs.map((x) => x.key);
    const selected = homeFilters.value.categories || [];
    if (selected.length === all.length) return [];
    if (selected.length === 0) return ["__none__"];
    return selected;
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
      const res = await getHomeTagSuggest({ q, limit: 10, ui_lang: lang.value });
      filterTagSuggestions.value = res.items || [];
    } catch {
      filterTagSuggestions.value = [];
    }
  }

  async function rerunSearchWithFilters() {
    const cats = effectiveFilterCategories();
    const tags = homeFilters.value.tags || [];
    const ctx0 = lastSearchContext.value || {};
    const fallbackQ = String(homeSearchQuery.value || "").trim();
    const q = String(ctx0.query || fallbackQ || "").trim();
    if (ctx0.mode === "text" && String(ctx0.query || "").trim()) {
      const res = await searchByText({ query: q, scope: "both", limit: searchResultLimit(), use_llm: !!config.value.SEARCH_NL_ENABLED, ui_lang: lang.value, include_categories: cats, include_tags: tags });
      homeSearchState.value.items = res.items || [];
      lastSearchContext.value = { mode: "text", query: q, hasImage: false };
      return;
    }
    if ((ctx0.mode === "image" || selectedImageFile.value) && selectedImageFile.value) {
      const res = await searchByImageUpload(selectedImageFile.value, {
        scope: "both",
        limit: searchResultLimit(),
        query: q,
        ui_lang: lang.value,
        text_weight: Number(config.value.SEARCH_MIXED_TEXT_WEIGHT ?? 0.5),
        visual_weight: Number(config.value.SEARCH_MIXED_VISUAL_WEIGHT ?? 0.5),
        include_categories: cats.join(","),
        include_tags: tags.join(","),
      });
      homeSearchState.value.items = res.items || [];
      lastSearchContext.value = { mode: "image", query: q, hasImage: true };
      return;
    }
    if (q) {
      const res = await searchByText({ query: q, scope: "both", limit: searchResultLimit(), use_llm: !!config.value.SEARCH_NL_ENABLED, ui_lang: lang.value, include_categories: cats, include_tags: tags });
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
    if (!state.hasMore && !reset) return;
    state.loading = true;
    state.error = "";
    try {
      const params = { limit: 24 };
      if (!reset && state.cursor) params.cursor = state.cursor;
      const res = homeTab.value === "history" ? await getHomeHistory(params) : await getHomeRecommend(params);
      const rows = res.items || [];
      state.items = reset ? rows : [...state.items, ...rows];
      state.cursor = res.next_cursor || "";
      state.hasMore = !!res.has_more;
    } catch (e) {
      state.error = String(e?.response?.data?.detail || e);
    } finally {
      state.loading = false;
    }
  }

  async function resetHomeFeed() {
    const target = activeHomeState.value;
    target.items = [];
    target.cursor = "";
    target.hasMore = homeTab.value !== "search";
    if (homeTab.value !== "search") {
      await loadHomeFeed(true);
    }
  }

  async function runHomeSearchPlaceholder() {
    const q = String(homeSearchQuery.value || "").trim();
    if (!q) {
      notify(t("home.search.placeholder"), "info");
      return;
    }
    try {
      const res = await searchByText({
        query: q,
        scope: "both",
        limit: searchResultLimit(),
        use_llm: !!config.value.SEARCH_NL_ENABLED,
        ui_lang: lang.value,
        include_categories: effectiveFilterCategories(),
        include_tags: homeFilters.value.tags || [],
      });
      homeSearchState.value.items = res.items || [];
      homeSearchState.value.cursor = "";
      homeSearchState.value.hasMore = false;
      homeTab.value = "search";
      lastSearchContext.value = { mode: "text", query: q, hasImage: false };
      notify(t("home.search.done"), "success");
    } catch (e) {
      notify(String(e?.response?.data?.detail || e), "warning");
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
        notify(t("home.search.camera_placeholder"), "info");
        return;
      }
      const res = await searchByImage({ arcid: refItem.arcid, scope: "both", limit: searchResultLimit() });
      homeRecommend.value.items = res.items || [];
      homeRecommend.value.cursor = "";
      homeRecommend.value.hasMore = false;
      homeTab.value = "recommend";
      notify(t("home.search.image_ready"), "success");
    } catch (e) {
      notify(String(e?.response?.data?.detail || e), "warning");
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
      notify(t("home.image_upload.only_image"), "warning");
      return;
    }
    selectedImageFile.value = file;
    if (homeTab.value === "search") {
      await runImageUploadSearch();
    }
  }

  async function runImageUploadSearch() {
    if (!selectedImageFile.value) return;
    try {
      const res = await searchByImageUpload(selectedImageFile.value, {
        scope: "both",
        limit: searchResultLimit(),
        ui_lang: lang.value,
        query: String(imageSearchQuery.value || "").trim(),
        text_weight: Number(config.value.SEARCH_MIXED_TEXT_WEIGHT ?? 0.5),
        visual_weight: Number(config.value.SEARCH_MIXED_VISUAL_WEIGHT ?? 0.5),
        include_categories: effectiveFilterCategories().join(","),
        include_tags: (homeFilters.value.tags || []).join(","),
      });
      homeSearchState.value.items = res.items || [];
      homeSearchState.value.cursor = "";
      homeSearchState.value.hasMore = false;
      homeTab.value = "search";
      lastSearchContext.value = { mode: "image", query: String(imageSearchQuery.value || "").trim(), hasImage: true };
      imageSearchDialog.value = false;
      notify(t("home.search.image_uploaded_ready"), "success");
    } catch (e) {
      notify(String(e?.response?.data?.detail || e), "warning");
    }
  }

  return {
    toggleHomeFilterCategory,
    selectAllHomeFilterCategories,
    clearAllHomeFilterCategories,
    homeFilterCategoryStyle,
    effectiveFilterCategories,
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
  };
}
