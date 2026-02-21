<template>
  <v-app>
    <v-navigation-drawer v-model="drawer" :rail="rail" permanent border>
      <div class="drawer-brand px-4 py-4">
        <img :src="brandLogo" alt="AutoEhHunter" class="brand-logo" />
        <div v-if="!rail" class="brand-title">AutoEhHunter</div>
      </div>
      <v-divider />
      <v-list nav density="comfortable">
        <v-list-item v-for="item in navItems" :key="item.key" :active="tab === item.key" :prepend-icon="item.icon" :title="t(item.title)" @click="tab = item.key" />
      </v-list>
      <template #append>
        <v-divider />
        <v-list density="compact">
          <v-list-item :title="t('nav.compact')" prepend-icon="mdi-dock-left" @click="rail = !rail" />
        </v-list>
      </template>
    </v-navigation-drawer>

    <v-app-bar flat color="surface">
      <v-app-bar-nav-icon @click="drawer = !drawer" />
      <v-app-bar-title class="font-weight-bold">{{ t(currentTitleKey) }}</v-app-bar-title>
      <v-spacer />
      <v-btn :icon="themeModeIcon" variant="text" @click="cycleThemeMode" />
      <v-menu location="bottom end">
        <template #activator="{ props }">
          <v-btn v-bind="props" icon="mdi-earth" variant="text" />
        </template>
        <v-list density="compact" min-width="160">
          <v-list-item
            v-for="opt in langOptions"
            :key="opt.value"
            :title="opt.title"
            :active="lang === opt.value"
            @click="lang = opt.value"
          />
        </v-list>
      </v-menu>
    </v-app-bar>

    <v-main>
      <v-container fluid class="pa-6">
        <section v-show="tab === 'dashboard'">
          <v-card class="pa-4 mb-4">
            <div class="d-flex align-center ga-2 flex-wrap">
              <v-btn icon="mdi-camera-outline" variant="text" @click="imageSearchDialog = true" />
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
              <v-btn icon="mdi-filter-variant" variant="text" @click="homeFiltersOpen = true" />
            </div>
            <div class="d-flex align-center justify-space-between mt-3 flex-wrap ga-2">
              <v-tabs v-model="homeTab" density="comfortable" color="primary">
                <v-tab value="history">{{ t('home.tab.history') }}</v-tab>
                <v-tab value="recommend">{{ t('home.tab.recommend') }}</v-tab>
                <v-tab value="search">{{ t('home.tab.search') }}</v-tab>
              </v-tabs>
              <v-btn-toggle v-model="homeViewMode" mandatory density="compact" variant="outlined">
                <v-btn value="wide">{{ t('home.view.wide') }}</v-btn>
                <v-btn value="compact">{{ t('home.view.compact') }}</v-btn>
                <v-btn value="list">{{ t('home.view.list') }}</v-btn>
              </v-btn-toggle>
            </div>
          </v-card>

          <v-alert v-if="activeHomeState.error" type="warning" class="mb-3">{{ activeHomeState.error }}</v-alert>

          <v-card v-if="homeTab === 'search'" class="pa-3 mb-3" variant="flat">
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
            <v-list-item v-for="item in filteredHomeItems" :key="item.id" :title="item.title || '-'" :subtitle="itemSubtitle(item)">
              <template #prepend>
                <div class="list-cover">
                  <div v-if="item.thumb_url" class="cover-bg-blur list-blur" :style="{ backgroundImage: `url(${item.thumb_url})` }" />
                  <img v-if="item.thumb_url" :src="item.thumb_url" alt="cover" class="cover-img list-cover-img" loading="lazy" />
                  <v-icon v-else size="18">mdi-image-outline</v-icon>
                </div>
              </template>
              <template #append>
                <v-btn size="small" variant="text" icon="mdi-open-in-new" :href="itemPrimaryLink(item)" target="_blank" rel="noopener noreferrer" />
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
              <v-menu open-on-hover location="end" :open-delay="1000" :close-delay="180" max-width="480">
                <template #activator="{ props }">
                  <v-card
                    v-bind="props"
                    class="home-card"
                    :class="{ compact: homeViewMode === 'compact' }"
                    variant="flat"
                    @touchstart.passive="onCardTouchStart(item)"
                    @touchend.passive="onCardTouchEnd"
                    @touchcancel.passive="onCardTouchEnd"
                  >
                    <a class="cover-anchor" :href="itemPrimaryLink(item)" target="_blank" rel="noopener noreferrer">
                      <div class="cover-ph">
                        <div v-if="item.thumb_url" class="cover-bg-blur" :style="{ backgroundImage: `url(${item.thumb_url})` }" />
                        <img v-if="item.thumb_url" :src="item.thumb_url" alt="cover" class="cover-img" loading="lazy" />
                        <v-icon v-else size="30">mdi-image-outline</v-icon>
                        <div v-if="categoryLabel(item)" class="cat-badge" :style="categoryBadgeStyle(item)">{{ categoryLabel(item) }}</div>
                      </div>
                      <div v-if="homeViewMode === 'compact'" class="cover-title-overlay">{{ item.title || '-' }}</div>
                    </a>
                    <div v-if="homeViewMode !== 'compact'" class="pa-2">
                      <div class="text-body-2 font-weight-medium text-truncate">{{ item.title || '-' }}</div>
                      <div class="text-caption text-medium-emphasis text-truncate">{{ itemSubtitle(item) }}</div>
                    </div>
                  </v-card>
                </template>
                <v-card class="pa-2 hover-preview-card" variant="flat">
                  <div class="hover-cover-wrap mb-2">
                    <img v-if="item.thumb_url" :src="item.thumb_url" alt="cover" class="hover-cover" />
                    <div v-else class="hover-cover hover-fallback"><v-icon size="42">mdi-image-outline</v-icon></div>
                  </div>
                  <div class="text-body-2 font-weight-medium mb-1">{{ item.title || '-' }}</div>
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
              <div class="hover-cover-wrap mb-2">
                <img v-if="mobilePreviewItem.thumb_url" :src="mobilePreviewItem.thumb_url" alt="cover" class="hover-cover" />
                <div v-else class="hover-cover hover-fallback"><v-icon size="42">mdi-image-outline</v-icon></div>
              </div>
              <div class="text-body-2 font-weight-medium mb-1">{{ mobilePreviewItem.title || '-' }}</div>
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
              <div class="d-flex justify-end ga-2 mt-3">
                <v-btn variant="text" @click="clearHomeFilters">{{ t('home.filter.clear') }}</v-btn>
                <v-btn color="primary" @click="applyHomeFilters">{{ t('home.filter.apply') }}</v-btn>
              </div>
            </v-card>
          </v-dialog>
        </section>

        <section v-show="tab === 'chat'">
          <v-row>
            <v-col cols="12" md="3">
              <v-card class="pa-3 chat-sidebar" variant="flat">
                <div class="d-flex align-center justify-space-between mb-2">
                  <div class="text-subtitle-2">{{ t('chat.sessions') }}</div>
                  <v-btn size="small" variant="text" icon="mdi-plus" @click="createChatSession" />
                </div>
                <v-list density="compact" nav>
                  <v-list-item
                    v-for="s in chatSessions"
                    :key="s.id"
                    :title="s.title"
                    :active="chatSessionId === s.id"
                    @click="chatSessionId = s.id"
                  />
                </v-list>
              </v-card>
            </v-col>
            <v-col cols="12" md="9">
              <v-card class="pa-3 chat-main" variant="flat">
                <div class="chat-log mb-3">
                  <div v-for="(m, idx) in (activeChatSession?.messages || [])" :key="`${idx}-${m.time || ''}`" :class="['chat-bubble', m.role === 'assistant' ? 'assistant' : 'user']">
                    <div class="text-body-2">{{ m.text }}</div>
                    <v-card v-if="m.role === 'assistant' && m.payload" class="mt-2 pa-2" variant="outlined">
                      <div class="text-subtitle-2">{{ m.payload.title || m.intent || 'Result' }}</div>
                      <div v-if="m.payload.summary" class="text-caption text-medium-emphasis mb-1">{{ m.payload.summary }}</div>
                      <div v-if="m.payload.narrative" class="text-body-2 mb-2" style="white-space: pre-wrap">{{ m.payload.narrative }}</div>
                      <v-row v-if="Array.isArray(m.payload.items) && m.payload.items.length" class="mt-1">
                        <v-col v-for="it in m.payload.items.slice(0, 6)" :key="`chat-${idx}-${it.id}`" cols="6" sm="4" md="3">
                          <v-menu open-on-hover location="top" :open-delay="700" :close-delay="120" max-width="360">
                            <template #activator="{ props }">
                              <v-card v-bind="props" class="home-card compact" variant="flat" @click="openChatPayloadResult(m.payload)">
                                <div class="cover-ph">
                                  <div v-if="it.thumb_url" class="cover-bg-blur" :style="{ backgroundImage: `url(${it.thumb_url})` }" />
                                  <img v-if="it.thumb_url" :src="it.thumb_url" alt="cover" class="cover-img" loading="lazy" />
                                  <v-icon v-else size="24">mdi-image-outline</v-icon>
                                </div>
                                <div class="cover-title-overlay">{{ it.title || '-' }}</div>
                              </v-card>
                            </template>
                            <v-card class="pa-2 hover-preview-card" variant="flat">
                              <div class="text-body-2 font-weight-medium mb-1">{{ it.title || '-' }}</div>
                              <div class="d-flex flex-wrap ga-1">
                                <v-chip v-for="tag in itemHoverTags(it)" :key="`chat-tag-${tag}`" size="x-small" variant="outlined" class="hover-tag">{{ tag }}</v-chip>
                              </div>
                            </v-card>
                          </v-menu>
                        </v-col>
                      </v-row>
                      <div class="d-flex ga-2 mt-2" v-if="Array.isArray(m.payload.items) && m.payload.items.length > 6">
                        <v-btn size="x-small" variant="tonal" @click="openChatExplore(m.payload)">{{ t('chat.explore.more') }}</v-btn>
                      </div>
                    </v-card>
                    <div class="text-caption text-medium-emphasis mt-1">{{ m.role }} · {{ formatDateMinute(m.time) }}</div>
                  </div>
                </div>
                <div class="d-flex ga-2 align-center">
                  <v-text-field v-model="chatInput" hide-details density="comfortable" :label="t('chat.input')" variant="outlined" @keyup.enter="sendChat('chat')" />
                  <v-select v-model="chatIntent" :items="chatIntentOptions" item-title="title" item-value="value" density="comfortable" hide-details style="max-width: 180px" />
                  <v-btn :loading="chatSending" color="primary" @click="sendChat('chat')">{{ t('chat.send') }}</v-btn>
                </div>
                <div class="d-flex ga-2 mt-2">
                  <v-btn size="small" variant="tonal" @click="sendChat('search_text')">{{ t('chat.action.search_text') }}</v-btn>
                  <v-btn size="small" variant="tonal" @click="tab='dashboard'; homeTab='recommend'">{{ t('chat.action.open_recommend') }}</v-btn>
                  <v-btn size="small" variant="tonal" @click="tab='xp'; chatInput=t('chat.prompt.xp'); sendChat('chat')">{{ t('chat.action.explain_xp') }}</v-btn>
                </div>
              </v-card>
            </v-col>
          </v-row>
        </section>

        <section v-show="tab === 'control'">
          <v-row class="mb-4">
            <v-col cols="12" md="4"><metric-card :title="t('dashboard.metric.works')" :value="health.database?.works ?? 0" /></v-col>
            <v-col cols="12" md="4"><metric-card :title="t('dashboard.metric.eh_works')" :value="health.database?.eh_works ?? 0" /></v-col>
            <v-col cols="12" md="4"><metric-card :title="t('dashboard.metric.last_fetch')" :value="formatDateMinute(health.database?.last_fetch)" /></v-col>
          </v-row>
          <v-alert v-if="health.database?.error" type="warning" class="mb-4">{{ t('dashboard.db_warning', { reason: health.database.error }) }}</v-alert>
          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('control.manual') }}</div>
            <v-row>
              <v-col cols="12" md="4" lg="2"><v-btn block color="primary" @click="triggerTask('eh_fetch')">{{ t('control.btn.eh_fetch') }}</v-btn></v-col>
              <v-col cols="12" md="4" lg="2"><v-btn block color="primary" @click="triggerTask('lrr_export')">{{ t('control.btn.lrr_export') }}</v-btn></v-col>
              <v-col cols="12" md="4" lg="2"><v-btn block color="primary" @click="triggerTask('text_ingest')">{{ t('control.btn.text_ingest') }}</v-btn></v-col>
              <v-col cols="12" md="4" lg="2"><v-btn block color="secondary" @click="triggerTask('eh_lrr_ingest')">{{ t('control.btn.eh_lrr_ingest') }}</v-btn></v-col>
              <v-col cols="12" md="4" lg="2"><v-btn block color="secondary" @click="triggerTask('eh_ingest')">{{ t('control.btn.eh_ingest') }}</v-btn></v-col>
              <v-col cols="12" md="4" lg="2"><v-btn block color="secondary" @click="triggerTask('lrr_ingest')">{{ t('control.btn.lrr_ingest') }}</v-btn></v-col>
            </v-row>
          </v-card>

          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3 d-flex align-center ga-2">
              <span>{{ t('control.scheduler') }}</span>
              <v-tooltip location="top">
                <template #activator="{ props }">
                  <v-btn
                    v-bind="props"
                    icon="mdi-help-circle-outline"
                    size="x-small"
                    variant="text"
                    href="https://crontab.guru/"
                    target="_blank"
                    rel="noopener noreferrer"
                  />
                </template>
                <span>{{ t('control.cron.help') }} e.g. `*/30 * * * *`, `0 3 * * *`, `0 0 * * 1`</span>
              </v-tooltip>
            </div>
            <v-row v-for="(item, key) in schedule" :key="key" class="align-center mb-2">
              <v-col cols="12" md="4">{{ schedulerLabel(key) }}</v-col>
              <v-col cols="12" md="3"><v-switch v-model="item.enabled" color="primary" hide-details /></v-col>
              <v-col cols="12" md="5"><v-text-field v-model="item.cron" :label="`Cron (${schedulerLabel(key)})`" hide-details /></v-col>
            </v-row>
            <v-btn color="primary" @click="saveSchedule">{{ t('control.scheduler.save') }}</v-btn>
          </v-card>

          <v-card class="pa-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('task.state') }}</div>
            <v-table density="compact">
              <thead><tr><th>ID</th><th>Task</th><th>Status</th><th>Start</th><th>Elapsed</th><th>Log</th></tr></thead>
              <tbody>
                <tr v-for="task in tasks" :key="task.task_id">
                  <td class="mono">{{ short(task.task_id) }}</td>
                  <td>{{ task.task }}</td>
                  <td><v-chip size="small" :color="statusColor(task.status)">{{ statusText(task.status) }}</v-chip></td>
                  <td>{{ formatDateTime(task.started_at) }}</td>
                  <td>{{ task.elapsed_s ?? '-' }}</td>
                  <td class="mono text-truncate" style="max-width: 360px">{{ task.log_file || '-' }}</td>
                </tr>
              </tbody>
            </v-table>
          </v-card>
        </section>

        <section v-show="tab === 'audit'">
          <v-row>
            <v-col cols="12" md="5">
              <v-card class="pa-4 mb-3">
                <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('audit.filters') }}</div>
                <v-row>
                  <v-col cols="12" md="6"><v-select v-model="auditFilter.task" :items="taskOptions" :label="t('audit.filter.task')" clearable /></v-col>
                  <v-col cols="12" md="6"><v-select v-model="auditFilter.status" :label="t('audit.filter.status')" :items="['', 'success', 'failed', 'timeout']" /></v-col>
                  <v-col cols="12"><v-text-field v-model="auditFilter.keyword" :label="t('audit.filter.keyword')" /></v-col>
                  <v-col cols="12" md="6"><v-text-field v-model="auditFilter.start_date" type="date" :label="t('audit.filter.start_date')" /></v-col>
                  <v-col cols="12" md="6"><v-text-field v-model="auditFilter.end_date" type="date" :label="t('audit.filter.end_date')" /></v-col>
                  <v-col cols="12" md="6"><v-text-field v-model.number="auditFilter.limit" type="number" min="5" max="500" label="Limit" /></v-col>
                  <v-col cols="12" md="6" class="d-flex align-center ga-2">
                    <v-btn color="primary" @click="applyAuditFilter">{{ t('audit.filter.apply') }}</v-btn>
                    <v-btn variant="text" @click="resetAuditFilter">{{ t('audit.filter.reset') }}</v-btn>
                  </v-col>
                </v-row>
              </v-card>

              <v-card class="pa-4">
                <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('audit.history') }}</div>
                <v-table density="compact">
                  <thead><tr><th>Time</th><th>Task</th><th>Status</th><th>RC</th></tr></thead>
                  <tbody>
                    <tr
                      v-for="row in auditRows"
                      :key="row.task_id + row.ts"
                      class="audit-row"
                      :class="{ selected: selectedLog === logNameFromPath(row.log_file) }"
                      @click="selectAuditRow(row)"
                    >
                      <td>{{ formatDateTime(row.ts) }}</td>
                      <td>{{ row.task }}</td>
                      <td>{{ row.status }}</td>
                      <td>{{ row.rc }}</td>
                    </tr>
                  </tbody>
                </v-table>
                <v-pagination v-model="auditPage" :length="auditPages" :total-visible="7" class="mt-3" />
              </v-card>
            </v-col>

            <v-col cols="12" md="7">
              <v-card class="pa-4">
                <div class="d-flex align-center justify-space-between mb-3">
                  <div class="text-subtitle-1 font-weight-medium">{{ t('audit.logs') }}</div>
                  <v-switch v-model="logAutoStream" color="primary" hide-details :label="t('audit.log.live')" />
                </div>
                <div class="text-caption text-medium-emphasis mb-2">{{ selectedLog || '-' }}</div>
                <v-text-field v-model="logHighlight" class="mt-2" :label="t('audit.log.highlight')" />
                <div class="log-view mono mt-2" v-html="highlightedLogHtml" />
              </v-card>
            </v-col>
          </v-row>
        </section>

        <section v-show="tab === 'xp'">
          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('xp.title') }}</div>
            <v-row>
              <v-col cols="12" md="2"><v-select v-model="xp.mode" :items="[{title:t('xp.mode.read_history'),value:'read_history'},{title:t('xp.mode.inventory'),value:'inventory'}]" item-title="title" item-value="value" :label="t('xp.mode')" /></v-col>
              <v-col cols="12" md="2"><v-select v-model="xp.time_basis" :disabled="xp.mode === 'read_history'" :items="[{title:t('xp.time_basis.read_time'),value:'read_time'},{title:t('xp.time_basis.eh_posted'),value:'eh_posted'},{title:t('xp.time_basis.date_added'),value:'date_added'}]" item-title="title" item-value="value" :label="t('xp.time_basis')" /></v-col>
              <v-col cols="12" md="2">
                <v-select v-model="xpTimeMode" :items="[{title:t('xp.time.mode.window'),value:'window'},{title:t('xp.time.mode.range'),value:'range'}]" item-title="title" item-value="value" :label="t('xp.time.mode')" />
              </v-col>
              <v-col v-if="xpTimeMode === 'window'" cols="12" md="2"><v-text-field v-model.number="xp.days" type="number" :label="t('xp.days')" /></v-col>
              <v-col v-else cols="12" md="2"><v-text-field v-model="xp.start_date" type="date" :label="t('xp.filter.start_date')" /></v-col>
              <v-col v-if="xpTimeMode === 'range'" cols="12" md="2"><v-text-field v-model="xp.end_date" type="date" :label="t('xp.filter.end_date')" /></v-col>
              <v-col cols="12" md="2"><v-text-field v-model.number="xp.max_points" type="number" :label="t('xp.max_points')" /></v-col>
              <v-col cols="12" md="2"><v-text-field v-model.number="xp.k" type="number" :label="t('xp.k')" /></v-col>
              <v-col cols="12" md="2" class="d-flex align-center text-medium-emphasis">{{ t('xp.auto_refresh') }}</v-col>
            </v-row>
            <v-row>
              <v-col cols="12" md="3"><v-switch v-model="xp.exclude_language_tags" :label="t('xp.exclude.language')" hide-details /></v-col>
              <v-col cols="12" md="3"><v-switch v-model="xp.exclude_other_tags" :label="t('xp.exclude.other')" hide-details /></v-col>
              <v-col cols="12" md="3"><v-text-field v-model.number="xp.topn" type="number" :label="t('xp.cluster_topn')" /></v-col>
              <v-col cols="12" md="3" class="d-flex align-center justify-end"><v-btn variant="tonal" @click="resetXpConfig">{{ t('audit.filter.reset') }}</v-btn></v-col>
            </v-row>
            <div class="d-flex ga-2 align-center mb-2">
              <v-text-field v-model="newXpExcludeTag" :label="t('xp.filter.exclude_tags')" @keyup.enter="addXpExcludeTag" />
              <v-btn color="primary" @click="addXpExcludeTag">Add</v-btn>
            </div>
            <div class="d-flex flex-wrap ga-2">
              <v-chip v-for="tag in xpExcludeTags" :key="tag" closable @click:close="removeXpExcludeTag(tag)">{{ tag }}</v-chip>
            </div>
          </v-card>

          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('xp.chart_title') }}</div>
            <div ref="xpChartEl" style="width: 100%; height: 520px" />
          </v-card>

          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('xp.dendrogram.title') }}</div>
            <div class="d-flex align-center ga-4 mb-2" v-if="xpResult.dendrogram?.available">
              <v-pagination v-model="xp.dendro_page" :length="xpResult.dendrogram?.pages || 1" :total-visible="6" />
              <v-select v-model.number="xp.dendro_page_size" :items="[40,60,80,100,150,200]" label="Page size" style="max-width: 160px" />
            </div>
            <div v-if="xpResult.dendrogram?.available" class="dendro-wrap">
              <div ref="dendroChartEl" style="width: 100%; height: 800px" />
            </div>
            <v-alert v-else type="info">{{ xpResult.dendrogram?.reason || t('xp.dendrogram.too_few') }}</v-alert>
          </v-card>

          <v-card class="pa-4">
            <v-table density="compact">
              <thead><tr><th>Cluster</th><th>Count</th><th>Top terms</th></tr></thead>
              <tbody><tr v-for="c in xpResult.clusters || []" :key="c.cluster_id"><td>{{ c.name }}</td><td>{{ c.count }}</td><td>{{ (c.top_terms || []).join(', ') }}</td></tr></tbody>
            </v-table>
          </v-card>
        </section>

        <section v-show="tab === 'settings'">
          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-2">{{ t('settings.title') }}</div>
            <div class="text-body-2 text-medium-emphasis">{{ t('settings.source', { chain: configMeta.sources || 'db > json > env' }) }}</div>
            <v-chip class="mt-2" :color="configMeta.db_connected ? 'success' : 'warning'" variant="tonal">
              {{ configMeta.db_connected ? t('settings.db_connected') : t('settings.db_disconnected', { reason: configMeta.db_error || 'n/a' }) }}
            </v-chip>
            <v-alert v-if="limitedModeMessages.length" type="warning" variant="tonal" class="mt-3">
              {{ t('settings.limited_mode.title') }} {{ limitedModeMessages.join(' / ') }}
            </v-alert>
          </v-card>

          <v-tabs v-model="settingsTab" class="mb-4" color="primary">
            <v-tab value="general">{{ t('settings.tab.general') }}</v-tab>
            <v-tab value="eh">{{ t('settings.tab.eh') }}</v-tab>
            <v-tab value="data_clean">{{ t('settings.tab.data_clean') }}</v-tab>
            <v-tab value="search">{{ t('settings.tab.search') }}</v-tab>
            <v-tab value="recommend">{{ t('settings.tab.recommend') }}</v-tab>
            <v-tab value="llm">{{ t('settings.tab.llm') }}</v-tab>
            <v-tab value="other">{{ t('settings.tab.other') }}</v-tab>
          </v-tabs>

          <v-card v-show="settingsTab === 'general'" class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('dashboard.health') }}</div>
            <v-row>
              <v-col cols="12" md="6"><service-chip :title="t('health.lrr')" :ok="health.services?.lrr?.ok" :message="health.services?.lrr?.message" /></v-col>
              <v-col cols="12" md="6"><service-chip :title="t('health.llm')" :ok="health.services?.llm?.ok" :message="health.services?.llm?.message" /></v-col>
            </v-row>
          </v-card>

          <v-card v-show="settingsTab === 'general'" class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.db') }}</div>
            <v-row>
              <v-col cols="12" md="4"><v-text-field v-model="config.POSTGRES_HOST" :label="labelFor('POSTGRES_HOST')" /></v-col>
              <v-col cols="12" md="2"><v-text-field v-model="config.POSTGRES_PORT" :label="labelFor('POSTGRES_PORT')" type="number" /></v-col>
              <v-col cols="12" md="3"><v-text-field v-model="config.POSTGRES_DB" :label="labelFor('POSTGRES_DB')" /></v-col>
              <v-col cols="12" md="3"><v-text-field v-model="config.POSTGRES_USER" :label="labelFor('POSTGRES_USER')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.POSTGRES_PASSWORD" :label="labelFor('POSTGRES_PASSWORD')" type="password" :placeholder="t('settings.secret.keep')" :hint="secretHint('POSTGRES_PASSWORD')" persistent-hint /></v-col>
              <v-col cols="12" md="6"><v-select v-model="config.POSTGRES_SSLMODE" :items="['disable','allow','prefer','require','verify-ca','verify-full']" :label="labelFor('POSTGRES_SSLMODE')" /></v-col>
            </v-row>
          </v-card>

          <v-card v-show="settingsTab === 'general'" class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.urls') }}</div>
            <v-row>
              <v-col cols="12" md="6"><v-text-field v-model="config.LRR_BASE" :label="labelFor('LRR_BASE')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.OPENAI_HEALTH_URL" :label="labelFor('OPENAI_HEALTH_URL')" /></v-col>
            </v-row>
          </v-card>

          <v-card v-show="settingsTab === 'general'" class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.secrets') }}</div>
            <v-row>
              <v-col cols="12" md="6"><v-text-field v-model="config.LRR_API_KEY" :label="labelFor('LRR_API_KEY')" type="password" :placeholder="t('settings.secret.keep')" :hint="secretHint('LRR_API_KEY')" persistent-hint /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.INGEST_API_KEY" :label="labelFor('INGEST_API_KEY')" type="password" :placeholder="t('settings.secret.keep')" :hint="secretHint('INGEST_API_KEY')" persistent-hint /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.LLM_API_KEY" :label="labelFor('LLM_API_KEY')" type="password" :placeholder="t('settings.secret.keep')" :hint="secretHint('LLM_API_KEY')" persistent-hint /></v-col>
            </v-row>
          </v-card>

          <v-card v-show="settingsTab === 'general'" class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.appearance') }}</div>
            <v-row>
              <v-col cols="12" md="4"><v-select v-model="config.DATA_UI_THEME_MODE" :items="themeModeOptions" item-title="title" item-value="value" :label="labelFor('DATA_UI_THEME_MODE')" /></v-col>
              <v-col cols="12" md="4"><v-select v-model="config.DATA_UI_THEME_PRESET" :items="themeOptions" item-title="title" item-value="value" :label="labelFor('DATA_UI_THEME_PRESET')" /></v-col>
              <v-col cols="12" md="4"><v-switch v-model="config.DATA_UI_THEME_OLED" :label="labelFor('DATA_UI_THEME_OLED')" hide-details /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.DATA_UI_THEME_CUSTOM_PRIMARY" :label="labelFor('DATA_UI_THEME_CUSTOM_PRIMARY')" type="color" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.DATA_UI_THEME_CUSTOM_SECONDARY" :label="labelFor('DATA_UI_THEME_CUSTOM_SECONDARY')" type="color" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.DATA_UI_THEME_CUSTOM_ACCENT" :label="labelFor('DATA_UI_THEME_CUSTOM_ACCENT')" type="color" /></v-col>
            </v-row>
          </v-card>

          <v-card v-show="settingsTab === 'general'" class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.runtime') }}</div>
            <v-row>
              <v-col cols="12" md="4"><v-select v-model="config.DATA_UI_TIMEZONE" :items="timezoneOptions" :label="labelFor('DATA_UI_TIMEZONE')" /></v-col>
              <v-col cols="12" md="8" class="d-flex align-center ga-2">
                <v-chip variant="tonal" color="info">{{ t('settings.cache.stats', { files: thumbCacheStats.files || 0, mb: thumbCacheStats.mb || 0, latest: thumbCacheStats.latest_at || '-' }) }}</v-chip>
                <v-btn variant="outlined" color="warning" @click="clearThumbCacheAction">{{ t('settings.cache.clear') }}</v-btn>
              </v-col>
              <v-col cols="12" md="12" class="d-flex align-center ga-2 flex-wrap">
                <v-chip variant="tonal" color="secondary">{{ t('settings.model.siglip_status', { mb: modelStatus.siglip?.size_mb || 0 }) }}</v-chip>
                <v-chip variant="tonal" :color="modelStatus.runtime_deps?.ready ? 'success' : 'warning'">{{ t('settings.model.runtime_deps', { mb: modelStatus.runtime_deps?.size_mb || 0, ready: modelStatus.runtime_deps?.ready ? 'yes' : 'no' }) }}</v-chip>
                <v-btn variant="outlined" color="primary" @click="downloadSiglipAction">{{ t('settings.model.siglip_download') }}</v-btn>
                <v-btn variant="outlined" color="error" @click="clearSiglipAction">{{ t('settings.model.siglip_clear') }}</v-btn>
                <v-btn variant="outlined" color="warning" @click="clearRuntimeDepsAction">{{ t('settings.model.runtime_deps_clear') }}</v-btn>
                <v-chip v-if="siglipDownload.status" variant="outlined">{{ t('settings.model.siglip_task', { status: siglipDownload.status, stage: siglipDownload.stage || '-' }) }}</v-chip>
              </v-col>
              <v-col cols="12" md="12" v-if="siglipDownload.status && siglipDownload.status !== 'done'">
                <v-progress-linear :model-value="Number(siglipDownload.progress || 0)" color="primary" height="14">
                  <template #default>{{ Number(siglipDownload.progress || 0) }}%</template>
                </v-progress-linear>
                <div class="text-caption text-medium-emphasis mt-1" v-if="siglipDownload.error">{{ siglipDownload.error }}</div>
              </v-col>
              <v-col cols="12" md="12" v-if="Array.isArray(siglipDownload.logs) && siglipDownload.logs.length">
                <div class="model-log-view mono">{{ siglipDownload.logs.slice(-8).join('\n') }}</div>
              </v-col>
            </v-row>
          </v-card>

          <v-card v-show="settingsTab === 'eh'" class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.eh.cookie') }} <v-chip size="small" class="ml-2" variant="tonal">{{ secretHint('EH_COOKIE') }}</v-chip></div>
            <v-row>
              <v-col cols="12" md="6"><v-text-field v-model="cookieParts.ipb_member_id" label="ipb_member_id" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="cookieParts.ipb_pass_hash" label="ipb_pass_hash" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="cookieParts.sk" label="sk" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="cookieParts.igneous" label="igneous" /></v-col>
            </v-row>
          </v-card>

          <v-card v-show="settingsTab === 'eh'" class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.eh.filter_category') }}</div>
            <div class="category-grid">
              <v-btn
                v-for="cat in ehCategoryDefs"
                :key="cat.key"
                class="category-btn"
                :style="categoryStyle(cat.key, cat.color)"
                @click="toggleCategory(cat.key)"
              >
                {{ cat.label }}
              </v-btn>
            </div>
          </v-card>

          <v-card v-show="settingsTab === 'eh'" class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.eh.filter_tag') }}</div>
            <div class="d-flex ga-2 align-center mb-3">
              <v-text-field v-model="newEhTag" :label="t('settings.eh.filter_tag')" @keyup.enter="addEhTag" />
              <v-btn color="primary" @click="addEhTag">Add</v-btn>
            </div>
            <div class="d-flex flex-wrap ga-2">
              <v-chip v-for="tag in ehFilterTags" :key="tag" closable @click:close="removeEhTag(tag)">{{ tag }}</v-chip>
            </div>
          </v-card>

          <v-card v-show="settingsTab === 'eh'" class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.eh_crawler') }}</div>
            <v-row>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_BASE_URL" :label="labelFor('EH_BASE_URL')" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_FETCH_MAX_PAGES" :label="labelFor('EH_FETCH_MAX_PAGES')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_REQUEST_SLEEP" :label="labelFor('EH_REQUEST_SLEEP')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_SAMPLING_DENSITY" :label="labelFor('EH_SAMPLING_DENSITY')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_USER_AGENT" :label="labelFor('EH_USER_AGENT')" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_MIN_RATING" :label="labelFor('EH_MIN_RATING')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_QUEUE_LIMIT" :label="labelFor('EH_QUEUE_LIMIT')" type="number" /></v-col>
            </v-row>
          </v-card>

          <v-card v-show="settingsTab === 'recommend'" class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.recommend') }}</div>
            <v-alert type="info" variant="tonal" class="mb-3">
              {{ t('settings.recommend.tuning_hint') }}
              <template #append>
                <v-btn size="small" variant="outlined" @click="resetRecommendPreset">{{ t('settings.recommend.reset') }}</v-btn>
              </template>
            </v-alert>
            <v-row>
              <v-col cols="12" md="4"><v-text-field v-model="config.LRR_READS_HOURS" :label="labelFor('LRR_READS_HOURS')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.REC_PROFILE_DAYS" :label="labelFor('REC_PROFILE_DAYS')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.REC_CANDIDATE_HOURS" :label="labelFor('REC_CANDIDATE_HOURS')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.REC_CANDIDATE_LIMIT" :label="labelFor('REC_CANDIDATE_LIMIT')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.REC_CLUSTER_K" :label="labelFor('REC_CLUSTER_K')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.REC_CLUSTER_CACHE_TTL_S" :label="labelFor('REC_CLUSTER_CACHE_TTL_S')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-slider v-model="config.REC_STRICTNESS" min="0" max="1" step="0.01" :label="labelFor('REC_STRICTNESS')" thumb-label /></v-col>
              <v-col cols="12" md="4"><v-slider v-model="config.REC_TAG_WEIGHT" min="0" max="1" step="0.01" :label="labelFor('REC_TAG_WEIGHT')" thumb-label /></v-col>
              <v-col cols="12" md="4"><v-slider v-model="config.REC_VISUAL_WEIGHT" min="0" max="1" step="0.01" :label="labelFor('REC_VISUAL_WEIGHT')" thumb-label /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.REC_TAG_FLOOR_SCORE" :label="labelFor('REC_TAG_FLOOR_SCORE')" type="number" step="0.01" /></v-col>
            </v-row>
          </v-card>

          <v-card v-show="settingsTab === 'data_clean'" class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.tab.data_clean') }}</div>
            <v-row>
              <v-col cols="12" md="8"><v-text-field v-model="config.INGEST_API_BASE" :label="labelFor('INGEST_API_BASE')" /></v-col>
              <v-col cols="12" md="4" class="d-flex align-center"><v-btn variant="outlined" block @click="reloadIngestModels">{{ t('settings.models.reload') }}</v-btn></v-col>
              <v-col cols="12" md="6"><v-combobox v-model="config.INGEST_VL_MODEL" :items="ingestModelOptions" :label="labelFor('INGEST_VL_MODEL')" clearable /></v-col>
              <v-col cols="12" md="6"><v-combobox v-model="config.INGEST_EMB_MODEL" :items="ingestModelOptions" :label="labelFor('INGEST_EMB_MODEL')" clearable /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.INGEST_VL_MODEL_CUSTOM" :label="labelFor('INGEST_VL_MODEL_CUSTOM')" clearable /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.INGEST_EMB_MODEL_CUSTOM" :label="labelFor('INGEST_EMB_MODEL_CUSTOM')" clearable /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.SIGLIP_MODEL" :label="labelFor('SIGLIP_MODEL')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.WORKER_BATCH" :label="labelFor('WORKER_BATCH')" type="number" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.WORKER_SLEEP" :label="labelFor('WORKER_SLEEP')" type="number" /></v-col>
              <v-col cols="12" md="6"><v-switch v-model="config.TEXT_INGEST_PRUNE_NOT_SEEN" :label="labelFor('TEXT_INGEST_PRUNE_NOT_SEEN')" /></v-col>
              <v-col cols="12" md="6"><v-switch v-model="config.WORKER_ONLY_MISSING" :label="labelFor('WORKER_ONLY_MISSING')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.TEXT_INGEST_BATCH_SIZE" :label="labelFor('TEXT_INGEST_BATCH_SIZE')" type="number" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.TAG_TRANSLATION_REPO" :label="labelFor('TAG_TRANSLATION_REPO')" clearable :hint="t('settings.translation.repo_hint')" persistent-hint /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.TAG_TRANSLATION_AUTO_UPDATE_HOURS" :label="labelFor('TAG_TRANSLATION_AUTO_UPDATE_HOURS')" type="number" /></v-col>
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
          </v-card>

          <v-card v-show="settingsTab === 'search'" class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.tab.search') }}</div>
            <v-alert type="info" variant="tonal" class="mb-3">
              {{ t('settings.search.tuning_hint') }}
              <template #append>
                <v-btn size="small" variant="outlined" @click="resetSearchWeightPresets">{{ t('settings.search.reset_presets') }}</v-btn>
              </template>
            </v-alert>
            <v-row>
              <v-col cols="12" md="6"><v-switch v-model="config.SEARCH_NL_ENABLED" :label="labelFor('SEARCH_NL_ENABLED')" /></v-col>
              <v-col cols="12" md="6"><v-switch v-model="config.SEARCH_TAG_SMART_ENABLED" :label="labelFor('SEARCH_TAG_SMART_ENABLED')" /></v-col>
              <v-col cols="12" md="6"><v-switch v-model="config.SEARCH_TAG_HARD_FILTER" :label="labelFor('SEARCH_TAG_HARD_FILTER')" /></v-col>
              <v-col cols="12" md="6"><v-select v-model="config.SEARCH_RESULT_SIZE" :items="[20,50,100]" :label="labelFor('SEARCH_RESULT_SIZE')" /></v-col>
              <v-col cols="12" md="6"><v-switch v-model="config.SEARCH_RESULT_INFINITE" :label="labelFor('SEARCH_RESULT_INFINITE')" /></v-col>
              <v-col cols="12"><div class="text-caption text-medium-emphasis">{{ t('settings.search.preset.visual') }}</div></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_WEIGHT_VISUAL" min="0" max="5" step="0.01" :label="labelFor('SEARCH_WEIGHT_VISUAL')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_WEIGHT_EH_VISUAL" min="0" max="5" step="0.01" :label="labelFor('SEARCH_WEIGHT_EH_VISUAL')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_WEIGHT_DESC" min="0" max="5" step="0.01" :label="labelFor('SEARCH_WEIGHT_DESC')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_WEIGHT_TEXT" min="0" max="5" step="0.01" :label="labelFor('SEARCH_WEIGHT_TEXT')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_WEIGHT_EH_TEXT" min="0" max="5" step="0.01" :label="labelFor('SEARCH_WEIGHT_EH_TEXT')" thumb-label /></v-col>
              <v-col cols="12"><div class="text-caption text-medium-emphasis">{{ t('settings.search.preset.plot') }}</div></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_WEIGHT_PLOT_VISUAL" min="0" max="5" step="0.01" :label="labelFor('SEARCH_WEIGHT_PLOT_VISUAL')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_WEIGHT_PLOT_EH_VISUAL" min="0" max="5" step="0.01" :label="labelFor('SEARCH_WEIGHT_PLOT_EH_VISUAL')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_WEIGHT_PLOT_DESC" min="0" max="5" step="0.01" :label="labelFor('SEARCH_WEIGHT_PLOT_DESC')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_WEIGHT_PLOT_TEXT" min="0" max="5" step="0.01" :label="labelFor('SEARCH_WEIGHT_PLOT_TEXT')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_WEIGHT_PLOT_EH_TEXT" min="0" max="5" step="0.01" :label="labelFor('SEARCH_WEIGHT_PLOT_EH_TEXT')" thumb-label /></v-col>
              <v-col cols="12"><div class="text-caption text-medium-emphasis">{{ t('settings.search.preset.mixed') }}</div></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_WEIGHT_MIXED_VISUAL" min="0" max="5" step="0.01" :label="labelFor('SEARCH_WEIGHT_MIXED_VISUAL')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_WEIGHT_MIXED_EH_VISUAL" min="0" max="5" step="0.01" :label="labelFor('SEARCH_WEIGHT_MIXED_EH_VISUAL')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_WEIGHT_MIXED_DESC" min="0" max="5" step="0.01" :label="labelFor('SEARCH_WEIGHT_MIXED_DESC')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_WEIGHT_MIXED_TEXT" min="0" max="5" step="0.01" :label="labelFor('SEARCH_WEIGHT_MIXED_TEXT')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_WEIGHT_MIXED_EH_TEXT" min="0" max="5" step="0.01" :label="labelFor('SEARCH_WEIGHT_MIXED_EH_TEXT')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_TAG_FUZZY_THRESHOLD" min="0.2" max="1" step="0.01" :label="labelFor('SEARCH_TAG_FUZZY_THRESHOLD')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_TEXT_WEIGHT" min="0" max="1" step="0.01" :label="labelFor('SEARCH_TEXT_WEIGHT')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_VISUAL_WEIGHT" min="0" max="1" step="0.01" :label="labelFor('SEARCH_VISUAL_WEIGHT')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_MIXED_TEXT_WEIGHT" min="0" max="1" step="0.01" :label="labelFor('SEARCH_MIXED_TEXT_WEIGHT')" thumb-label /></v-col>
              <v-col cols="12" md="6"><v-slider v-model="config.SEARCH_MIXED_VISUAL_WEIGHT" min="0" max="1" step="0.01" :label="labelFor('SEARCH_MIXED_VISUAL_WEIGHT')" thumb-label /></v-col>
            </v-row>
          </v-card>

          <v-card v-show="settingsTab === 'llm'" class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.tab.llm') }}</div>
            <v-row>
              <v-col cols="12" md="8"><v-text-field v-model="config.LLM_API_BASE" :label="labelFor('LLM_API_BASE')" /></v-col>
              <v-col cols="12" md="4" class="d-flex align-center"><v-btn variant="outlined" block @click="reloadLlmModels">{{ t('settings.models.reload') }}</v-btn></v-col>
              <v-col cols="12" md="6"><v-combobox v-model="config.LLM_MODEL" :items="llmModelOptions" :label="labelFor('LLM_MODEL')" clearable /></v-col>
              <v-col cols="12" md="6"><v-combobox v-model="config.EMB_MODEL" :items="llmModelOptions" :label="labelFor('EMB_MODEL')" clearable /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.LLM_MODEL_CUSTOM" :label="labelFor('LLM_MODEL_CUSTOM')" clearable /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.EMB_MODEL_CUSTOM" :label="labelFor('EMB_MODEL_CUSTOM')" clearable /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.LLM_API_KEY" :label="labelFor('LLM_API_KEY')" type="password" :placeholder="t('settings.secret.keep')" :hint="secretHint('LLM_API_KEY')" persistent-hint /></v-col>
              <v-col cols="12"><v-textarea v-model="config.PROMPT_SEARCH_NARRATIVE_SYSTEM" :label="labelFor('PROMPT_SEARCH_NARRATIVE_SYSTEM')" rows="4" auto-grow /></v-col>
              <v-col cols="12"><v-textarea v-model="config.PROMPT_PROFILE_SYSTEM" :label="labelFor('PROMPT_PROFILE_SYSTEM')" rows="4" auto-grow /></v-col>
              <v-col cols="12"><v-textarea v-model="config.PROMPT_REPORT_SYSTEM" :label="labelFor('PROMPT_REPORT_SYSTEM')" rows="4" auto-grow /></v-col>
              <v-col cols="12"><v-textarea v-model="config.PROMPT_TAG_EXTRACT_SYSTEM" :label="labelFor('PROMPT_TAG_EXTRACT_SYSTEM')" rows="4" auto-grow /></v-col>
              <v-col cols="12">
                <div class="text-subtitle-2 mb-2">{{ t('skills.builtin.title') }}</div>
                <div class="d-flex flex-wrap ga-2">
                  <v-chip v-for="s in builtinSkills" :key="`bi-${s.name}`" color="primary" variant="tonal">{{ s.name }}</v-chip>
                </div>
              </v-col>
              <v-col cols="12">
                <div class="text-subtitle-2 mb-2">{{ t('skills.user.title') }}</div>
                <div class="d-flex ga-2 align-center mb-2">
                  <input ref="pluginUploadRef" type="file" accept=".py" @change="onPluginUploadChange" />
                  <v-btn variant="outlined" @click="loadSkillsData">{{ t('skills.reload') }}</v-btn>
                </div>
                <div class="d-flex flex-wrap ga-2">
                  <v-chip v-for="s in userSkills" :key="`usr-${s.name}`" variant="outlined">{{ s.name }}</v-chip>
                </div>
                <div class="text-caption text-medium-emphasis mt-2">{{ (pluginFiles || []).join(', ') || '-' }}</div>
              </v-col>
            </v-row>
          </v-card>

          <v-card v-show="settingsTab === 'other'" class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-2">{{ t('settings.tab.other') }}</div>
            <div class="text-body-2 text-medium-emphasis">{{ t('settings.other.placeholder') }}</div>
          </v-card>

          <v-btn color="primary" size="large" @click="saveConfig">{{ t('settings.save') }}</v-btn>
        </section>
      </v-container>
    </v-main>

    <div class="chat-fab-wrap">
      <v-btn color="primary" icon="mdi-chat" size="large" class="chat-fab" @click="chatFabOpen = !chatFabOpen" />
      <v-card v-if="chatFabOpen" class="chat-fab-panel pa-3" variant="flat">
        <div class="d-flex align-center justify-space-between mb-2">
          <div class="text-subtitle-2">{{ t('chat.fab.title') }}</div>
          <v-btn size="x-small" icon="mdi-close" variant="text" @click="chatFabOpen=false" />
        </div>
        <div class="chat-fab-log mb-2">
          <div v-for="(m, idx) in (activeChatSession?.messages || []).slice(-6)" :key="`fab-${idx}-${m.time || ''}`" :class="['chat-bubble mini', m.role === 'assistant' ? 'assistant' : 'user']">
            <div class="text-caption">{{ m.text }}</div>
          </div>
        </div>
        <div class="d-flex ga-2 align-center">
          <v-text-field v-model="chatInput" hide-details density="compact" :label="t('chat.input')" variant="outlined" @keyup.enter="sendChat('chat')" />
          <v-select v-model="chatIntent" :items="chatIntentOptions" item-title="title" item-value="value" density="compact" hide-details style="max-width: 150px" />
          <v-btn size="small" :loading="chatSending" color="primary" @click="sendChat('chat')">{{ t('chat.send') }}</v-btn>
        </div>
      </v-card>
    </div>

    <v-dialog v-model="chatExploreOpen" max-width="980">
      <v-card class="pa-3" variant="flat">
        <div class="d-flex align-center justify-space-between mb-2">
          <div class="text-subtitle-1">{{ chatExplorePayload?.title || t('chat.explore.title') }}</div>
          <v-btn size="small" icon="mdi-close" variant="text" @click="chatExploreOpen=false" />
        </div>
        <v-row>
          <v-col v-for="it in (chatExplorePayload?.items || [])" :key="`chat-exp-${it.id}`" cols="6" sm="4" md="3" lg="2">
            <v-card class="home-card compact" variant="flat" @click="openChatExploreItem()">
              <div class="cover-ph">
                <div v-if="it.thumb_url" class="cover-bg-blur" :style="{ backgroundImage: `url(${it.thumb_url})` }" />
                <img v-if="it.thumb_url" :src="it.thumb_url" alt="cover" class="cover-img" loading="lazy" />
                <v-icon v-else size="24">mdi-image-outline</v-icon>
              </div>
              <div class="cover-title-overlay">{{ it.title || '-' }}</div>
            </v-card>
          </v-col>
        </v-row>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="toast.show" :color="toast.color" timeout="3000">{{ toast.text }}</v-snackbar>
  </v-app>
