<template>
          <v-card class="pa-4 mb-4">
            <div class="mb-3">
              <div class="d-flex align-center ga-2">
              <v-text-field
                v-model="homeSearchQuery"
                class="home-search-input flex-grow-1"
                density="compact"
                hide-details
                :label="t('home.search.placeholder')"
                variant="outlined"
                color="primary"
                rounded="lg"
                @keyup.enter="runHomeSearchPlaceholder"
              >
                <template #prepend-inner>
                  <v-icon 
                    class="mr-2 cursor-pointer" 
                    :color="imageSearchDialog ? 'primary' : 'medium-emphasis'" 
                    @click="imageSearchDialog = true" 
                    title="Image Search"
                  >mdi-camera-outline</v-icon>
                  <v-icon 
                    class="cursor-pointer" 
                    :color="config.SEARCH_NL_ENABLED ? 'primary' : 'medium-emphasis'" 
                    @click="config.SEARCH_NL_ENABLED = !config.SEARCH_NL_ENABLED" 
                    title="AI Semantic Search"
                  >mdi-robot-outline</v-icon>
                </template>
                
                <template #append-inner>
                  <v-divider vertical class="mx-2" />
                  <v-icon 
                    color="primary" 
                    class="cursor-pointer" 
                    @click="runHomeSearchPlaceholder"
                  >mdi-magnify</v-icon>
                </template>
              </v-text-field>

                <template v-if="!isMobile">
                  <v-btn v-if="homeTab === 'recommend'" color="secondary" variant="tonal" icon="mdi-shuffle-variant" rounded="lg" @click="shuffleRecommendBatch" />
                  <v-btn v-if="homeTab === 'local'" color="secondary" variant="tonal" icon="mdi-sort" rounded="lg" @click="openLocalSortDialog" />
                  <v-btn color="primary" variant="tonal" icon="mdi-filter-variant" rounded="lg" @click="homeFiltersOpen = true" />
                </template>
              </div>

              <div v-if="isMobile" class="d-flex ga-2 mt-2">
                <v-btn
                  v-if="homeTab === 'recommend'"
                  class="flex-grow-1"
                  color="secondary"
                  variant="tonal"
                  prepend-icon="mdi-shuffle-variant"
                  rounded="lg"
                  @click="shuffleRecommendBatch"
                >
                  {{ t('home.recommend.shuffle') }}
                </v-btn>
                <v-btn
                  v-if="homeTab === 'local'"
                  class="flex-grow-1"
                  color="secondary"
                  variant="tonal"
                  prepend-icon="mdi-sort"
                  rounded="lg"
                  @click="openLocalSortDialog"
                >
                  {{ t('home.local.sort.open') }}
                </v-btn>
                <v-btn
                  :class="homeTab === 'recommend' || homeTab === 'local' ? 'flex-grow-1' : 'w-100'"
                  color="primary"
                  variant="tonal"
                  prepend-icon="mdi-filter-variant"
                  rounded="lg"
                  @click="homeFiltersOpen = true"
                >
                  {{ t('home.filter.title') }}
                </v-btn>
              </div>
            </div>

            <div class="d-flex align-center justify-space-between flex-wrap ga-2 home-tab-row" :class="{ 'home-tab-row-mobile': isMobile }">
              <v-tabs v-model="homeTab" density="compact" color="primary">
                <v-tab value="recommend" class="font-weight-bold">{{ t('home.tab.recommend') }}</v-tab>
                <v-tab value="local" class="font-weight-bold">{{ t('home.tab.local') }}</v-tab>
                <v-tab value="history" class="font-weight-bold">{{ t('home.tab.history') }}</v-tab>
                <v-tab value="search" class="font-weight-bold">{{ t('home.tab.search') }}</v-tab>
              </v-tabs>

              <v-btn-toggle 
                v-model="homeViewMode" 
                mandatory 
                variant="outlined" 
                divided 
                density="compact" 
                rounded="lg" 
                color="primary"
                class="home-view-toggle flex-shrink-0 bg-surface"
              >
                <v-btn value="wide" :title="t('home.view.wide')">
                  <v-icon>mdi-view-grid-outline</v-icon>
                </v-btn>
                <v-btn value="compact" :title="t('home.view.compact')">
                  <v-icon>mdi-view-module-outline</v-icon>
                </v-btn>
                <v-btn value="list" :title="t('home.view.list')">
                  <v-icon>mdi-view-list-outline</v-icon>
                </v-btn>
              </v-btn-toggle>
            </div>
            
            <div v-if="homeTab === 'recommend'" class="text-caption text-medium-emphasis mt-2">
              <div class="d-flex align-center justify-space-between flex-wrap ga-2">
                <span>{{ t('home.recommend.longpress_dislike') }}</span>
                <v-switch
                  v-model="config.REC_SHOW_PAGE_COUNT"
                  density="compact"
                  inset
                  hide-details
                  color="primary"
                  :label="t('home.recommend.show_page_count')"
                />
              </div>
            </div>
          </v-card>

          <v-alert v-if="activeHomeState.error" type="warning" class="mb-3">{{ activeHomeState.error }}</v-alert>

          <v-card v-if="homeTab === 'search'" class="pa-3 mb-3" variant="flat">
            <input ref="imageFileInputRef" type="file" accept="image/*" class="d-none" @change="onImagePickChange" />
            <div
              class="upload-dropzone"
              :class="{ active: imageDropActive }"
              @dragover.prevent="imageDropActive = true"
              @dragleave.prevent="imageDropActive = false"
              @drop.prevent="onImageDrop"
              @click="triggerImagePicker"
            >
              <div class="text-body-2">{{ selectedImageFile ? selectedImageFile.name : t('home.image_upload.hint') }}</div>
              <div class="text-caption text-medium-emphasis">{{ t('home.image_upload.subhint') }}</div>
            </div>
            <v-text-field
              v-model="imageSearchQuery"
              class="mt-2"
              density="compact"
              variant="outlined"
              :label="t('home.search.extra_text')"
              :hint="t('home.search.extra_text_hint')"
              persistent-hint
              @keyup.enter="runImageUploadSearch"
            />
            <div class="d-flex justify-end mt-2">
              <v-btn color="primary" :disabled="!selectedImageFile" @click="runImageUploadSearch">{{ t('home.image_upload.search') }}</v-btn>
            </div>
          </v-card>

          <v-list v-if="homeViewMode === 'list'" class="mb-2" lines="two">
            <v-list-item v-for="item in filteredHomeItems" :key="item.id" :subtitle="itemSubtitle(item)" @click="openDetailCard(item)">
              <template #title>
                <a :href="itemPrimaryLink(item)" :ref="(el) => setRecommendExposureRef(el, item)" target="_blank" rel="noopener noreferrer" class="cover-link-title" @mousedown.stop="onRecommendItemOpen(item)" @click.stop="onRecommendItemOpen(item)">{{ getGalleryTitle(item) }}</a>
              </template>
              <template #prepend>
                <div class="list-cover" @contextmenu.prevent>
                  <div v-if="item.thumb_url" class="cover-bg-blur list-blur" :style="{ backgroundImage: `url(${item.thumb_url})` }" />
                  <img v-if="item.thumb_url" :src="item.thumb_url" alt="cover" class="cover-img list-cover-img" loading="lazy" draggable="false" @dragstart.prevent @error="onImageError(item)" />
                  <v-icon v-else size="18">mdi-image-outline</v-icon>
                </div>
              </template>
              <template #append>
                <v-btn
                  v-if="item.source === 'works' && item.arcid && !config.READER_HIDE_START_BUTTON"
                  icon="mdi-play"
                  size="small"
                  variant="tonal"
                  @click.stop="startReader(item)"
                />
              </template>
            </v-list-item>
          </v-list>

          <v-row v-else>
            <v-col
              v-for="item in filteredHomeItems"
              :key="item.id"
              cols="12"
              :sm="homeViewMode === 'wide' ? 6 : 4"
              :md="homeViewMode === 'wide' ? 4 : 3"
              :lg="homeViewMode === 'wide' ? 3 : 2"
            >
              <v-menu :open-on-hover="!isMobile" :open-on-click="!isMobile" location="end" :open-delay="1000" :close-delay="180" max-width="480">
                <template #activator="{ props }">
                  <v-card
                    v-bind="props"
                    class="home-card"
                    :class="{ compact: homeViewMode === 'compact' }"
                    variant="flat"
                    @touchstart.passive="onCardTouchStart(item)"
                    @touchmove.passive="onCardTouchEnd"
                    @touchend.passive="onCardTouchEnd"
                    @touchcancel.passive="onCardTouchEnd"
                    @contextmenu.prevent
                    @click="onCoverClick(item)"
                  >
                    <div class="cover-anchor">
                      <div class="cover-ph" :class="{ disliked: isRecommendDisliked(item) }">
                        <div v-if="item.thumb_url" class="cover-bg-blur" :style="{ backgroundImage: `url(${item.thumb_url})` }" />
                        <img v-if="item.thumb_url" :src="item.thumb_url" alt="cover" class="cover-img" loading="lazy" draggable="false" @dragstart.prevent @error="onImageError(item)" />
                        <v-icon v-else size="30">mdi-image-outline</v-icon>
                        <div class="cover-guard" @contextmenu.prevent />
                        <div v-if="isRecommendDisliked(item)" class="dislike-mask"><v-icon size="40">mdi-thumb-down</v-icon></div>
                         <div v-if="categoryLabel(item)" class="cat-badge" :style="categoryBadgeStyle(item)">{{ categoryLabel(item) }}</div>
                       </div>
                      <div v-if="homeViewMode === 'compact'" class="cover-title-overlay">{{ getGalleryTitle(item) }}</div>
                    </div>
                    <div v-if="homeViewMode !== 'compact'" class="pa-2">
                      <a :href="itemPrimaryLink(item)" :ref="(el) => setRecommendExposureRef(el, item)" target="_blank" rel="noopener noreferrer" class="text-body-2 font-weight-medium text-truncate cover-link-title d-block" @mousedown="onRecommendItemOpen(item)" @click="onRecommendItemOpen(item)">{{ getGalleryTitle(item) }}</a>
                      <div class="text-caption text-medium-emphasis text-truncate">{{ itemSubtitle(item) }}</div>
                    </div>
                  </v-card>
                </template>
                <v-card class="pa-2 hover-preview-card" variant="flat">
                  <div class="hover-cover-wrap mb-2" @contextmenu.prevent>
                    <img v-if="item.thumb_url" :src="item.thumb_url" alt="cover" class="hover-cover" draggable="false" @dragstart.prevent @error="onImageError(item)" />
                    <div v-else class="hover-cover hover-fallback"><v-icon size="42">mdi-image-outline</v-icon></div>
                    <div
                      v-if="item.source === 'works' && item.arcid && !config.READER_HIDE_START_BUTTON"
                      class="reader-start-overlay"
                    >
                      <v-btn
                        icon="mdi-play"
                        color="grey-lighten-1"
                        variant="flat"
                        class="reader-start-play"
                        @click.stop="startReader(item)"
                      />
                    </div>
                    <div class="hover-dislike-banner">
                      <v-btn size="small" color="warning" variant="flat" prepend-icon="mdi-thumb-down-outline" @click.stop="markRecommendDislike(item)">{{ t('home.recommend.dislike_action') }}</v-btn>
                    </div>
                  </div>
                  <a :href="itemPrimaryLink(item)" :ref="(el) => setRecommendExposureRef(el, item)" target="_blank" rel="noopener noreferrer" class="text-body-2 font-weight-medium mb-1 cover-link-title d-inline-block" @mousedown="onRecommendItemOpen(item)" @click="onRecommendItemOpen(item)">{{ getGalleryTitle(item) }}</a>
                  <div v-if="categoryLabel(item)" class="text-caption text-medium-emphasis mb-1">{{ categoryLabel(item) }}</div>
                  <div class="d-flex flex-wrap ga-1">
                    <v-chip
                      v-for="tag in itemHoverTags(item)"
                      :key="`${item.id}-${tag}`"
                      size="x-small"
                      variant="outlined"
                      class="hover-tag"
                      :class="{ active: isTagFilterActive(tag) }"
                      @click.stop="toggleTagFilter(tag)"
                    >{{ tag }}</v-chip>
                  </div>
                </v-card>
              </v-menu>
            </v-col>
          </v-row>

          <div ref="homeSentinel" class="home-sentinel" />
          <div v-if="activeHomeState.loading" class="text-center py-3"><v-progress-circular indeterminate color="primary" size="24" /></div>
          <div v-else-if="!filteredHomeItems.length" class="text-center text-medium-emphasis py-8">{{ t('home.empty') }}</div>

          <v-dialog :model-value="!!mobilePreviewItem" max-width="560" content-class="mobile-preview-dialog" @update:model-value="onMobilePreviewToggle">
            <v-card v-if="mobilePreviewItem" class="pa-2 hover-preview-card" variant="flat">
              <div class="d-flex justify-space-between mb-1">
                <v-btn size="x-small" icon="mdi-close-circle" color="error" variant="tonal" @click="mobilePreviewItem = null" />
              </div>
              <div class="hover-cover-wrap mb-2" @contextmenu.prevent>
                <img v-if="mobilePreviewItem.thumb_url" :src="mobilePreviewItem.thumb_url" alt="cover" class="hover-cover" draggable="false" @dragstart.prevent @error="onImageError(mobilePreviewItem)" />
                <div v-else class="hover-cover hover-fallback"><v-icon size="42">mdi-image-outline</v-icon></div>
                <div
                  v-if="mobilePreviewItem.source === 'works' && mobilePreviewItem.arcid && !config.READER_HIDE_START_BUTTON"
                  class="reader-start-overlay"
                >
                  <v-btn
                    icon="mdi-play"
                    color="grey-lighten-1"
                    variant="flat"
                    class="reader-start-play"
                    @click.stop="startReader(mobilePreviewItem)"
                  />
                </div>
                <div class="hover-dislike-banner">
                  <v-btn size="small" color="warning" variant="flat" prepend-icon="mdi-thumb-down-outline" @click="markRecommendDislike(mobilePreviewItem)">{{ t('home.recommend.dislike_action') }}</v-btn>
                </div>
              </div>
              <a :href="itemPrimaryLink(mobilePreviewItem)" class="text-body-2 font-weight-medium mb-1 cover-link-title d-inline-block" target="_blank" rel="noopener noreferrer" @click="onMobileDetailLinkClick(); onRecommendItemOpen(mobilePreviewItem)">{{ getGalleryTitle(mobilePreviewItem) }}</a>
              <div v-if="categoryLabel(mobilePreviewItem)" class="text-caption text-medium-emphasis mb-1">{{ categoryLabel(mobilePreviewItem) }}</div>
              <div class="d-flex flex-wrap ga-1">
                <v-chip v-for="tag in itemHoverTags(mobilePreviewItem)" :key="`m-${mobilePreviewItem.id}-${tag}`" size="x-small" variant="outlined" class="hover-tag" :class="{ active: isTagFilterActive(tag) }" @click="toggleTagFilter(tag)">{{ tag }}</v-chip>
              </div>
            </v-card>
          </v-dialog>

          <v-dialog v-model="imageSearchDialog" max-width="560">
            <v-card class="pa-4" variant="flat">
              <div class="text-subtitle-1 font-weight-medium mb-2">{{ t('home.image_upload.title') }}</div>
              <div
                class="upload-dropzone"
                :class="{ active: imageDropActive }"
                @dragover.prevent="imageDropActive = true"
                @dragleave.prevent="imageDropActive = false"
                @drop.prevent="onImageDrop"
                @click="triggerImagePicker"
              >
                <div class="text-body-2">{{ selectedImageFile ? selectedImageFile.name : t('home.image_upload.hint') }}</div>
                <div class="text-caption text-medium-emphasis">{{ t('home.image_upload.subhint') }}</div>
              </div>
              <input ref="imageFileInputRef" type="file" accept="image/*" class="d-none" @change="onImagePickChange" />
              <v-text-field
                v-model="imageSearchQuery"
                class="mt-3"
                density="compact"
                variant="outlined"
                :label="t('home.search.extra_text')"
                :hint="t('home.search.extra_text_hint')"
                persistent-hint
                @keyup.enter="runImageUploadSearch"
              />
              <div class="d-flex ga-2 mt-3 justify-end">
                <v-btn variant="text" @click="imageSearchDialog = false">{{ t('home.image_upload.cancel') }}</v-btn>
                <v-btn color="primary" :disabled="!selectedImageFile" @click="runImageUploadSearch">{{ t('home.image_upload.search') }}</v-btn>
              </div>
            </v-card>
          </v-dialog>

          <v-dialog v-model="homeFiltersOpen" max-width="680">
            <v-card class="pa-4" variant="flat">
              <div class="text-subtitle-1 font-weight-medium mb-2">{{ t('home.filter.title') }}</div>
              <div class="text-caption text-medium-emphasis mb-3">{{ t('home.filter.hint') }}</div>
              
              <div class="d-flex align-center justify-space-between mb-2">
                <div class="text-body-2">{{ t('home.filter.categories') }}</div>
                <div class="d-flex ga-2">
                  <v-btn size="small" variant="text" color="primary" @click="selectAllHomeFilterCategories">{{ t('home.filter.select_all') }}</v-btn>
                  <v-btn size="small" variant="text" color="medium-emphasis" @click="clearAllHomeFilterCategories">{{ t('home.filter.select_none') }}</v-btn>
                </div>
              </div>

              <div class="mb-4" style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px;">
                <v-btn
                  v-for="cat in ehCategoryDefs"
                  :key="`f-${cat.key}`"
                  class="category-btn text-caption font-weight-bold"
                  height="32" 
                  rounded="lg" 
                  variant="flat"
                  :style="homeFilterCategoryStyle(cat.key, cat.color)"
                  @click="toggleHomeFilterCategory(cat.key)"
                >
                  <span class="text-truncate">{{ cat.label }}</span>
                </v-btn>
              </div>

              <v-autocomplete
                v-model="homeFilters.tags"
                v-model:search="filterTagInput"
                :items="filterTagSuggestions"
                multiple
                chips
                closable-chips
                clearable
                variant="outlined"
                density="compact"
                color="primary"
                :label="t('home.filter.tags')"
                :hint="t('home.filter.tags_hint')"
                persistent-hint
                class="mb-2"
              />

              <div class="d-flex justify-space-between mt-2">
                <v-btn size="small" :color="config.SEARCH_TAG_SMART_ENABLED ? 'primary' : undefined" :variant="config.SEARCH_TAG_SMART_ENABLED ? 'tonal' : 'outlined'" @click="config.SEARCH_TAG_SMART_ENABLED = !config.SEARCH_TAG_SMART_ENABLED">
                  {{ t('home.filter.smart') }}
                </v-btn>
              </div>

              <div class="d-flex justify-end ga-2 mt-3">
                <v-btn variant="text" @click="clearHomeFilters">{{ t('home.filter.clear') }}</v-btn>
                <v-btn color="primary" variant="flat" @click="applyHomeFilters">{{ t('home.filter.apply') }}</v-btn>
              </div>
            </v-card>
          </v-dialog>

          <v-dialog v-model="quickSearchOpen" max-width="560">
            <v-card class="pa-4" variant="flat">
              <div class="text-subtitle-1 font-weight-medium mb-2">{{ t('home.search.quick_title') }}</div>
              <v-text-field
                v-model="homeSearchQuery"
                density="compact"
                hide-details
                :label="t('home.search.placeholder')"
                variant="outlined"
                @keyup.enter="runQuickSearch"
              />
              <div class="d-flex ga-2 mt-3 justify-end">
                <v-btn variant="text" @click="quickSearchOpen = false">{{ t('home.image_upload.cancel') }}</v-btn>
                <v-btn color="primary" variant="tonal" @click="runQuickSearch">{{ t('home.search.go') }}</v-btn>
                <v-btn color="secondary" variant="tonal" @click="quickImageSearch">{{ t('home.image_upload.title') }}</v-btn>
                <v-btn color="primary" variant="text" @click="openQuickFilters">{{ t('home.filter.title') }}</v-btn>
              </div>
            </v-card>
          </v-dialog>

          <v-dialog v-model="localSortOpen" max-width="520">
            <v-card class="pa-4" variant="flat">
              <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('home.local.sort.title') }}</div>
              <v-radio-group v-model="localSortBy" color="primary" hide-details>
                <v-radio :label="t('home.local.sort.xp')" value="xp" />
                <v-radio :label="t('home.local.sort.date_added')" value="date_added" />
                <v-radio :label="t('home.local.sort.eh_posted')" value="eh_posted" />
              </v-radio-group>
              <v-switch
                v-model="localSortAsc"
                color="primary"
                inset
                hide-details
                class="mt-2"
                :label="localSortAsc ? t('home.local.sort.asc') : t('home.local.sort.desc')"
              />
              <div class="d-flex justify-end ga-2 mt-4">
                <v-btn variant="text" @click="localSortOpen = false">{{ t('home.image_upload.cancel') }}</v-btn>
                <v-btn color="primary" @click="applyLocalSort">{{ t('home.filter.apply') }}</v-btn>
              </div>
            </v-card>
          </v-dialog>
