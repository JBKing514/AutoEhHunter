<template>
<v-card  class="pa-4 mb-4">
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
              <v-col cols="12" md="6">
                <v-slider
                  v-model="config.REC_TOUCH_PENALTY_PCT"
                  min="0"
                  max="100"
                  step="1"
                  :label="labelFor('REC_TOUCH_PENALTY_PCT')"
                  thumb-label
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-slider
                  v-model="config.REC_IMPRESSION_PENALTY_PCT"
                  min="0"
                  max="100"
                  step="1"
                  :label="labelFor('REC_IMPRESSION_PENALTY_PCT')"
                  thumb-label
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-switch
                  v-model="config.REC_DYNAMIC_EXPAND_ENABLED"
                  :label="labelFor('REC_DYNAMIC_EXPAND_ENABLED')"
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