</template>

<script setup>
import { computed, defineComponent, h, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useTheme } from "vuetify";
import {
  getAuditHistory,
  getAuditLogContent,
  getAuditLogTail,
  getAuditLogs,
  getAuditTasks,
  getConfig,
  getConfigSchema,
  getHealth,
  getHomeHistory,
  getHomeRecommend,
  getHomeTagSuggest,
  getModelStatus,
  getProviderModels,
  getSiglipDownloadStatus,
  getSkills,
  getThumbCacheStats,
  getChatHistory,
  getTranslationStatus,
  getSchedule,
  getTasks,
  getXpMap,
  downloadSiglip,
  clearSiglip,
  clearRuntimeDeps,
  runTask,
  clearThumbCache,
  searchByImage,
  searchByImageUpload,
  searchByText,
  sendChatMessage,
  uploadSkillPlugin,
  uploadTranslationFile,
  updateConfig,
  updateSchedule,
} from "./api";
import { getInitialLang, setLang, t as tr } from "./i18n";
import brandLogo from "./ico/AutoEhHunterLogo_128.png";

const drawer = ref(true);
const rail = ref(false);
const tab = ref("dashboard");
const lang = ref(getInitialLang());
const langOptions = [
  { title: "简体中文", value: "zh" },
  { title: "English", value: "en" },
];
const theme = useTheme();
const themeOptions = [
  { title: "Modern", value: "modern" },
  { title: "Ocean", value: "ocean" },
  { title: "Sunset", value: "sunset" },
  { title: "Forest", value: "forest" },
  { title: "Slate", value: "slate" },
  { title: "Custom", value: "custom" },
];
const themeModeOptions = computed(() => [
  { title: t("theme.mode.system"), value: "system" },
  { title: t("theme.mode.light"), value: "light" },
  { title: t("theme.mode.dark"), value: "dark" },
]);
const timezoneOptions = ref(["UTC", "Asia/Shanghai", "Asia/Tokyo", "America/New_York", "Europe/Berlin"]);

