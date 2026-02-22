<template>
<v-card  class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('dashboard.health') }}</div>
            <v-row>
              <v-col cols="12" md="6"><service-chip :title="t('health.lrr')" :ok="health?.services?.lrr?.ok" :message="health?.services?.lrr?.message" /></v-col>
              <v-col cols="12" md="6"><service-chip :title="t('health.llm')" :ok="health?.services?.llm?.ok" :message="health?.services?.llm?.message" /></v-col>
            </v-row>
          </v-card>

<v-card  class="pa-4 mb-4">
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

<v-card  class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.urls') }}</div>
            <v-row>
              <v-col cols="12" md="6"><v-text-field v-model="config.LRR_BASE" :label="labelFor('LRR_BASE')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.OPENAI_HEALTH_URL" :label="labelFor('OPENAI_HEALTH_URL')" /></v-col>
            </v-row>
          </v-card>

<v-card  class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.secrets') }}</div>
            <v-row>
              <v-col cols="12" md="6"><v-text-field v-model="config.LRR_API_KEY" :label="labelFor('LRR_API_KEY')" type="password" :placeholder="t('settings.secret.keep')" :hint="secretHint('LRR_API_KEY')" persistent-hint /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.INGEST_API_KEY" :label="labelFor('INGEST_API_KEY')" type="password" :placeholder="t('settings.secret.keep')" :hint="secretHint('INGEST_API_KEY')" persistent-hint /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.LLM_API_KEY" :label="labelFor('LLM_API_KEY')" type="password" :placeholder="t('settings.secret.keep')" :hint="secretHint('LLM_API_KEY')" persistent-hint /></v-col>
            </v-row>
          </v-card>

<v-card  class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.account') }}</div>
            <v-row>
              <v-col cols="12" md="6"><v-text-field v-model="accountForm.username" :label="t('auth.username')" /></v-col>
              <v-col cols="12" md="6" class="d-flex align-center"><v-btn color="primary" variant="outlined" @click="updateAccountUsername">{{ t('auth.profile.update_username') }}</v-btn></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="accountForm.oldPassword" :label="t('auth.profile.old_password')" type="password" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="accountForm.newPassword" :label="t('auth.profile.new_password')" type="password" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="accountForm.newPassword2" :label="t('auth.profile.new_password_confirm')" type="password" /></v-col>
              <v-col cols="12" md="6" class="d-flex align-center"><v-btn color="warning" variant="outlined" @click="updateAccountPassword">{{ t('auth.profile.change_password') }}</v-btn></v-col>
              <v-col cols="12" md="6" class="d-flex align-center justify-end">
                <v-btn color="error" variant="tonal" @click="deleteAccountNow">{{ t('auth.profile.delete_account') }}</v-btn>
              </v-col>
            </v-row>
          </v-card>

<v-card  class="pa-4 mb-4">
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

<v-card  class="pa-4 mb-4">
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
</template>

<script>
import { useSettingsStore } from "../../stores/settingsStore";

export default {
  setup() {
    return useSettingsStore();
  },
};
</script>
