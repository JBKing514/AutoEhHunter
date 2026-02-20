<template>
  <v-app>
    <v-navigation-drawer v-model="drawer" :rail="rail" permanent border>
      <v-list-item class="py-4" :title="t('app.title')" prepend-icon="mdi-view-dashboard-outline" />
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
      <v-select
        v-model="colorPreset"
        :items="themeOptions"
        item-title="title"
        item-value="value"
        hide-details
        density="compact"
        variant="outlined"
        style="max-width: 140px"
      />
      <v-select v-model="lang" :items="['zh', 'en']" hide-details density="compact" variant="outlined" style="max-width: 120px" />
      <v-btn icon variant="text" @click="darkMode = !darkMode">
        <v-icon>{{ darkMode ? 'mdi-weather-night' : 'mdi-white-balance-sunny' }}</v-icon>
      </v-btn>
    </v-app-bar>

    <v-main>
      <v-container fluid class="pa-6">
        <section v-show="tab === 'dashboard'">
          <v-row>
            <v-col cols="12" md="4"><metric-card :title="t('dashboard.metric.works')" :value="health.database?.works ?? 0" /></v-col>
            <v-col cols="12" md="4"><metric-card :title="t('dashboard.metric.eh_works')" :value="health.database?.eh_works ?? 0" /></v-col>
            <v-col cols="12" md="4"><metric-card :title="t('dashboard.metric.last_fetch')" :value="health.database?.last_fetch ?? '-'" /></v-col>
          </v-row>
          <v-alert v-if="health.database?.error" type="warning" class="mb-4">{{ t('dashboard.db_warning', { reason: health.database.error }) }}</v-alert>
          <v-card class="pa-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('dashboard.health') }}</div>
            <v-row>
              <v-col cols="12" md="4"><service-chip :title="t('health.lrr')" :ok="health.services?.lrr?.ok" :message="health.services?.lrr?.message" /></v-col>
              <v-col cols="12" md="4"><service-chip :title="t('health.compute')" :ok="health.services?.compute?.ok" :message="health.services?.compute?.message" /></v-col>
              <v-col cols="12" md="4"><service-chip :title="t('health.llm')" :ok="health.services?.llm?.ok" :message="health.services?.llm?.message" /></v-col>
            </v-row>
          </v-card>
        </section>

        <section v-show="tab === 'control'">
          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('control.manual') }}</div>
            <v-row>
              <v-col cols="12" md="4" lg="2"><v-btn block color="primary" @click="triggerTask('eh_fetch')">{{ t('control.btn.eh_fetch') }}</v-btn></v-col>
              <v-col cols="12" md="4" lg="2"><v-btn block color="primary" @click="triggerTask('lrr_export')">{{ t('control.btn.lrr_export') }}</v-btn></v-col>
              <v-col cols="12" md="4" lg="2"><v-btn block color="primary" @click="triggerTask('text_ingest')">{{ t('control.btn.text_ingest') }}</v-btn></v-col>
              <v-col cols="12" md="4" lg="2"><v-btn block color="secondary" @click="triggerTask('compute_daily')">{{ t('control.btn.compute_daily') }}</v-btn></v-col>
              <v-col cols="12" md="4" lg="2"><v-btn block color="secondary" @click="triggerTask('compute_eh_ingest')">{{ t('control.btn.compute_eh_ingest') }}</v-btn></v-col>
              <v-col cols="12" md="4" lg="2"><v-btn block color="secondary" @click="triggerTask('compute_worker', workerArgs)">{{ t('control.btn.compute_worker') }}</v-btn></v-col>
            </v-row>
            <v-text-field v-model="workerArgs" class="mt-3" :label="t('control.worker.args')" :hint="t('control.worker.args.help')" persistent-hint />
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
                  <td>{{ task.started_at || '-' }}</td>
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
                  <v-col cols="12" md="6"><v-text-field v-model.number="auditFilter.limit" type="number" min="50" max="2000" label="Limit" /></v-col>
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
                    <tr v-for="row in auditRows" :key="row.task_id + row.ts"><td>{{ row.ts }}</td><td>{{ row.task }}</td><td>{{ row.status }}</td><td>{{ row.rc }}</td></tr>
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
                <v-select v-model="selectedLog" :items="auditLogs" :label="t('audit.select_log')" @update:model-value="loadLog" />
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
          </v-card>

          <v-card class="pa-4 mb-4">
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

          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.urls') }}</div>
            <v-row>
              <v-col cols="12" md="6"><v-text-field v-model="config.LRR_BASE" :label="labelFor('LRR_BASE')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.COMPUTE_HEALTH_URL" :label="labelFor('COMPUTE_HEALTH_URL')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.OPENAI_HEALTH_URL" :label="labelFor('OPENAI_HEALTH_URL')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.EH_BASE_URL" :label="labelFor('EH_BASE_URL')" /></v-col>
            </v-row>
          </v-card>

          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.secrets') }}</div>
            <v-row>
              <v-col cols="12" md="6"><v-text-field v-model="config.LRR_API_KEY" :label="labelFor('LRR_API_KEY')" type="password" :placeholder="t('settings.secret.keep')" :hint="secretHint('LRR_API_KEY')" persistent-hint /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.OPENAI_API_KEY" :label="labelFor('OPENAI_API_KEY')" type="password" :placeholder="t('settings.secret.keep')" :hint="secretHint('OPENAI_API_KEY')" persistent-hint /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.LLM_API_KEY" :label="labelFor('LLM_API_KEY')" type="password" :placeholder="t('settings.secret.keep')" :hint="secretHint('LLM_API_KEY')" persistent-hint /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.EMB_API_KEY" :label="labelFor('EMB_API_KEY')" type="password" :placeholder="t('settings.secret.keep')" :hint="secretHint('EMB_API_KEY')" persistent-hint /></v-col>
            </v-row>
          </v-card>

          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.eh.cookie') }} <v-chip size="small" class="ml-2" variant="tonal">{{ secretHint('EH_COOKIE') }}</v-chip></div>
            <v-row>
              <v-col cols="12" md="6"><v-text-field v-model="cookieParts.ipb_member_id" label="ipb_member_id" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="cookieParts.ipb_pass_hash" label="ipb_pass_hash" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="cookieParts.sk" label="sk" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="cookieParts.igneous" label="igneous" /></v-col>
            </v-row>
          </v-card>

          <v-card class="pa-4 mb-4">
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

          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.eh.filter_tag') }}</div>
            <div class="d-flex ga-2 align-center mb-3">
              <v-text-field v-model="newEhTag" :label="t('settings.eh.filter_tag')" @keyup.enter="addEhTag" />
              <v-btn color="primary" @click="addEhTag">Add</v-btn>
            </div>
            <div class="d-flex flex-wrap ga-2">
              <v-chip v-for="tag in ehFilterTags" :key="tag" closable @click:close="removeEhTag(tag)">{{ tag }}</v-chip>
            </div>
          </v-card>

          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.data_node') }}</div>
            <v-row>
              <v-col cols="12" md="4"><v-switch v-model="config.TEXT_INGEST_PRUNE_NOT_SEEN" :label="labelFor('TEXT_INGEST_PRUNE_NOT_SEEN')" /></v-col>
              <v-col cols="12" md="4"><v-switch v-model="config.WORKER_ONLY_MISSING" :label="labelFor('WORKER_ONLY_MISSING')" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.LRR_READS_HOURS" :label="labelFor('LRR_READS_HOURS')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_FETCH_MAX_PAGES" :label="labelFor('EH_FETCH_MAX_PAGES')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_REQUEST_SLEEP" :label="labelFor('EH_REQUEST_SLEEP')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_SAMPLING_DENSITY" :label="labelFor('EH_SAMPLING_DENSITY')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_USER_AGENT" :label="labelFor('EH_USER_AGENT')" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_MIN_RATING" :label="labelFor('EH_MIN_RATING')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.TEXT_INGEST_BATCH_SIZE" :label="labelFor('TEXT_INGEST_BATCH_SIZE')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_QUEUE_LIMIT" :label="labelFor('EH_QUEUE_LIMIT')" type="number" /></v-col>
            </v-row>
          </v-card>

          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.compute_node') }}</div>
            <v-row>
              <v-col cols="12" md="6"><v-text-field v-model="config.COMPUTE_CONTAINER_NAME" :label="labelFor('COMPUTE_CONTAINER_NAME')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.LLM_API_BASE" :label="labelFor('LLM_API_BASE')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.LLM_MODEL" :label="labelFor('LLM_MODEL')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.EMB_API_BASE" :label="labelFor('EMB_API_BASE')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.EMB_MODEL" :label="labelFor('EMB_MODEL')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.VL_BASE" :label="labelFor('VL_BASE')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.EMB_BASE" :label="labelFor('EMB_BASE')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.VL_MODEL_ID" :label="labelFor('VL_MODEL_ID')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.EMB_MODEL_ID" :label="labelFor('EMB_MODEL_ID')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.SIGLIP_MODEL" :label="labelFor('SIGLIP_MODEL')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.SIGLIP_DEVICE" :label="labelFor('SIGLIP_DEVICE')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.WORKER_BATCH" :label="labelFor('WORKER_BATCH')" type="number" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.WORKER_SLEEP" :label="labelFor('WORKER_SLEEP')" type="number" /></v-col>
            </v-row>
          </v-card>

          <v-btn color="primary" size="large" @click="saveConfig">{{ t('settings.save') }}</v-btn>
        </section>
      </v-container>
    </v-main>

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
  getSchedule,
  getTasks,
  getXpMap,
  runTask,
  updateConfig,
  updateSchedule,
} from "./api";
import { getInitialLang, setLang, t as tr } from "./i18n";

