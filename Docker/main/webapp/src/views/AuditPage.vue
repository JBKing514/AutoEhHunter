<template>
          <v-row>
            <v-col cols="12" md="5">
              <v-card class="pa-4 mb-3">
                <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('audit.filters') }}</div>
                <v-row>
                  <v-col cols="12" md="6"><v-select v-model="auditFilter.task" :items="taskOptions" :label="t('audit.filter.task')" clearable variant="outlined" density="compact" color="primary" hide-details/></v-col>
                  <v-col cols="12" md="6"><v-select v-model="auditFilter.status" :label="t('audit.filter.status')" :items="['', 'success', 'failed', 'timeout']" variant="outlined" density="compact" color="primary" hide-details/></v-col>
                  <v-col cols="12"><v-text-field v-model="auditFilter.keyword" :label="t('audit.filter.keyword')" variant="outlined" density="compact" color="primary"/></v-col>
                  <v-col cols="12" md="6"><v-text-field v-model="auditFilter.start_date" type="date" :label="t('audit.filter.start_date')" variant="outlined" density="compact" color="primary"/></v-col>
                  <v-col cols="12" md="6"><v-text-field v-model="auditFilter.end_date" type="date" :label="t('audit.filter.end_date')" variant="outlined" density="compact" color="primary"/></v-col>
                  <v-col cols="12" md="6"><v-text-field v-model.number="auditFilter.limit" type="number" min="5" max="500" label="Limit" variant="outlined" density="compact" color="primary"/></v-col>
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
                  <div class="d-flex ga-2 align-center">
                    <v-btn size="small" color="warning" variant="outlined" @click="clearAuditLogsNow">{{ t('audit.log.clear') }}</v-btn>
                    <v-switch v-model="logAutoStream" color="primary" hide-details :label="t('audit.log.live')" inset />
                  </div>
                </div>
                <div class="text-caption text-medium-emphasis mb-2">{{ selectedLog || '-' }}</div>
                <v-text-field v-model="logHighlight" class="mt-2" :label="t('audit.log.highlight')" variant="outlined" density="compact" color="primary"/>
                <div class="log-view mono mt-2" v-html="highlightedLogHtml" />
              </v-card>
            </v-col>
          </v-row>
</template>

<script>
import { onBeforeUnmount, onMounted } from "vue";
import { useAuditStore } from "../stores/auditStore";

export default {
  setup() {
    const store = useAuditStore();
    onMounted(() => {
      store.loadAudit().catch(() => null);
      store.startLogTailPolling();
    });
    onBeforeUnmount(() => {
      store.stopLogTailPolling();
    });
    return store;
  },
};
</script>
