import { computed } from "vue";

export function createDashboardHelpers(ctx) {
  const {
    config,
    homeFilters,
    ehCategoryMap,
    formatDateMinute,
    isMobile,
    rail,
  } = ctx;

  function formatEpoch(v) {
    const ep = Number(v || 0);
    if (!ep) return "-";
    return formatDateMinute(new Date(ep * 1000).toISOString());
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

  function searchResultLimit() {
    if (config.value.SEARCH_RESULT_INFINITE) return 300;
    const n = Number(config.value.SEARCH_RESULT_SIZE || 20);
    if (n === 50 || n === 100) return n;
    return 20;
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
  }

  function scrollToTop() {
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  const quickFabStyle = computed(() => {
    if (isMobile.value) return {};
    return { left: `${rail.value ? 92 : 292}px` };
  });

  return {
    itemSubtitle,
    itemPrimaryLink,
    categoryLabel,
    categoryBadgeStyle,
    itemHoverTags,
    searchResultLimit,
    isTagFilterActive,
    toggleTagFilter,
    scrollToTop,
    quickFabStyle,
  };
}