const drawer = ref(true);
const rail = ref(false);
const tab = ref("dashboard");
const lang = ref(getInitialLang());
const theme = useTheme();
const darkMode = ref(false);
const colorPreset = ref("modern");
const themeOptions = [
  { title: "Modern", value: "modern" },
  { title: "Ocean", value: "ocean" },
  { title: "Sunset", value: "sunset" },
];

const health = ref({ database: {}, services: {} });
const schedule = ref({});
const tasks = ref([]);
const config = ref({});
const schema = ref({});
const configMeta = ref({});
const secretState = ref({});

const workerArgs = ref("--limit 20 --only-missing");
const auditRows = ref([]);
const auditLogs = ref([]);
const taskOptions = ref([]);
const selectedLog = ref("");
const selectedLogContent = ref("");
const logOffset = ref(0);
const logAutoStream = ref(true);
const logHighlight = ref("");
const auditFilter = ref({ task: "", status: "", keyword: "", start_date: "", end_date: "", limit: 300, offset: 0 });
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
const ehCategoryAllowMap = ref(Object.fromEntries(ehCategoryDefs.map((x) => [x.key, true])));

let tasksEventSource = null;
let dashboardTimer = null;
let logTimer = null;
let Plotly = null;

const toast = ref({ show: false, text: "", color: "success" });

