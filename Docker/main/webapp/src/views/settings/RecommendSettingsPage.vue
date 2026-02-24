<template>
  <v-card class="pa-4 mb-4">
    <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.recommend') }}</div>
    <v-alert type="info" variant="tonal" class="mb-3">
      {{ t('settings.recommend.tuning_hint') }}
      <template #append>
        <v-btn size="small" variant="outlined" @click="resetRecommendPreset">{{ t('settings.recommend.reset') }}</v-btn>
      </template>
    </v-alert>
    <v-row>
      <v-col cols="12" md="4"><v-text-field v-model="config.LRR_READS_HOURS" :label="t('settings.lrr.reads_hours')" type="number" variant="outlined" density="compact" color="primary" /></v-col>
      <v-col cols="12" md="4"><v-text-field v-model="config.REC_PROFILE_DAYS" :label="t('settings.rec.profile_days')" type="number" variant="outlined" density="compact" color="primary" /></v-col>
      <v-col cols="12" md="4"><v-text-field v-model="config.REC_CANDIDATE_HOURS" :label="t('settings.rec.candidate_hours')" type="number" variant="outlined" density="compact" color="primary" /></v-col>
      <v-col cols="12" md="4"><v-text-field v-model="config.REC_CANDIDATE_LIMIT" :label="t('settings.rec.candidate_limit')" type="number" variant="outlined" density="compact" color="primary" /></v-col>
      <v-col cols="12" md="4"><v-text-field v-model="config.REC_CLUSTER_K" :label="t('settings.rec.cluster_k')" type="number" variant="outlined" density="compact" color="primary" /></v-col>
      <v-col cols="12" md="4"><v-text-field v-model="config.REC_CLUSTER_CACHE_TTL_S" :label="t('settings.rec.cache_ttl')" type="number" variant="outlined" density="compact" color="primary" /></v-col>

      <v-col cols="12"><v-divider class="my-2" /></v-col>

      <v-col cols="12" md="4"><v-slider v-model="config.REC_STRICTNESS" min="0" max="1" step="0.01" :label="t('settings.rec.strictness')" color="primary" density="compact" hide-details thumb-label /></v-col>
      <v-col cols="12" md="4"><v-slider v-model="config.REC_TAG_WEIGHT" min="0" max="1" step="0.01" :label="t('settings.rec.tag_weight')" color="primary" density="compact" hide-details thumb-label /></v-col>
      <v-col cols="12" md="4"><v-slider v-model="config.REC_VISUAL_WEIGHT" min="0" max="1" step="0.01" :label="t('settings.rec.visual_weight')" color="primary" density="compact" hide-details thumb-label /></v-col>
      <v-col cols="12" md="4"><v-slider v-model="config.REC_FEEDBACK_WEIGHT" min="0" max="1" step="0.01" :label="t('settings.rec.feedback_weight')" color="primary" density="compact" hide-details thumb-label /></v-col>
      <v-col cols="12" md="4"><v-text-field v-model="config.REC_TAG_FLOOR_SCORE" :label="t('settings.rec.tag_floor')" type="number" step="0.01" variant="outlined" density="compact" color="primary" /></v-col>

      <v-col cols="12"><v-divider class="my-2" /></v-col>

      <v-col cols="12" md="6">
        <v-slider
          v-model="config.REC_TOUCH_PENALTY_PCT"
          min="0"
          max="100"
          step="1"
          :label="t('settings.rec.touch_penalty_pct')"
          color="primary"
          density="compact"
          hide-details
          thumb-label
        />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider
          v-model="config.REC_IMPRESSION_PENALTY_PCT"
          min="0"
          max="100"
          step="1"
          :label="t('settings.rec.impression_penalty_pct')"
          color="primary"
          density="compact"
          hide-details
          thumb-label
        />
      </v-col>
      <v-col cols="12" md="6">
        <v-switch
          v-model="config.REC_DYNAMIC_EXPAND_ENABLED"
          :label="t('settings.rec.dynamic_expand_enabled')"
          color="primary"
          inset
          hide-details
        />
      </v-col>
      <v-col cols="12" md="6">
        <v-switch
          v-model="config.REC_SHOW_JPN_TITLE"
          :label="t('settings.rec.show_jpn_title')"
          color="primary"
          inset
          hide-details
        />
      </v-col>
      <v-col cols="12" md="6" class="d-flex align-center justify-end ga-2">
        <v-btn color="warning" variant="outlined" @click="clearRecommendTouchesAction">{{ t('settings.recommend.touch_clear') }}</v-btn>
        <v-btn color="error" variant="outlined" @click="clearRecommendProfileAction">{{ t('settings.recommend.profile_clear') }}</v-btn>
      </v-col>
      <v-col cols="12">
        <div class="text-caption text-medium-emphasis">{{ t('settings.recommend.touch_hint') }}</div>
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