const health = ref({ database: {}, services: {} });
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
const schedule = ref({});
const tasks = ref([]);
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
const thumbCacheStats = ref({ files: 0, mb: 0, latest_at: "-" });
const translationStatus = ref({ repo: "", head_sha: "", fetched_at: "-", manual_file: { path: "", exists: false, size: 0, updated_at: "-" } });
const translationUploadRef = ref(null);
const modelStatus = ref({ siglip: { path: "", size_mb: 0 } });
const siglipDownload = ref({ task_id: "", status: "", progress: 0, stage: "", error: "", logs: [] });
let siglipPollTimer = null;
const chatFabOpen = ref(false);
const chatSessions = ref([{ id: "default", title: "New Chat", messages: [] }]);
const chatSessionId = ref("default");
const chatInput = ref("");
const chatIntent = ref("auto");
const chatSending = ref(false);
const chatExploreOpen = ref(false);
const chatExplorePayload = ref(null);
const imageSearchDialog = ref(false);
const imageDropActive = ref(false);
const selectedImageFile = ref(null);
const imageFileInputRef = ref(null);

const auditRows = ref([]);
const auditLogs = ref([]);
const taskOptions = ref([]);
const selectedLog = ref("");
const selectedLogContent = ref("");
const logOffset = ref(0);
const logAutoStream = ref(true);
const logHighlight = ref("");
const auditFilter = ref({ task: "", status: "", keyword: "", start_date: "", end_date: "", limit: 15, offset: 0 });
const auditPage = ref(1);
const auditTotal = ref(0);