const navItems = [
  { key: "dashboard", title: "tab.dashboard", icon: "mdi-view-dashboard-outline" },
  { key: "control", title: "tab.control", icon: "mdi-console" },
  { key: "audit", title: "tab.audit", icon: "mdi-clipboard-text-clock-outline" },
  { key: "xp", title: "tab.xp_map", icon: "mdi-chart-bubble" },
  { key: "settings", title: "tab.settings", icon: "mdi-cog-outline" },
];

const currentTitleKey = computed(() => navItems.find((x) => x.key === tab.value)?.title || "tab.dashboard");
const auditPages = computed(() => {
  const per = Math.max(1, Number(auditFilter.value.limit || 300));
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

function t(key, vars = {}) {
  return tr(lang.value, key, vars);
}

function notify(text, color = "success") {
  toast.value = { show: true, text, color };
}

function applyTheme() {
  const mode = darkMode.value ? "Dark" : "Light";
  const name = `${colorPreset.value}${mode}`;
  theme.global.name.value = name;
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
    COMPUTE_HEALTH_URL: "settings.compute.health",
    OPENAI_HEALTH_URL: "settings.openai.health",
    LRR_API_KEY: "settings.lrr.api_key",
    OPENAI_API_KEY: "settings.openai.api_key",
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
    COMPUTE_CONTAINER_NAME: "settings.compute.container",
    LLM_API_BASE: "settings.compute.llm_api_base",
    LLM_API_KEY: "settings.compute.llm_api_key",
    LLM_MODEL: "settings.compute.llm_model",
    EMB_API_BASE: "settings.compute.emb_api_base",
    EMB_API_KEY: "settings.compute.emb_api_key",
    EMB_MODEL: "settings.compute.emb_model",
    VL_BASE: "settings.compute.vl_base",
    EMB_BASE: "settings.compute.emb_base",
    VL_MODEL_ID: "settings.compute.vl_model_id",
    EMB_MODEL_ID: "settings.compute.emb_model_id",
    SIGLIP_MODEL: "settings.compute.siglip_model",
    SIGLIP_DEVICE: "settings.compute.siglip_device",
    WORKER_BATCH: "settings.compute.worker_batch",
    WORKER_SLEEP: "settings.compute.worker_sleep",
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
  const limit = Math.max(1, Number(auditFilter.value.limit || 300));
  const offset = (page - 1) * limit;
  const history = await getAuditHistory({ ...auditFilter.value, limit, offset });
  auditRows.value = history.rows || [];
  auditTotal.value = Number(history.total || 0);
  const logs = await getAuditLogs();
  auditLogs.value = logs.logs || [];
  const tasksRes = await getAuditTasks();
  taskOptions.value = tasksRes.tasks || [];
  if (!selectedLog.value && auditLogs.value.length) {
    selectedLog.value = auditLogs.value[0];
    await loadLog();
  }
}

function resetAuditFilter() {
  auditFilter.value = { task: "", status: "", keyword: "", start_date: "", end_date: "", limit: 300, offset: 0 };
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

async function loadLog() {
  if (!selectedLog.value) return;
  const data = await getAuditLogContent(selectedLog.value);
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

watch([darkMode, colorPreset], () => applyTheme(), { immediate: true });

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
    await Promise.all([loadDashboard(), loadConfigData(), loadScheduleData(), loadTasks(), loadAudit(), loadXp()]);
    await setupTaskStream();
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
});

const MetricCard = defineComponent({
  props: { title: { type: String, required: true }, value: { type: [String, Number], required: true } },
  setup(props) {
    return () =>
      h("div", { class: "v-card pa-4 rounded-lg elevation-1" }, [
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
