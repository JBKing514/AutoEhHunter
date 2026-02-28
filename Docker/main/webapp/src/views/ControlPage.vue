<template>
          <v-row class="mb-4">
            <v-col cols="12" md="4"><metric-card :title="t('dashboard.metric.works')" :value="health.database?.works ?? 0" /></v-col>
            <v-col cols="12" md="4"><metric-card :title="t('dashboard.metric.eh_works')" :value="health.database?.eh_works ?? 0" /></v-col>
            <v-col cols="12" md="4"><metric-card :title="t('dashboard.metric.last_fetch')" :value="formatDateMinute(health.database?.last_fetch)" /></v-col>
          </v-row>
          <v-alert v-if="health.database?.error" type="warning" class="mb-4">{{ t('dashboard.db_warning', { reason: health.database.error }) }}</v-alert>
          <v-card class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('control.manual') }}</div>
            <v-row class="manual-task-row" align="stretch">
              <v-col cols="12" sm="6" md="4" lg="3" xl="2"><v-btn block class="manual-task-btn" color="primary" @click="triggerTask('eh_fetch')">{{ t('control.btn.eh_fetch') }}</v-btn></v-col>
              <v-col cols="12" sm="6" md="4" lg="3" xl="2"><v-btn block class="manual-task-btn" color="warning" variant="tonal" @click="clearEhCheckpointNow">{{ t('control.btn.clear_eh_checkpoint') }}</v-btn></v-col>
              <v-col cols="12" sm="6" md="4" lg="3" xl="2"><v-btn block class="manual-task-btn" color="primary" @click="triggerTask('lrr_sync_manual')">{{ t('control.btn.lrr_sync_manual') }}</v-btn></v-col>
              <v-col cols="12" sm="6" md="4" lg="3" xl="2"><v-btn block class="manual-task-btn" color="secondary" @click="triggerTask('eh_lrr_ingest')">{{ t('control.btn.eh_lrr_ingest') }}</v-btn></v-col>
              <v-col cols="12" sm="6" md="4" lg="3" xl="2"><v-btn block class="manual-task-btn" color="secondary" @click="triggerTask('eh_ingest')">{{ t('control.btn.eh_ingest') }}</v-btn></v-col>
              <v-col cols="12" sm="6" md="4" lg="3" xl="2"><v-btn block class="manual-task-btn" color="warning" variant="tonal" @click="triggerTask('eh_ingest', '--retry-fail-embedding')">{{ t('control.btn.eh_ingest_retry_fail') }}</v-btn></v-col>
              <v-col cols="12" sm="6" md="4" lg="3" xl="2"><v-btn block class="manual-task-btn" color="secondary" @click="triggerTask('lrr_ingest')">{{ t('control.btn.lrr_ingest') }}</v-btn></v-col>
              <v-col cols="12" sm="6" md="4" lg="3" xl="2"><v-btn block class="manual-task-btn" color="warning" variant="tonal" @click="triggerTask('lrr_ingest', '--retry-fail-embedding')">{{ t('control.btn.lrr_ingest_retry_fail') }}</v-btn></v-col>
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
              <v-col cols="12" md="3"><v-switch v-model="item.enabled" color="primary" hide-details inset/></v-col>
              <v-col cols="12" md="5"><v-text-field v-model="item.cron" :label="`Cron (${schedulerLabel(key)})`" hide-details variant="outlined" density="comfortable" color="primary"/></v-col>
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
</template>

<script>
import { onBeforeUnmount, onMounted } from "vue";
import { useControlStore } from "../stores/controlStore";

export default {
  setup() {
    const store = useControlStore();
    onMounted(() => {
      store.startControlPolling().catch(() => null);
    });
    onBeforeUnmount(() => {
      store.stopControlPolling();
    });
    return store;
  },
};
</script>

<style scoped>
.manual-task-btn {
  min-height: 52px;
}

.manual-task-btn :deep(.v-btn__content) {
  white-space: normal;
  text-align: center;
  line-height: 1.25;
}
</style>