const xpChartEl = ref(null);
const dendroChartEl = ref(null);

const xp = ref({
  mode: "read_history",
  time_basis: "read_time",
  max_points: 1800,
  days: 30,
  k: 3,
  topn: 3,
  exclude_language_tags: true,
  exclude_other_tags: false,
  start_date: "",
  end_date: "",
  dendro_page: 1,
  dendro_page_size: 100,
});
const xpTimeMode = ref("window");
const xpResult = ref({ meta: {}, clusters: [], points: [], dendrogram: null });
const xpExcludeTags = ref([]);
const newXpExcludeTag = ref("");

const cookieParts = ref({ ipb_member_id: "", ipb_pass_hash: "", sk: "", igneous: "" });
const ehFilterTags = ref([]);
const newEhTag = ref("");
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
if (!homeFilters.value.categories.length) {
  homeFilters.value.categories = ehCategoryDefs.map((x) => x.key);
}
const ehCategoryAllowMap = ref(Object.fromEntries(ehCategoryDefs.map((x) => [x.key, true])));
const ehCategoryMap = Object.fromEntries(ehCategoryDefs.map((x) => [String(x.key).toLowerCase(), x]));
const mobilePreviewItem = ref(null);

let tasksEventSource = null;
let dashboardTimer = null;
let logTimer = null;
let Plotly = null;
let prefersDarkMedia = null;
let prefersDarkListener = null;
let touchPreviewTimer = null;
let agentWeightSyncing = false;