</template>

<script>
import { useDashboardStore } from "../stores/dashboardStore";

export default {
  name: "DashboardPage",
  setup() {
    return useDashboardStore();
  },
  mounted() {
    this.applyReaderOriginRestore();
    this.$nextTick(() => {
      if (typeof this.bindHomeInfiniteScroll === "function") {
        this.bindHomeInfiniteScroll();
      }
    });
  },
  beforeUnmount() {
    if (typeof this.resetRecommendExposureObserver === "function") {
      this.resetRecommendExposureObserver();
    }
  },
  watch: {
    homeTab(next) {
      if (next !== "recommend" && typeof this.resetRecommendExposureObserver === "function") {
        this.resetRecommendExposureObserver();
      }
      const state = this.activeHomeState || {};
      if (!Array.isArray(state.items) || !state.items.length) {
        if (typeof this.resetHomeFeed === "function") {
          this.resetHomeFeed().catch(() => null);
        }
      }
      this.$nextTick(() => {
        if (typeof this.bindHomeInfiniteScroll === "function") {
          this.bindHomeInfiniteScroll();
        }
      });
    },
    filterTagInput() {
      if (typeof this.loadTagSuggestions === "function") {
        this.loadTagSuggestions().catch(() => null);
      }
    },
  },
  methods: {
    applyReaderOriginRestore() {
      if (typeof window === "undefined") return;
      let payload = null;
      try {
        const raw = window.sessionStorage.getItem("aeh_reader_origin");
        if (raw) payload = JSON.parse(raw);
      } catch {
        payload = null;
      }
      if (!payload || typeof payload !== "object") return;
      try {
        window.sessionStorage.removeItem("aeh_reader_origin");
      } catch {
        // ignore
      }
      const tab = String(payload.tab || "").trim();
      if (["recommend", "local", "history", "search"].includes(tab)) {
        this.homeTab = tab;
      }
      const vm = String(payload.viewMode || "").trim();
      if (["wide", "compact", "list"].includes(vm)) {
        this.homeViewMode = vm;
      }
      const y = Number(payload.scrollY || 0);
      this.$nextTick(() => {
        if (Number.isFinite(y) && y > 0) {
          window.requestAnimationFrame(() => {
            window.scrollTo({ top: y, left: 0, behavior: "auto" });
          });
        }
      });
    },
    startReader(item) {
      const arcid = String(item?.arcid || "").trim();
      if (!arcid) return;
      this.mobilePreviewItem = null;
      if (typeof window !== "undefined") {
        const payload = {
          tab: String(this.homeTab || "recommend"),
          viewMode: String(this.homeViewMode || "wide"),
          scrollY: Number(window.scrollY || 0),
          at: Date.now(),
        };
        try {
          window.sessionStorage.setItem("aeh_reader_origin", JSON.stringify(payload));
        } catch {
          // ignore
        }
      }
      this.$router.push({
        name: "reader",
        params: { arcid },
        query: { page: "1", origin: "dashboard" },
      }).catch(() => null);
    },
    onImageError(item) {
      if (!item || !item.thumb_url || item._is_retrying) return;
      if (item._retries === undefined) item._retries = 0;
      if (item._retries >= 3) return;

      item._retries += 1;
      item._is_retrying = true;

      const retryDelayMs = 1500 * item._retries;
      const originalUrl = String(item.thumb_url || "");

      setTimeout(() => {
        const baseUrl = originalUrl.replace(/([?&])r=\d+/g, "").replace(/[?&]$/, "");
        const separator = baseUrl.includes("?") ? "&" : "?";
        const testUrl = `${baseUrl}${separator}r=${Date.now()}`;

        const ghostImg = new Image();
        ghostImg.onload = () => {
          item.thumb_url = testUrl;
          item._is_retrying = false;
        };
        ghostImg.onerror = () => {
          item._is_retrying = false;
          this.onImageError(item);
        };
        ghostImg.src = testUrl;
      }, retryDelayMs);
    },
    openDetailCard(item) {
      this.mobilePreviewItem = item || null;
    },
  },
};
</script>

<style scoped>
.home-tab-row-mobile {
  align-items: stretch;
}

.home-tab-row-mobile .v-tabs {
  width: 100%;
}

.home-tab-row-mobile .home-view-toggle {
  margin: 0 auto;
}

.reader-start-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.reader-start-play {
  pointer-events: auto;
  opacity: 0.32;
  width: 44%;
  max-width: 180px;
  min-width: 96px;
  aspect-ratio: 1 / 1;
  border-radius: 9999px;
}
</style>
