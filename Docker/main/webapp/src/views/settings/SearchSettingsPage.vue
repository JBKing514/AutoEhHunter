<template>
<v-card  class="pa-4 mb-4">
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
</template>

<script>
import { useSettingsStore } from "../../stores/settingsStore";

export default {
  setup() {
    return useSettingsStore();
  },
};
</script>