const toast = ref({ show: false, text: "", color: "success" });

const navItems = [
  { key: "dashboard", title: "tab.dashboard", icon: "mdi-view-dashboard-outline" },
  { key: "chat", title: "tab.chat", icon: "mdi-chat-processing-outline" },
  { key: "control", title: "tab.control", icon: "mdi-console" },
  { key: "audit", title: "tab.audit", icon: "mdi-clipboard-text-clock-outline" },
  { key: "xp", title: "tab.xp_map", icon: "mdi-chart-bubble" },
  { key: "settings", title: "tab.settings", icon: "mdi-cog-outline" },
];

const currentTitleKey = computed(() => navItems.find((x) => x.key === tab.value)?.title || "tab.dashboard");
const chatIntentOptions = computed(() => ([
  { title: t("chat.intent.auto"), value: "auto" },
  { title: t("chat.intent.chat"), value: "chat" },
  { title: t("chat.intent.profile"), value: "profile" },
  { title: t("chat.intent.search"), value: "search" },
  { title: t("chat.intent.report"), value: "report" },
  { title: t("chat.intent.recommendation"), value: "recommendation" },
]));
const themeModeIcon = computed(() => {
  const mode = String(config.value.DATA_UI_THEME_MODE || "system");
  if (mode === "light") return "mdi-weather-sunny";
  if (mode === "dark") return "mdi-weather-night";
  return "mdi-brightness-auto";
});
const limitedModeMessages = computed(() => {
  const out = [];
  const ingestBase = String(config.value.INGEST_API_BASE || "").trim();
  const ingestVl = String(config.value.INGEST_VL_MODEL_CUSTOM || config.value.INGEST_VL_MODEL || "").trim();
  const ingestEmb = String(config.value.INGEST_EMB_MODEL_CUSTOM || config.value.INGEST_EMB_MODEL || "").trim();
  if (!ingestBase || !ingestVl || !ingestEmb) out.push(t("settings.limited_mode.ingest"));
  const llmBase = String(config.value.LLM_API_BASE || "").trim();
  const llmModel = String(config.value.LLM_MODEL_CUSTOM || config.value.LLM_MODEL || "").trim();
  const embModel = String(config.value.EMB_MODEL_CUSTOM || config.value.EMB_MODEL || "").trim();
  if (!llmBase || !llmModel || !embModel) out.push(t("settings.limited_mode.llm"));
  return out;
});
const auditPages = computed(() => {
  const per = Math.max(1, Number(auditFilter.value.limit || 15));
  return Math.max(1, Math.ceil(Number(auditTotal.value || 0) / per));
});

const highlightedLogHtml = computed(() => {
  const raw = String(selectedLogContent.value || "");
  const escaped = escapeHtml(raw);
  const kw = String(logHighlight.value || "").trim();
  if (!kw) return escaped.replace(/\n/g, "<br>");
  const re = new RegExp(escapeRegExp(kw), "gi");
  return escaped.replace(re, (m) => `<mark>${m}</mark>`).replace(/\n/g, "<br>");
});

