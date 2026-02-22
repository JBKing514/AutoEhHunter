import { computed, ref } from "vue";

export function createDashboardState(options = {}) {
  const { tab = null } = options;
  const homeTab = ref("history");
  const homeViewMode = ref("wide");
  const homeSearchQuery = ref("");
  const imageSearchQuery = ref("");
  const homeSentinel = ref(null);
  const homeHistory = ref({ items: [], cursor: "", hasMore: true, loading: false, error: "" });
  const homeRecommend = ref({ items: [], cursor: "", hasMore: true, loading: false, error: "" });
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

  const activeHomeState = computed(() => {
    if (homeTab.value === "history") return homeHistory.value;
    if (homeTab.value === "recommend") return homeRecommend.value;
    return homeSearchState.value;
  });

  const lastWindowScrollY = ref(0);
  let touchPreviewTimer = null;

  function onCardTouchStart(item) {
    if (touchPreviewTimer) clearTimeout(touchPreviewTimer);
    touchPreviewTimer = setTimeout(() => {
      mobilePreviewItem.value = item || null;
    }, 1000);
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
    if (!isMobile.value) return;
    mobilePreviewItem.value = item || null;
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
    const isDashboard = tab ? tab.value === "dashboard" : true;
    showScrollQuickActions.value = isDashboard && (isMobile.value ? y > 220 : y > 120);
  }

  function runQuickSearch() {
    quickSearchOpen.value = false;
  }

  function quickImageSearch() {
    quickSearchOpen.value = false;
    imageSearchDialog.value = true;
  }

  function openQuickFilters() {
    quickSearchOpen.value = false;
    homeFiltersOpen.value = true;
  }

  function onMobileDetailLinkClick() {
    mobilePreviewItem.value = null;
  }

  return {
    homeTab,
    homeViewMode,
    homeSearchQuery,
    imageSearchQuery,
    homeSentinel,
    homeHistory,
    homeRecommend,
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
    activeHomeState,
    lastWindowScrollY,
    onCardTouchStart,
    onCardTouchEnd,
    onMobilePreviewToggle,
    onCoverClick,
    updateViewportFlags,
    onWindowScroll,
    runQuickSearch,
    quickImageSearch,
    openQuickFilters,
    onMobileDetailLinkClick,
    touchPreviewTimerRef: () => touchPreviewTimer,
    clearTouchPreviewTimer: () => {
      if (touchPreviewTimer) {
        clearTimeout(touchPreviewTimer);
        touchPreviewTimer = null;
      }
    },
  };
}
