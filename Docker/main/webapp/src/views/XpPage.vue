<template>
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
</template>

<script>
import { onBeforeUnmount, onMounted } from "vue";
import { useXpStore } from "../stores/xpStore";

export default {
  setup() {
    const store = useXpStore();
    onMounted(() => {
      store.loadXp().catch(() => null);
    });
    onBeforeUnmount(() => {
      store.clearXpTimer();
    });
    return store;
  },
};
</script>