const activeHomeState = computed(() => {
  if (homeTab.value === "history") return homeHistory.value;
  if (homeTab.value === "recommend") return homeRecommend.value;
  return homeSearchState.value;
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
const activeChatSession = computed(() => {
  const found = (chatSessions.value || []).find((s) => s.id === chatSessionId.value);
  return found || chatSessions.value[0];
});

function t(key, vars = {}) {
  return tr(lang.value, key, vars);
}

function notify(text, color = "success") {
  toast.value = { show: true, text, color };
}

function ensureHexColor(value, fallback) {
  const s = String(value || "").trim();
  return /^#[0-9a-fA-F]{6}$/.test(s) ? s : fallback;
}

function shiftHex(hex, delta) {
  const clean = String(hex || "").replace("#", "");
  if (!/^[0-9a-fA-F]{6}$/.test(clean)) return hex;
  const num = Number.parseInt(clean, 16);
  const r = Math.max(0, Math.min(255, ((num >> 16) & 255) + delta));
  const g = Math.max(0, Math.min(255, ((num >> 8) & 255) + delta));
  const b = Math.max(0, Math.min(255, (num & 255) + delta));
  return `#${[r, g, b].map((x) => x.toString(16).padStart(2, "0")).join("")}`;
}

function uiTimezone() {
  const tz = String(config.value.DATA_UI_TIMEZONE || health.value?.database?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  return tz || "UTC";
}

function formatDateTime(value) {
  if (!value || value === "-") return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return new Intl.DateTimeFormat(lang.value === "zh" ? "zh-CN" : "en-US", {
    timeZone: uiTimezone(),
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(d);
}

function formatDateMinute(value) {
  if (!value || value === "-") return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value).slice(0, 16).replace("T", " ");
  return new Intl.DateTimeFormat(lang.value === "zh" ? "zh-CN" : "en-US", {
    timeZone: uiTimezone(),
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);
}

function applyTheme() {
  const modeSetting = String(config.value.DATA_UI_THEME_MODE || "system");
  const systemDark = typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)").matches : false;
  const dark = modeSetting === "dark" || (modeSetting === "system" && systemDark);
  const preset = String(config.value.DATA_UI_THEME_PRESET || "modern");
  const themes = theme.themes.value;
  const useCustom = preset === "custom";
  if (useCustom) {
    const primary = ensureHexColor(config.value.DATA_UI_THEME_CUSTOM_PRIMARY, "#6750A4");
    const secondary = ensureHexColor(config.value.DATA_UI_THEME_CUSTOM_SECONDARY, "#625B71");
    const accent = ensureHexColor(config.value.DATA_UI_THEME_CUSTOM_ACCENT, "#7D5260");
    themes.customLight = {
      dark: false,
      colors: {
        primary,
        secondary,
        info: accent,
        surface: "#ffffff",
        background: shiftHex(primary, 235),
      },
    };
    themes.customDark = {
      dark: true,
      colors: {
        primary: shiftHex(primary, 72),
        secondary: shiftHex(secondary, 72),
        info: shiftHex(accent, 72),
        surface: "#1d1b20",
        background: _asBool(config.value.DATA_UI_THEME_OLED) ? "#000000" : "#141218",
      },
    };
  }
  const mode = dark ? "Dark" : "Light";
  const baseName = `${preset}${mode}`;
  const fallbackName = `modern${mode}`;
  const resolvedBaseName = themes[baseName] ? baseName : fallbackName;
  const oled = dark && _asBool(config.value.DATA_UI_THEME_OLED);
  if (oled) {
    const oledName = `${resolvedBaseName}Oled`;
    const baseTheme = themes[resolvedBaseName];
    themes[oledName] = {
      ...baseTheme,
      dark: true,
      colors: {
        ...(baseTheme?.colors || {}),
        background: "#000000",
        surface: "#000000",
      },
    };
    theme.global.name.value = oledName;
    return;
  }
  theme.global.name.value = resolvedBaseName;
}

function _asBool(v) {
  return String(v).toLowerCase() === "true" || String(v) === "1";
}

function itemSubtitle(item) {
  const src = item?.source === "eh_works" ? "EH" : "LRR";
  const epoch = item?.meta?.read_time || item?.meta?.posted || item?.meta?.date_added;
  const cat = categoryLabel(item);
  return `${src} · ${formatEpoch(epoch)}${cat ? ` · ${cat}` : ""}`;
}

function formatEpoch(v) {
  const ep = Number(v || 0);
  if (!ep) return "-";
  return formatDateMinute(new Date(ep * 1000).toISOString());
}

function itemPrimaryLink(item) {
  return item?.link_url || item?.eh_url || item?.ex_url || "#";
}

function categoryLabel(item) {
  const raw = String(item?.category || "").trim().toLowerCase();
  if (raw && ehCategoryMap[raw]) return ehCategoryMap[raw].label;
  if (raw) return raw;
  return "";
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
  const cur = [...(homeFilters.value.tags || [])];
  const idx = cur.findIndex((x) => String(x || "").trim().toLowerCase() === t.toLowerCase());
  if (idx >= 0) cur.splice(idx, 1);
  else cur.push(t);
  homeFilters.value.tags = cur;
  if (homeTab.value === "search") rerunSearchWithFilters().catch(() => null);
}

function cycleThemeMode() {
  const now = String(config.value.DATA_UI_THEME_MODE || "system");
  if (now === "system") config.value.DATA_UI_THEME_MODE = "light";
  else if (now === "light") config.value.DATA_UI_THEME_MODE = "dark";
  else config.value.DATA_UI_THEME_MODE = "system";
  applyTheme();
}

async function loadThumbCacheStats() {
  try {
    thumbCacheStats.value = await getThumbCacheStats();
  } catch {
    // ignore
  }
}

async function clearThumbCacheAction() {
  const res = await clearThumbCache();
  notify(t("settings.cache.cleared", { mb: res.freed_mb ?? 0 }), "success");
  await loadThumbCacheStats();
}

async function loadTranslationStatus() {
  try {
    translationStatus.value = await getTranslationStatus();
  } catch {
    // ignore
  }
}

async function onTranslationUploadChange(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  await uploadTranslationFile(file);
  notify(t("settings.translation.uploaded"), "success");
  await loadTranslationStatus();
  if (translationUploadRef.value) translationUploadRef.value.value = "";
}

async function loadModelStatus() {
  try {
    const res = await getModelStatus();
    modelStatus.value = res.model || res || {};
    if (res.download) siglipDownload.value = { ...siglipDownload.value, ...res.download };
  } catch {
    // ignore
  }
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
      // ignore one poll failure
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

function ensureChatSession() {
  if (!chatSessions.value.length) {
    chatSessions.value = [{ id: "default", title: "New Chat", messages: [] }];
    chatSessionId.value = "default";
  }
  if (!chatSessions.value.find((s) => s.id === chatSessionId.value)) {
    chatSessionId.value = chatSessions.value[0].id;
  }
}

function createChatSession() {
  const id = `s-${Date.now()}`;
  chatSessions.value.unshift({ id, title: "New Chat", messages: [] });
  chatSessionId.value = id;
}

async function loadChatHistory() {
  ensureChatSession();
  try {
    const res = await getChatHistory({ session_id: chatSessionId.value });
    const sess = activeChatSession.value;
    if (sess) sess.messages = res.messages || [];
  } catch {
    // ignore
  }
}

async function sendChat(mode = "chat") {
  if (chatSending.value) return;
  const text = String(chatInput.value || "").trim();
  if (!text && mode === "chat") return;
  ensureChatSession();
  chatSending.value = true;
  try {
    const res = await sendChatMessage({
      session_id: chatSessionId.value,
      text,
      mode,
      intent: chatIntent.value,
      ui_lang: lang.value,
      context: { page: tab.value },
    });
    const sess = activeChatSession.value;
    if (sess) {
      sess.messages = res.history || [];
      if (text && sess.title === "New Chat") sess.title = text.slice(0, 24);
    }
    chatInput.value = "";
  } catch (e) {
    notify(String(e?.response?.data?.detail || e), "warning");
  } finally {
    chatSending.value = false;
  }
}

function openChatExplore(payload) {
  chatExplorePayload.value = payload || null;
  chatExploreOpen.value = true;
}

function openChatPayloadResult(payload) {
  const p = payload || {};
  if (String(p.type || "") === "profile" || String(p.type || "") === "report") {
    openChatExplore(p);
    return;
  }
  const items = Array.isArray(p.items) ? p.items : [];
  const tabKey = String(p.home_tab || "").trim();
  if (tabKey === "recommend") {
    homeRecommend.value.items = items;
    homeRecommend.value.cursor = "";
    homeRecommend.value.hasMore = false;
    tab.value = "dashboard";
    homeTab.value = "recommend";
  } else if (tabKey === "history") {
    homeHistory.value.items = items;
    homeHistory.value.cursor = "";
    homeHistory.value.hasMore = false;
    tab.value = "dashboard";
    homeTab.value = "history";
  } else {
    homeSearchState.value.items = items;
    homeSearchState.value.cursor = "";
    homeSearchState.value.hasMore = false;
    tab.value = "dashboard";
    homeTab.value = "search";
  }
  chatExploreOpen.value = false;
}

function openChatExploreItem() {
  const p = chatExplorePayload.value || {};
  const items = Array.isArray(p.items) ? p.items : [];
  if (String(p.home_tab || "") === "history") {
    homeHistory.value.items = items;
    homeHistory.value.cursor = "";
    homeHistory.value.hasMore = false;
    tab.value = "dashboard";
    homeTab.value = "history";
  }
  chatExploreOpen.value = false;
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
    if (sum <= 0) {
      config.value[prefixA] = 0.5;
      config.value[prefixB] = 0.5;
    } else {
      config.value[prefixA] = Number((ca / sum).toFixed(4));
      config.value[prefixB] = Number((cb / sum).toFixed(4));
    }
  }
}

function normalizeAgentChannelWeights(changedKey, keys = [
  "SEARCH_WEIGHT_VISUAL",
  "SEARCH_WEIGHT_EH_VISUAL",
  "SEARCH_WEIGHT_DESC",
  "SEARCH_WEIGHT_TEXT",
  "SEARCH_WEIGHT_EH_TEXT",
]) {
  if (agentWeightSyncing) return;
  agentWeightSyncing = true;
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
    agentWeightSyncing = false;
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
  normalizeAgentChannelWeights("SEARCH_WEIGHT_VISUAL");
  normalizeAgentChannelWeights("SEARCH_WEIGHT_PLOT_DESC", ["SEARCH_WEIGHT_PLOT_VISUAL", "SEARCH_WEIGHT_PLOT_EH_VISUAL", "SEARCH_WEIGHT_PLOT_DESC", "SEARCH_WEIGHT_PLOT_TEXT", "SEARCH_WEIGHT_PLOT_EH_TEXT"]);
  normalizeAgentChannelWeights("SEARCH_WEIGHT_MIXED_DESC", ["SEARCH_WEIGHT_MIXED_VISUAL", "SEARCH_WEIGHT_MIXED_EH_VISUAL", "SEARCH_WEIGHT_MIXED_DESC", "SEARCH_WEIGHT_MIXED_TEXT", "SEARCH_WEIGHT_MIXED_EH_TEXT"]);
}

function normalizeRecommendWeights(changedKey) {
  const a = Number(config.value.REC_TAG_WEIGHT ?? 0.55);
  const b = Number(config.value.REC_VISUAL_WEIGHT ?? 0.45);
  const ca = Number.isFinite(a) ? Math.max(0, Math.min(1, a)) : 0.55;
  const cb = Number.isFinite(b) ? Math.max(0, Math.min(1, b)) : 0.45;
  if (changedKey === "REC_TAG_WEIGHT") {
    config.value.REC_TAG_WEIGHT = ca;
    config.value.REC_VISUAL_WEIGHT = Number((1 - ca).toFixed(4));
  } else if (changedKey === "REC_VISUAL_WEIGHT") {
    config.value.REC_VISUAL_WEIGHT = cb;
    config.value.REC_TAG_WEIGHT = Number((1 - cb).toFixed(4));
  } else {
    const sum = ca + cb;
    if (sum <= 0) {
      config.value.REC_TAG_WEIGHT = 0.55;
      config.value.REC_VISUAL_WEIGHT = 0.45;
    } else {
      config.value.REC_TAG_WEIGHT = Number((ca / sum).toFixed(4));
      config.value.REC_VISUAL_WEIGHT = Number((cb / sum).toFixed(4));
    }
  }
}

function resetRecommendPreset() {
  config.value.REC_STRICTNESS = 0.55;
  config.value.REC_TAG_WEIGHT = 0.55;
  config.value.REC_VISUAL_WEIGHT = 0.45;
  normalizeRecommendWeights();
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

function effectiveFilterCategories() {
  const all = ehCategoryDefs.map((x) => x.key);
  const selected = homeFilters.value.categories || [];
  if (selected.length === all.length) return [];
  if (selected.length === 0) return ["__none__"];
  return selected;
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
  const ctx = lastSearchContext.value || {};
  const fallbackQ = String(homeSearchQuery.value || "").trim();
  const q = String(ctx.query || fallbackQ || "").trim();
  if (ctx.mode === "text" && String(ctx.query || "").trim()) {
    const res = await searchByText({ query: q, scope: "both", limit: searchResultLimit(), use_llm: !!config.value.SEARCH_NL_ENABLED, ui_lang: lang.value, include_categories: cats, include_tags: tags });
    homeSearchState.value.items = res.items || [];
    lastSearchContext.value = { mode: "text", query: q, hasImage: false };
    return;
  }
  if ((ctx.mode === "image" || selectedImageFile.value) && selectedImageFile.value) {
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

let homeObserver = null;
function bindHomeInfiniteScroll() {
  if (homeObserver) {
    homeObserver.disconnect();
    homeObserver = null;
  }
  if (!homeSentinel.value) return;
  homeObserver = new IntersectionObserver((entries) => {
    const first = entries[0];
    if (!first?.isIntersecting) return;
    loadHomeFeed(false).catch(() => null);
  }, { root: null, rootMargin: "600px 0px", threshold: 0.01 });
  homeObserver.observe(homeSentinel.value);
}

function short(id) {
  return id ? String(id).slice(0, 8) : "-";
}

function schedulerLabel(key) {
  return t(`scheduler.${key}`);
}

function statusColor(status) {
  if (status === "running") return "warning";
  if (status === "success") return "success";
  return "error";
}

function statusText(status) {
  if (status === "running") return t("task.running");
  if (status === "success") return t("task.success");
  if (status === "timeout") return t("task.timeout");
  return t("task.failed");
}

function secretHint(key) {
  return secretState.value[key] ? t("settings.secret.present") : t("settings.secret.empty");
}

function escapeHtml(s) {
  return s.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
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
    DATA_UI_THEME_CUSTOM_PRIMARY: "settings.ui.custom_primary",
    DATA_UI_THEME_CUSTOM_SECONDARY: "settings.ui.custom_secondary",
    DATA_UI_THEME_CUSTOM_ACCENT: "settings.ui.custom_accent",
    REC_PROFILE_DAYS: "settings.rec.profile_days",
    REC_CANDIDATE_HOURS: "settings.rec.candidate_hours",
    REC_CLUSTER_K: "settings.rec.cluster_k",
    REC_CLUSTER_CACHE_TTL_S: "settings.rec.cache_ttl",
    REC_TAG_WEIGHT: "settings.rec.tag_weight",
    REC_VISUAL_WEIGHT: "settings.rec.visual_weight",
    REC_STRICTNESS: "settings.rec.strictness",
    REC_CANDIDATE_LIMIT: "settings.rec.candidate_limit",
    REC_TAG_FLOOR_SCORE: "settings.rec.tag_floor",
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
    TAG_TRANSLATION_REPO: "settings.translation.repo",
    TAG_TRANSLATION_AUTO_UPDATE_HOURS: "settings.translation.auto_update_hours",
    PROMPT_SEARCH_NARRATIVE_SYSTEM: "settings.prompt.search_narrative",
    PROMPT_PROFILE_SYSTEM: "settings.prompt.profile",
    PROMPT_REPORT_SYSTEM: "settings.prompt.report",
    PROMPT_TAG_EXTRACT_SYSTEM: "settings.prompt.tag_extract",
    TEXT_INGEST_PRUNE_NOT_SEEN: "settings.text_ingest.prune",
    WORKER_ONLY_MISSING: "settings.worker.only_missing",
    LRR_READS_HOURS: "settings.lrr.reads_hours",
    EH_BASE_URL: "settings.eh.base_url",
    EH_FETCH_MAX_PAGES: "settings.eh.max_pages",
    EH_REQUEST_SLEEP: "settings.eh.request_sleep",
    EH_SAMPLING_DENSITY: "settings.eh.sampling_density",
    EH_USER_AGENT: "settings.eh.user_agent",
    EH_MIN_RATING: "settings.eh.min_rating",
    EH_FILTER_TAG: "settings.eh.filter_tag",
    TEXT_INGEST_BATCH_SIZE: "settings.text_ingest.batch",
    EH_QUEUE_LIMIT: "settings.eh.queue_limit",
    LLM_API_BASE: "settings.provider.llm_api_base",
    LLM_API_KEY: "settings.provider.llm_api_key",
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
  };
  const tk = map[key];
  return tk ? t(tk) : key;
}

function parseCookie(raw) {
  const out = { ipb_member_id: "", ipb_pass_hash: "", sk: "", igneous: "" };
  String(raw || "").split(";").forEach((part) => {
    const i = part.indexOf("=");
    if (i < 0) return;
    const k = part.slice(0, i).trim();
    const v = part.slice(i + 1).trim();
    if (k in out) out[k] = v;
  });
  return out;
}

function buildCookie(parts) {
  return ["ipb_member_id", "ipb_pass_hash", "sk", "igneous"]
    .map((k) => (parts[k] ? `${k}=${parts[k]}` : ""))
    .filter(Boolean)
    .join("; ");
}

function parseCsv(raw) {
  return String(raw || "")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}

function toggleCategory(key) {
  ehCategoryAllowMap.value[key] = !ehCategoryAllowMap.value[key];
}

function categoryStyle(key, color) {
  const on = !!ehCategoryAllowMap.value[key];
  return {
    backgroundColor: on ? color : "#424242",
    color: "#ffffff",
    opacity: on ? 1 : 0.45,
  };
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

async function loadDashboard() {
  health.value = await getHealth();
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
  const nextMap = Object.fromEntries(ehCategoryDefs.map((x) => [x.key, !blocked.has(x.key)]));
  ehCategoryAllowMap.value = nextMap;
  if (config.value.DATA_UI_LANG === "en" || config.value.DATA_UI_LANG === "zh") {
    lang.value = config.value.DATA_UI_LANG;
  }
  if (!config.value.DATA_UI_THEME_MODE) config.value.DATA_UI_THEME_MODE = "system";
  if (!config.value.DATA_UI_THEME_PRESET) config.value.DATA_UI_THEME_PRESET = "modern";
  if (!config.value.DATA_UI_TIMEZONE) config.value.DATA_UI_TIMEZONE = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  if (!config.value.DATA_UI_THEME_CUSTOM_PRIMARY) config.value.DATA_UI_THEME_CUSTOM_PRIMARY = "#6750A4";
  if (!config.value.DATA_UI_THEME_CUSTOM_SECONDARY) config.value.DATA_UI_THEME_CUSTOM_SECONDARY = "#625B71";
  if (!config.value.DATA_UI_THEME_CUSTOM_ACCENT) config.value.DATA_UI_THEME_CUSTOM_ACCENT = "#7D5260";
  if (!config.value.REC_PROFILE_DAYS) config.value.REC_PROFILE_DAYS = 30;
  if (!config.value.REC_CANDIDATE_HOURS) config.value.REC_CANDIDATE_HOURS = 24;
  if (!config.value.REC_CLUSTER_K) config.value.REC_CLUSTER_K = 3;
  if (!config.value.REC_CLUSTER_CACHE_TTL_S) config.value.REC_CLUSTER_CACHE_TTL_S = 900;
  if (!config.value.REC_TAG_WEIGHT) config.value.REC_TAG_WEIGHT = 0.55;
  if (!config.value.REC_VISUAL_WEIGHT) config.value.REC_VISUAL_WEIGHT = 0.45;
  if (!config.value.REC_STRICTNESS) config.value.REC_STRICTNESS = 0.55;
  if (!config.value.REC_CANDIDATE_LIMIT) config.value.REC_CANDIDATE_LIMIT = 400;
  if (!config.value.REC_TAG_FLOOR_SCORE) config.value.REC_TAG_FLOOR_SCORE = 0.08;
  if (config.value.SEARCH_TEXT_WEIGHT === undefined) config.value.SEARCH_TEXT_WEIGHT = 0.6;
  if (config.value.SEARCH_VISUAL_WEIGHT === undefined) config.value.SEARCH_VISUAL_WEIGHT = 0.4;
  if (config.value.SEARCH_MIXED_TEXT_WEIGHT === undefined) config.value.SEARCH_MIXED_TEXT_WEIGHT = 0.5;
  if (config.value.SEARCH_MIXED_VISUAL_WEIGHT === undefined) config.value.SEARCH_MIXED_VISUAL_WEIGHT = 0.5;
  if (config.value.SEARCH_NL_ENABLED === undefined) config.value.SEARCH_NL_ENABLED = false;
  if (config.value.SEARCH_TAG_SMART_ENABLED === undefined) config.value.SEARCH_TAG_SMART_ENABLED = false;
  if (config.value.SEARCH_TAG_HARD_FILTER === undefined) config.value.SEARCH_TAG_HARD_FILTER = true;
  if (!config.value.SEARCH_RESULT_SIZE) config.value.SEARCH_RESULT_SIZE = 20;
  if (config.value.SEARCH_RESULT_INFINITE === undefined) config.value.SEARCH_RESULT_INFINITE = false;
  if (config.value.SEARCH_WEIGHT_VISUAL === undefined) config.value.SEARCH_WEIGHT_VISUAL = 2.0;
  if (config.value.SEARCH_WEIGHT_EH_VISUAL === undefined) config.value.SEARCH_WEIGHT_EH_VISUAL = 1.6;
  if (config.value.SEARCH_WEIGHT_DESC === undefined) config.value.SEARCH_WEIGHT_DESC = 0.8;
  if (config.value.SEARCH_WEIGHT_TEXT === undefined) config.value.SEARCH_WEIGHT_TEXT = 0.7;
  if (config.value.SEARCH_WEIGHT_EH_TEXT === undefined) config.value.SEARCH_WEIGHT_EH_TEXT = 0.7;
  if (config.value.SEARCH_WEIGHT_PLOT_VISUAL === undefined) config.value.SEARCH_WEIGHT_PLOT_VISUAL = 0.6;
  if (config.value.SEARCH_WEIGHT_PLOT_EH_VISUAL === undefined) config.value.SEARCH_WEIGHT_PLOT_EH_VISUAL = 0.5;
  if (config.value.SEARCH_WEIGHT_PLOT_DESC === undefined) config.value.SEARCH_WEIGHT_PLOT_DESC = 2.0;
  if (config.value.SEARCH_WEIGHT_PLOT_TEXT === undefined) config.value.SEARCH_WEIGHT_PLOT_TEXT = 0.9;
  if (config.value.SEARCH_WEIGHT_PLOT_EH_TEXT === undefined) config.value.SEARCH_WEIGHT_PLOT_EH_TEXT = 0.9;
  if (config.value.SEARCH_WEIGHT_MIXED_VISUAL === undefined) config.value.SEARCH_WEIGHT_MIXED_VISUAL = 1.2;
  if (config.value.SEARCH_WEIGHT_MIXED_EH_VISUAL === undefined) config.value.SEARCH_WEIGHT_MIXED_EH_VISUAL = 1.0;
  if (config.value.SEARCH_WEIGHT_MIXED_DESC === undefined) config.value.SEARCH_WEIGHT_MIXED_DESC = 1.4;
  if (config.value.SEARCH_WEIGHT_MIXED_TEXT === undefined) config.value.SEARCH_WEIGHT_MIXED_TEXT = 0.9;
  if (config.value.SEARCH_WEIGHT_MIXED_EH_TEXT === undefined) config.value.SEARCH_WEIGHT_MIXED_EH_TEXT = 0.9;
  if (!config.value.SEARCH_TAG_FUZZY_THRESHOLD) config.value.SEARCH_TAG_FUZZY_THRESHOLD = 0.62;
  normalizeAgentChannelWeights("SEARCH_WEIGHT_VISUAL");
  normalizeAgentChannelWeights("SEARCH_WEIGHT_PLOT_DESC", ["SEARCH_WEIGHT_PLOT_VISUAL", "SEARCH_WEIGHT_PLOT_EH_VISUAL", "SEARCH_WEIGHT_PLOT_DESC", "SEARCH_WEIGHT_PLOT_TEXT", "SEARCH_WEIGHT_PLOT_EH_TEXT"]);
  normalizeAgentChannelWeights("SEARCH_WEIGHT_MIXED_DESC", ["SEARCH_WEIGHT_MIXED_VISUAL", "SEARCH_WEIGHT_MIXED_EH_VISUAL", "SEARCH_WEIGHT_MIXED_DESC", "SEARCH_WEIGHT_MIXED_TEXT", "SEARCH_WEIGHT_MIXED_EH_TEXT"]);
  config.value.SIGLIP_DEVICE = "cpu";
  if (!config.value.TAG_TRANSLATION_AUTO_UPDATE_HOURS) config.value.TAG_TRANSLATION_AUTO_UPDATE_HOURS = 24;
  if (!config.value.LLM_API_BASE) config.value.LLM_API_BASE = "";
  if (!config.value.INGEST_API_BASE) config.value.INGEST_API_BASE = "";
  if (!config.value.LLM_MODEL) config.value.LLM_MODEL = "";
  if (!config.value.EMB_MODEL) config.value.EMB_MODEL = "";
  if (!config.value.INGEST_VL_MODEL) config.value.INGEST_VL_MODEL = "";
  if (!config.value.INGEST_EMB_MODEL) config.value.INGEST_EMB_MODEL = "";
  if (config.value.REC_STRICTNESS === undefined) config.value.REC_STRICTNESS = 0.55;
  if (config.value.REC_TAG_WEIGHT === undefined) config.value.REC_TAG_WEIGHT = 0.55;
  if (config.value.REC_VISUAL_WEIGHT === undefined) config.value.REC_VISUAL_WEIGHT = 0.45;
  normalizeRecommendWeights();
  normalizeSearchWeights("SEARCH_TEXT_WEIGHT", "SEARCH_VISUAL_WEIGHT");
  normalizeSearchWeights("SEARCH_MIXED_TEXT_WEIGHT", "SEARCH_MIXED_VISUAL_WEIGHT");
  if (typeof Intl.supportedValuesOf === "function") {
    try {
      const zones = Intl.supportedValuesOf("timeZone");
      if (Array.isArray(zones) && zones.length) timezoneOptions.value = zones;
    } catch {
      // ignore
    }
  }
  applyTheme();
  await Promise.all([reloadIngestModels(), reloadLlmModels(), loadSkillsData()]);
}

async function reloadIngestModels() {
  const base = String(config.value.INGEST_API_BASE || "").trim();
  if (!base) {
    ingestModelOptions.value = [];
    return;
  }
  const apiKey = String(config.value.INGEST_API_KEY || "").trim();
  try {
    const res = await getProviderModels(base, apiKey);
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
  const apiKey = String(config.value.LLM_API_KEY || "").trim();
  try {
    const res = await getProviderModels(base, apiKey);
    llmModelOptions.value = Array.isArray(res.models) ? res.models : [];
  } catch {
    llmModelOptions.value = [];
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

async function saveConfig() {
  const blocked = Object.entries(ehCategoryAllowMap.value)
    .filter(([, allow]) => !allow)
    .map(([key]) => key);
  const payload = {
    ...config.value,
    EH_COOKIE: buildCookie(cookieParts.value),
    EH_FILTER_TAG: ehFilterTags.value.join(","),
    EH_FILTER_CATEGORY: blocked.join(","),
    DATA_UI_LANG: lang.value,
  };
  const res = await updateConfig(payload);
  notify(res.saved_db ? t("settings.saved_db") : t("settings.saved_db_failed", { reason: res.db_error || "n/a" }), res.saved_db ? "success" : "warning");
  await loadConfigData();
}

async function loadScheduleData() {
  const data = await getSchedule();
  schedule.value = data.schedule || {};
}

async function saveSchedule() {
  await updateSchedule(schedule.value);
  notify(t("control.scheduler.saved"));
}

async function triggerTask(task, args = "") {
  await runTask(task, args);
  notify(`${t("task.start")}: ${task}`);
}

async function loadTasks() {
  const data = await getTasks();
  tasks.value = data.tasks || [];
}

async function setupTaskStream() {
  if (tasksEventSource) tasksEventSource.close();
  tasksEventSource = new EventSource("/api/tasks/stream");
  tasksEventSource.onmessage = (evt) => {
    try {
      const payload = JSON.parse(evt.data || "{}");
      tasks.value = (payload.tasks || []).sort((a, b) => String(b.started_at || "").localeCompare(String(a.started_at || ""))).slice(0, 200);
    } catch {
      // ignore
    }
  };
}

async function loadAudit() {
  const page = Math.max(1, Number(auditPage.value || 1));
  const limit = Math.max(1, Number(auditFilter.value.limit || 15));
  const offset = (page - 1) * limit;
  const history = await getAuditHistory({ ...auditFilter.value, limit, offset });
  auditRows.value = history.rows || [];
  auditTotal.value = Number(history.total || 0);
  const logs = await getAuditLogs();
  auditLogs.value = logs.logs || [];
  const tasksRes = await getAuditTasks();
  taskOptions.value = tasksRes.tasks || [];
  if (!selectedLog.value && auditRows.value.length) {
    await selectAuditRow(auditRows.value[0]);
  } else if (!selectedLog.value && auditLogs.value.length) {
    selectedLog.value = auditLogs.value[0];
    await loadLog(selectedLog.value);
  }
}

function resetAuditFilter() {
  auditFilter.value = { task: "", status: "", keyword: "", start_date: "", end_date: "", limit: 15, offset: 0 };
  auditPage.value = 1;
  loadAudit();
}

function resetXpConfig() {
  xp.value = {
    ...xp.value,
    days: 30,
    start_date: "",
    end_date: "",
    max_points: 1800,
    k: 3,
    topn: 3,
    exclude_language_tags: true,
    exclude_other_tags: false,
    dendro_page: 1,
    dendro_page_size: 100,
  };
  xpTimeMode.value = "window";
  xpExcludeTags.value = [];
}

function applyAuditFilter() {
  auditPage.value = 1;
  loadAudit();
}

function logNameFromPath(logFile) {
  if (!logFile) return "";
  return String(logFile).split(/[\\/]/).pop() || "";
}

async function selectAuditRow(row) {
  if (!row) return;
  const name = logNameFromPath(row.log_file);
  if (!name) return;
  selectedLog.value = name;
  await loadLog(name);
}

async function loadLog(name = "") {
  const target = name || selectedLog.value;
  if (!target) return;
  selectedLog.value = target;
  const data = await getAuditLogContent(target);
  selectedLogContent.value = data.content || "";
  logOffset.value = selectedLogContent.value.length;
}

async function pollLogTail() {
  if (!logAutoStream.value || !selectedLog.value) return;
  const data = await getAuditLogTail(selectedLog.value, logOffset.value, 12000);
  if (data.chunk) {
    selectedLogContent.value += data.chunk;
    if (selectedLogContent.value.length > 200000) {
      selectedLogContent.value = selectedLogContent.value.slice(-200000);
    }
  }
  logOffset.value = Number(data.next_offset || logOffset.value);
}

async function renderXpChart() {
  if (!xpChartEl.value) return;
  if (!Plotly) {
    const mod = await import("plotly.js-dist-min");
    Plotly = mod.default;
  }
  const points = xpResult.value.points || [];
  const byCluster = new Map();
  points.forEach((p) => {
    const key = p.cluster || "cluster";
    if (!byCluster.has(key)) byCluster.set(key, []);
    byCluster.get(key).push(p);
  });
  const traces = [];
  byCluster.forEach((arr, name) => {
    traces.push({
      x: arr.map((x) => x.x),
      y: arr.map((x) => x.y),
      text: arr.map((x) => `${x.title}<br>${x.arcid}`),
      mode: "markers",
      type: "scattergl",
      name,
      hovertemplate: "%{text}<extra></extra>",
      marker: { size: 8, opacity: 0.85 },
    });
  });
  await Plotly.react(
    xpChartEl.value,
    traces,
    {
      margin: { l: 40, r: 220, t: 20, b: 60 },
      paper_bgcolor: "#ffffff",
      plot_bgcolor: "#ffffff",
      legend: { orientation: "v", x: 1.02, y: 1, xanchor: "left", yanchor: "top" },
      xaxis: { title: xpResult.value.meta?.x_axis_title || "PC1", automargin: true },
      yaxis: { title: xpResult.value.meta?.y_axis_title || "PC2", automargin: true, scaleanchor: "x", scaleratio: 1 },
    },
    { displayModeBar: false, responsive: true },
  );
}

async function renderDendrogram() {
  if (!dendroChartEl.value || !xpResult.value.dendrogram?.available) return;
  if (!Plotly) {
    const mod = await import("plotly.js-dist-min");
    Plotly = mod.default;
  }
  const fig = xpResult.value.dendrogram.figure;
  if (!fig?.data || !fig?.layout) return;
  await Plotly.react(dendroChartEl.value, fig.data, fig.layout, { displayModeBar: false, responsive: true });
}

async function loadXp() {
  const params = {
    ...xp.value,
    exclude_tags: xpExcludeTags.value.join(","),
    start_date: xpTimeMode.value === "range" ? xp.value.start_date : "",
    end_date: xpTimeMode.value === "range" ? xp.value.end_date : "",
    days: xpTimeMode.value === "window" ? xp.value.days : 30,
  };
  xpResult.value = await getXpMap(params);
  await nextTick();
  await renderXpChart();
  await renderDendrogram();
}

function addXpExcludeTag() {
  const v = String(newXpExcludeTag.value || "").trim().toLowerCase();
  if (!v) return;
  if (!xpExcludeTags.value.includes(v)) xpExcludeTags.value.push(v);
  newXpExcludeTag.value = "";
}

function removeXpExcludeTag(tag) {
  xpExcludeTags.value = xpExcludeTags.value.filter((x) => x !== tag);
}

let xpTimer = null;
function scheduleXpRefresh() {
  if (xpTimer) clearTimeout(xpTimer);
  xpTimer = setTimeout(() => {
    loadXp().catch(() => null);
  }, 500);
}

watch(lang, (next) => {
  lang.value = setLang(next);
});

watch(() => config.value.INGEST_API_BASE, () => {
  reloadIngestModels().catch(() => null);
});

watch(() => config.value.LLM_API_BASE, () => {
  reloadLlmModels().catch(() => null);
});

watch(homeTab, () => {
  const s = activeHomeState.value;
  if (!s.items?.length) {
    resetHomeFeed().catch(() => null);
  }
  nextTick().then(() => bindHomeInfiniteScroll());
});

watch(chatSessionId, () => {
  loadChatHistory().catch(() => null);
});

watch(filterTagInput, () => {
  loadTagSuggestions().catch(() => null);
});

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
watch(() => config.value.REC_STRICTNESS, () => {
  const v = Number(config.value.REC_STRICTNESS ?? 0.55);
  config.value.REC_STRICTNESS = Number((Number.isFinite(v) ? Math.max(0, Math.min(1, v)) : 0.55).toFixed(4));
});

watch(
  () => [
    config.value.DATA_UI_THEME_MODE,
    config.value.DATA_UI_THEME_PRESET,
    config.value.DATA_UI_THEME_OLED,
    config.value.DATA_UI_THEME_CUSTOM_PRIMARY,
    config.value.DATA_UI_THEME_CUSTOM_SECONDARY,
    config.value.DATA_UI_THEME_CUSTOM_ACCENT,
  ],
  () => applyTheme(),
  { deep: true, immediate: true },
);

watch(
  xp,
  (next) => {
    if (next.mode === "read_history" && next.time_basis !== "read_time") {
      xp.value.time_basis = "read_time";
    }
    if (xpTimeMode.value === "window") {
      xp.value.start_date = "";
      xp.value.end_date = "";
    }
    scheduleXpRefresh();
  },
  { deep: true },
);

watch(xpTimeMode, (mode) => {
  if (mode === "window") {
    xp.value.start_date = "";
    xp.value.end_date = "";
  }
  if (mode === "range") {
    xp.value.days = 30;
  }
  scheduleXpRefresh();
});

watch(xpExcludeTags, () => scheduleXpRefresh(), { deep: true });

watch(auditPage, () => {
  loadAudit().catch(() => null);
});

watch(logAutoStream, (enabled) => {
  if (enabled && !logTimer) {
    logTimer = setInterval(() => {
      pollLogTail().catch(() => null);
    }, 1200);
  }
  if (!enabled && logTimer) {
    clearInterval(logTimer);
    logTimer = null;
  }
});

onMounted(async () => {
  try {
    ensureChatSession();
    await Promise.all([
      loadDashboard(),
      loadConfigData(),
      loadScheduleData(),
      loadTasks(),
      loadAudit(),
      loadXp(),
      resetHomeFeed(),
      loadThumbCacheStats(),
      loadTranslationStatus(),
      loadModelStatus(),
      loadChatHistory(),
    ]);
    await setupTaskStream();
    await nextTick();
    bindHomeInfiniteScroll();
    if (typeof window !== "undefined" && window.matchMedia) {
      prefersDarkMedia = window.matchMedia("(prefers-color-scheme: dark)");
      prefersDarkListener = () => applyTheme();
      if (typeof prefersDarkMedia.addEventListener === "function") {
        prefersDarkMedia.addEventListener("change", prefersDarkListener);
      } else if (typeof prefersDarkMedia.addListener === "function") {
        prefersDarkMedia.addListener(prefersDarkListener);
      }
    }
    dashboardTimer = setInterval(loadDashboard, 10000);
    if (logAutoStream.value) {
      logTimer = setInterval(() => {
        pollLogTail().catch(() => null);
      }, 1200);
    }
  } catch (e) {
    notify(String(e), "error");
  }
});

onBeforeUnmount(() => {
  if (tasksEventSource) tasksEventSource.close();
  if (dashboardTimer) clearInterval(dashboardTimer);
  if (logTimer) clearInterval(logTimer);
  if (xpTimer) clearTimeout(xpTimer);
  if (siglipPollTimer) clearInterval(siglipPollTimer);
  if (touchPreviewTimer) clearTimeout(touchPreviewTimer);
  if (homeObserver) {
    homeObserver.disconnect();
    homeObserver = null;
  }
  if (prefersDarkMedia && prefersDarkListener) {
    if (typeof prefersDarkMedia.removeEventListener === "function") {
      prefersDarkMedia.removeEventListener("change", prefersDarkListener);
    } else if (typeof prefersDarkMedia.removeListener === "function") {
      prefersDarkMedia.removeListener(prefersDarkListener);
    }
  }
});

const MetricCard = defineComponent({
  props: { title: { type: String, required: true }, value: { type: [String, Number], required: true } },
  setup(props) {
    return () =>
      h("div", { class: "v-card metric-card pa-4 rounded-lg elevation-2" }, [
        h("div", { class: "text-caption text-medium-emphasis" }, props.title),
        h("div", { class: "text-h5 font-weight-bold mt-1" }, String(props.value)),
      ]);
  },
});

const ServiceChip = defineComponent({
  props: { title: { type: String, required: true }, ok: { type: [Boolean, null], default: null }, message: { type: String, default: "n/a" } },
  setup(props) {
    return () =>
      h("div", {},
        h(
          "div",
          { class: `v-chip v-chip--size-default ${props.ok === true ? "bg-success" : props.ok === false ? "bg-error" : "bg-grey-lighten-1"} text-white px-3 py-2` },
          `${props.title}: ${props.message || "n/a"}`,
        ));
  },
});
</script>

<style scoped>
.v-main {
  background:
    radial-gradient(circle at 8% 12%, rgba(0, 106, 106, 0.12), transparent 28%),
    radial-gradient(circle at 90% 8%, rgba(116, 91, 53, 0.1), transparent 25%),
    rgb(var(--v-theme-background));
}

:deep(.v-btn) {
  border-radius: 999px;
  text-transform: none;
  font-weight: 600;
}

:deep(.v-field) {
  border-radius: 14px;
}

.mono {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
}

.drawer-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 72px;
}

.brand-logo {
  width: 26px;
  height: 26px;
  border-radius: 6px;
}

.brand-title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.2px;
  white-space: nowrap;
}

.home-search-input {
  flex: 1;
  min-width: 220px;
}

.home-card {
  overflow: hidden;
  border: 1px solid rgba(110, 118, 129, 0.25);
}

.cover-anchor {
  display: block;
  text-decoration: none;
  color: inherit;
  position: relative;
}

.cover-ph {
  height: 190px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 18% 20%, rgba(56, 189, 248, 0.18), transparent 42%),
    radial-gradient(circle at 82% 80%, rgba(74, 222, 128, 0.18), transparent 46%),
    rgba(15, 23, 42, 0.78);
}

.cover-bg-blur {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  filter: blur(14px);
  transform: scale(1.08);
  opacity: 0.9;
}

.cover-img {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.home-card.compact .cover-ph {
  height: 220px;
}

.cat-badge {
  position: absolute;
  right: 6px;
  bottom: 6px;
  z-index: 2;
  color: #ffffff;
  font-size: 10px;
  line-height: 1;
  font-weight: 600;
  padding: 4px 6px;
  border-radius: 10px;
  text-transform: none;
  letter-spacing: 0.1px;
}

.cover-title-overlay {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 3;
  padding: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #ffffff;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.78), rgba(0, 0, 0, 0.12));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.list-cover {
  width: 42px;
  height: 56px;
  border-radius: 8px;
  margin-right: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(30, 41, 59, 0.85);
  overflow: hidden;
  position: relative;
}

.list-blur {
  filter: blur(10px);
}

.list-cover-img {
  position: relative;
  z-index: 1;
}

.hover-preview-card {
  border: 1px solid rgba(110, 118, 129, 0.25);
  width: min(460px, 92vw);
}

.hover-cover-wrap {
  width: 100%;
  max-height: min(60vh, 520px);
  border-radius: 8px;
  overflow: auto;
  background: rgba(15, 23, 42, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
}

.hover-cover {
  max-width: 100%;
  max-height: min(58vh, 500px);
  width: auto;
  height: auto;
  object-fit: contain;
  display: block;
}

.hover-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
}

.hover-tag {
  max-width: 100%;
  height: auto;
  min-height: 22px;
}

.hover-tag.active {
  border-color: rgba(var(--v-theme-primary), 0.9);
  background: rgba(var(--v-theme-primary), 0.18);
}

.hover-tag :deep(.v-chip__content) {
  white-space: normal;
  overflow: visible;
  text-overflow: clip;
  line-height: 1.25;
}

:deep(.mobile-preview-dialog) {
  width: min(92vw, 560px);
}

.home-sentinel {
  height: 2px;
}

.chat-sidebar {
  min-height: 560px;
  border: 1px solid rgba(110, 118, 129, 0.25);
}

.chat-main {
  min-height: 560px;
  border: 1px solid rgba(110, 118, 129, 0.25);
  display: flex;
  flex-direction: column;
}

.chat-log {
  flex: 1;
  min-height: 420px;
  max-height: 58vh;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 4px;
}

.chat-bubble {
  max-width: 80%;
  border-radius: 10px;
  padding: 8px 10px;
}

.chat-bubble.user {
  align-self: flex-end;
  background: rgba(var(--v-theme-primary), 0.15);
}

.chat-bubble.assistant {
  align-self: flex-start;
  background: rgba(110, 118, 129, 0.16);
}

.chat-bubble.mini {
  max-width: 100%;
  padding: 6px 8px;
}

.chat-fab-wrap {
  position: fixed;
  right: 22px;
  bottom: 22px;
  z-index: 40;
}

.chat-fab-panel {
  position: absolute;
  right: 0;
  bottom: 56px;
  width: min(360px, 88vw);
  border: 1px solid rgba(110, 118, 129, 0.25);
}

.chat-fab-log {
  max-height: 240px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.upload-dropzone {
  border: 1px dashed rgba(110, 118, 129, 0.55);
  border-radius: 10px;
  min-height: 160px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  background: rgba(30, 41, 59, 0.25);
}

.upload-dropzone.active {
  border-color: rgba(var(--v-theme-primary), 0.8);
  background: rgba(var(--v-theme-primary), 0.08);
}

.model-log-view {
  max-height: 140px;
  overflow: auto;
  white-space: pre-wrap;
  border: 1px solid rgba(110, 118, 129, 0.3);
  border-radius: 8px;
  padding: 8px;
  font-size: 12px;
}

.metric-card {
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgba(110, 118, 129, 0.22);
}

.audit-row {
  cursor: pointer;
}

.audit-row.selected {
  background: rgba(var(--v-theme-primary), 0.12);
}

.log-view {
  border: 1px solid #cfd8dc;
  border-radius: 8px;
  min-height: 520px;
  max-height: 520px;
  overflow: auto;
  background: #10131a;
  color: #e7edf3;
  padding: 12px;
  line-height: 1.4;
  font-size: 12px;
}

.log-view :deep(mark) {
  background: #ffd54f;
  color: #2d2d2d;
  padding: 0 2px;
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}

.category-btn {
  font-weight: 700;
  min-height: 52px;
  border-radius: 10px;
  text-transform: none;
}

.dendro-wrap {
  overflow-x: auto;
}
</style>
