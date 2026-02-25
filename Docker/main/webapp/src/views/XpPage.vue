<template>
          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('xp.title') }}</div>
            <v-row>
              <v-col cols="12" md="2"><v-select v-model="xp.mode" :items="[{title:t('xp.mode.read_history'),value:'read_history'},{title:t('xp.mode.inventory'),value:'inventory'}]" item-title="title" item-value="value" :label="t('xp.mode')" variant="outlined" density="compact" color="primary" hide-details /></v-col>
              <v-col cols="12" md="2"><v-select v-model="xp.time_basis" :disabled="xp.mode === 'read_history'" :items="[{title:t('xp.time_basis.read_time'),value:'read_time'},{title:t('xp.time_basis.eh_posted'),value:'eh_posted'},{title:t('xp.time_basis.date_added'),value:'date_added'}]" item-title="title" item-value="value" :label="t('xp.time_basis')" variant="outlined" density="compact" color="primary" hide-details/></v-col>
              <v-col cols="12" md="2">
                <v-select v-model="xpTimeMode" :items="[{title:t('xp.time.mode.window'),value:'window'},{title:t('xp.time.mode.range'),value:'range'}]" item-title="title" item-value="value" :label="t('xp.time.mode')" variant="outlined" density="compact" color="primary" hide-details/>
              </v-col>
              <v-col v-if="xpTimeMode === 'window'" cols="12" md="2"><v-text-field v-model.number="xp.days" type="number" :label="t('xp.days')" variant="outlined" density="compact" color="primary"/></v-col>
              <v-col v-else cols="12" md="2"><v-text-field v-model="xp.start_date" type="date" :label="t('xp.filter.start_date')" variant="outlined" density="compact" color="primary" /></v-col>
              <v-col v-if="xpTimeMode === 'range'" cols="12" md="2"><v-text-field v-model="xp.end_date" type="date" :label="t('xp.filter.end_date')" variant="outlined" density="compact" color="primary"/></v-col>
              <v-col cols="12" md="2"><v-text-field v-model.number="xp.max_points" type="number" :label="t('xp.max_points')" variant="outlined" density="compact" color="primary"/></v-col>
              <v-col cols="12" md="2"><v-text-field v-model.number="xp.k" type="number" :label="t('xp.k')" variant="outlined" density="compact" color="primary"/></v-col>
              <v-col cols="12" md="2" class="d-flex align-center text-medium-emphasis">{{ t('xp.auto_refresh') }}</v-col>
            </v-row>
            <v-row>
              <v-col cols="12" md="3"><v-switch v-model="xp.exclude_language_tags" :label="t('xp.exclude.language')" hide-details inset/></v-col>
              <v-col cols="12" md="3"><v-switch v-model="xp.exclude_other_tags" :label="t('xp.exclude.other')" hide-details inset/></v-col>
              <v-col cols="12" md="3"><v-text-field v-model.number="xp.topn" type="number" :label="t('xp.cluster_topn')" variant="outlined" density="compact" color="primary"/></v-col>
              <v-col cols="12" md="3" class="d-flex align-center justify-end"><v-btn variant="tonal" @click="resetXpConfig">{{ t('audit.filter.reset') }}</v-btn></v-col>
            </v-row>
            <v-autocomplete
              v-model="xpExcludeTags"
              v-model:search="newXpExcludeTag"
              :items="xpExcludeTagSuggestions"
              multiple
              chips
              closable-chips
              clearable
              variant="outlined"
              density="compact"
              color="primary"
              :label="t('xp.filter.exclude_tags')"
            />
          </v-card>

          <v-card class="pa-4 mb-4">
            <div class="d-flex align-center justify-space-between mb-3 flex-wrap ga-2">
              <div class="text-subtitle-1 font-weight-medium">{{ t('xp.chart_title') }}</div>
              <v-btn-toggle
                v-model="xpChartMode"
                density="compact"
                variant="outlined"
                color="primary"
                mandatory
                @update:model-value="toggleXpChartMode"
              >
                <v-btn value="3d" size="small">3D</v-btn>
                <v-btn value="2d" size="small">2D</v-btn>
              </v-btn-toggle>
            </div>
            <div class="xp-chart-scroll">
              <div ref="xpChartEl" class="xp-chart-canvas" />
            </div>
          </v-card>

          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('xp.dendrogram.title') }}</div>
            <div class="d-flex align-center ga-4 mb-2 flex-wrap" v-if="xpResult.dendrogram?.available">
              <v-pagination v-model="xp.dendro_page" :length="xpResult.dendrogram?.pages || 1" :total-visible="6" />
              <v-select v-model.number="xp.dendro_page_size" :items="[40,60,80,100,150,200]" label="Page size" class="xp-page-size" variant="outlined" density="compact" color="primary" hide-details/>
            </div>
            <div v-if="xpResult.dendrogram?.available" class="dendro-wrap xp-chart-scroll">
              <div ref="dendroChartEl" class="dendro-chart-canvas" />
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

<style scoped>
.xp-chart-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  touch-action: pan-x pan-y;
}

.xp-chart-canvas {
  width: 100%;
  height: 520px;
}

.dendro-chart-canvas {
  width: 100%;
  height: 800px;
}

.xp-page-size {
  max-width: 160px;
}

@media (max-width: 960px) {
  .xp-chart-canvas {
    min-width: 720px;
    height: 460px;
  }

  .dendro-chart-canvas {
    min-width: 920px;
    height: 680px;
  }

  .xp-page-size {
    max-width: 100%;
    min-width: 140px;
  }
}
</style>
