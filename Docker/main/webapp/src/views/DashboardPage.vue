<template>
          <v-card class="pa-4 mb-4">
            <div class="d-flex align-center ga-2 flex-wrap">
              <v-btn icon="mdi-camera-outline" variant="text" @click="imageSearchDialog = true" />
              <v-btn :color="config.SEARCH_NL_ENABLED ? 'primary' : undefined" :variant="config.SEARCH_NL_ENABLED ? 'tonal' : 'text'" icon="mdi-robot-outline" @click="config.SEARCH_NL_ENABLED = !config.SEARCH_NL_ENABLED" />
              <v-text-field
                v-model="homeSearchQuery"
                class="home-search-input"
                density="compact"
                hide-details
                :label="t('home.search.placeholder')"
                variant="outlined"
                @keyup.enter="runHomeSearchPlaceholder"
              />
              <v-btn color="primary" variant="tonal" prepend-icon="mdi-magnify" @click="runHomeSearchPlaceholder">{{ t('home.search.go') }}</v-btn>
              <v-btn v-if="homeTab === 'recommend'" color="secondary" variant="tonal" prepend-icon="mdi-shuffle-variant" @click="shuffleRecommendBatch">{{ t('home.recommend.shuffle') }}</v-btn>
              <v-btn icon="mdi-filter-variant" variant="text" @click="homeFiltersOpen = true" />
            </div>
            <div class="d-flex align-center justify-space-between mt-3 flex-wrap ga-2">
              <v-tabs v-model="homeTab" density="comfortable" color="primary">
                <v-tab value="recommend">{{ t('home.tab.recommend') }}</v-tab>
                <v-tab value="history">{{ t('home.tab.history') }}</v-tab>
                <v-tab value="search">{{ t('home.tab.search') }}</v-tab>
              </v-tabs>
              <v-btn-toggle v-model="homeViewMode" mandatory variant="outlined" class="home-view-toggle">
                <v-btn value="wide">{{ t('home.view.wide') }}</v-btn>
                <v-btn value="compact">{{ t('home.view.compact') }}</v-btn>
                <v-btn value="list">{{ t('home.view.list') }}</v-btn>
              </v-btn-toggle>
            </div>
            <div v-if="homeTab === 'recommend'" class="text-caption text-medium-emphasis mt-2">{{ t('home.recommend.longpress_dislike') }}</div>
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
            <v-list-item v-for="item in filteredHomeItems" :key="item.id" :subtitle="itemSubtitle(item)">
              <template #title>
                <a :href="itemPrimaryLink(item)" :ref="(el) => setRecommendExposureRef(el, item)" target="_blank" rel="noopener noreferrer" class="cover-link-title" @mousedown="onRecommendItemOpen(item)" @click="onRecommendItemOpen(item)">{{ item.title || '-' }}</a>
              </template>
              <template #prepend>
                <div class="list-cover" @contextmenu.prevent>
                  <div v-if="item.thumb_url" class="cover-bg-blur list-blur" :style="{ backgroundImage: `url(${item.thumb_url})` }" />
                  <img v-if="item.thumb_url" :src="item.thumb_url" alt="cover" class="cover-img list-cover-img" loading="lazy" draggable="false" @dragstart.prevent />
                  <v-icon v-else size="18">mdi-image-outline</v-icon>
                </div>
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
                        <img v-if="item.thumb_url" :src="item.thumb_url" alt="cover" class="cover-img" loading="lazy" draggable="false" @dragstart.prevent />
                        <v-icon v-else size="30">mdi-image-outline</v-icon>
                        <div class="cover-guard" @contextmenu.prevent />
                        <div v-if="isRecommendDisliked(item)" class="dislike-mask"><v-icon size="40">mdi-thumb-down</v-icon></div>
                        <div v-if="categoryLabel(item)" class="cat-badge" :style="categoryBadgeStyle(item)">{{ categoryLabel(item) }}</div>
                      </div>
                      <div v-if="homeViewMode === 'compact'" class="cover-title-overlay">{{ item.title || '-' }}</div>
                    </div>
                    <div v-if="homeViewMode !== 'compact'" class="pa-2">
                      <a :href="itemPrimaryLink(item)" :ref="(el) => setRecommendExposureRef(el, item)" target="_blank" rel="noopener noreferrer" class="text-body-2 font-weight-medium text-truncate cover-link-title d-block" @mousedown="onRecommendItemOpen(item)" @click="onRecommendItemOpen(item)">{{ item.title || '-' }}</a>
                      <div class="text-caption text-medium-emphasis text-truncate">{{ itemSubtitle(item) }}</div>
                    </div>
                  </v-card>
                </template>
                <v-card class="pa-2 hover-preview-card" variant="flat">
                  <div class="hover-cover-wrap mb-2" @contextmenu.prevent>
                    <img v-if="item.thumb_url" :src="item.thumb_url" alt="cover" class="hover-cover" draggable="false" @dragstart.prevent />
                    <div v-else class="hover-cover hover-fallback"><v-icon size="42">mdi-image-outline</v-icon></div>
                    <div class="hover-dislike-banner">
                      <v-btn size="small" color="warning" variant="flat" prepend-icon="mdi-thumb-down-outline" @click.stop="markRecommendDislike(item)">{{ t('home.recommend.dislike_action') }}</v-btn>
                    </div>
                  </div>
                  <a :href="itemPrimaryLink(item)" :ref="(el) => setRecommendExposureRef(el, item)" target="_blank" rel="noopener noreferrer" class="text-body-2 font-weight-medium mb-1 cover-link-title d-inline-block" @mousedown="onRecommendItemOpen(item)" @click="onRecommendItemOpen(item)">{{ item.title || '-' }}</a>
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
                <img v-if="mobilePreviewItem.thumb_url" :src="mobilePreviewItem.thumb_url" alt="cover" class="hover-cover" draggable="false" @dragstart.prevent />
                <div v-else class="hover-cover hover-fallback"><v-icon size="42">mdi-image-outline</v-icon></div>
                <div class="hover-dislike-banner">
                  <v-btn size="small" color="warning" variant="flat" prepend-icon="mdi-thumb-down-outline" @click="markRecommendDislike(mobilePreviewItem)">{{ t('home.recommend.dislike_action') }}</v-btn>
                </div>
              </div>
              <a :href="itemPrimaryLink(mobilePreviewItem)" class="text-body-2 font-weight-medium mb-1 cover-link-title d-inline-block" target="_blank" rel="noopener noreferrer" @click="onMobileDetailLinkClick(); onRecommendItemOpen(mobilePreviewItem)">{{ mobilePreviewItem.title || '-' }}</a>
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
              <div class="text-body-2 mb-2">{{ t('home.filter.categories') }}</div>
              <div class="d-flex ga-2 mb-2">
                <v-btn size="small" variant="outlined" @click="selectAllHomeFilterCategories">{{ t('home.filter.select_all') }}</v-btn>
                <v-btn size="small" variant="outlined" @click="clearAllHomeFilterCategories">{{ t('home.filter.select_none') }}</v-btn>
              </div>
              <div class="d-flex flex-wrap ga-2 mb-3">
                <v-btn
                  v-for="cat in ehCategoryDefs"
                  :key="`f-${cat.key}`"
                  class="category-btn"
                  :style="homeFilterCategoryStyle(cat.key, cat.color)"
                  @click="toggleHomeFilterCategory(cat.key)"
                >{{ cat.label }}</v-btn>
              </div>
              <v-autocomplete
                v-model="homeFilters.tags"
                v-model:search="filterTagInput"
                :items="filterTagSuggestions"
                multiple
                chips
                closable-chips
                clearable
                :label="t('home.filter.tags')"
                :hint="t('home.filter.tags_hint')"
                persistent-hint
              />
              <div class="d-flex justify-space-between mt-2">
                <v-btn size="small" :color="config.SEARCH_TAG_SMART_ENABLED ? 'primary' : undefined" :variant="config.SEARCH_TAG_SMART_ENABLED ? 'tonal' : 'outlined'" @click="config.SEARCH_TAG_SMART_ENABLED = !config.SEARCH_TAG_SMART_ENABLED">{{ t('home.filter.smart') }}</v-btn>
              </div>
              <div class="d-flex justify-end ga-2 mt-3">
                <v-btn variant="text" @click="clearHomeFilters">{{ t('home.filter.clear') }}</v-btn>
                <v-btn color="primary" @click="applyHomeFilters">{{ t('home.filter.apply') }}</v-btn>
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
</template>

<script>
import { useDashboardStore } from "../stores/dashboardStore";

export default {
  setup() {
    return useDashboardStore();
  },
  mounted() {
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
};
</script>
