<template>
  <v-card class="pa-4 mb-4">
    <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.tab.search') }}</div>
    <v-alert type="info" variant="tonal" class="mb-4">
      {{ t('settings.search.tuning_hint') }}
      <template #append>
        <v-btn size="small" variant="outlined" @click="resetSearchWeightPresets">
          {{ t('settings.search.reset_presets') }}
        </v-btn>
      </template>
    </v-alert>

    <v-row>
      <v-col cols="12" md="4">
        <v-switch v-model="config.SEARCH_NL_ENABLED" :label="t('settings.search.nl_enabled')" color="primary" inset hide-details />
      </v-col>
      <v-col cols="12" md="4">
        <v-switch v-model="config.SEARCH_TAG_SMART_ENABLED" :label="t('settings.search.tag_smart_enabled')" color="primary" inset hide-details />
      </v-col>
      <v-col cols="12" md="4">
        <v-switch v-model="config.SEARCH_TAG_HARD_FILTER" :label="t('settings.search.tag_hard_filter')" color="primary" inset hide-details />
      </v-col>
      <v-col cols="12" md="4">
        <v-switch v-model="config.SEARCH_RESULT_INFINITE" :label="t('settings.search.result_infinite')" color="primary" inset hide-details />
      </v-col>
      <v-col cols="12" md="4">
        <v-select v-model="config.SEARCH_RESULT_SIZE" :items="[20, 50, 100]" :label="t('settings.search.result_size')" variant="outlined" density="compact" color="primary" hide-details />
      </v-col>
      
      <v-col cols="12"><v-divider class="my-2" /></v-col>

      <v-col cols="12">
        <div class="text-caption text-primary font-weight-bold">{{ t('settings.search.preset.visual') }}</div>
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_WEIGHT_VISUAL" min="0" max="5" step="0.01" :label="t('settings.search.weight_visual')" color="primary" density="compact" hide-details thumb-label />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_WEIGHT_EH_VISUAL" min="0" max="5" step="0.01" :label="t('settings.search.weight_eh_visual')" color="primary" density="compact" hide-details thumb-label />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_WEIGHT_DESC" min="0" max="5" step="0.01" :label="t('settings.search.weight_desc')" color="primary" density="compact" hide-details thumb-label />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_WEIGHT_TEXT" min="0" max="5" step="0.01" :label="t('settings.search.weight_text')" color="primary" density="compact" hide-details thumb-label />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_WEIGHT_EH_TEXT" min="0" max="5" step="0.01" :label="t('settings.search.weight_eh_text')" color="primary" density="compact" hide-details thumb-label />
      </v-col>

      <v-col cols="12">
        <div class="text-caption text-primary font-weight-bold">{{ t('settings.search.preset.plot') }}</div>
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_WEIGHT_PLOT_VISUAL" min="0" max="5" step="0.01" :label="t('settings.search.weight_plot_visual')" color="primary" density="compact" hide-details thumb-label />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_WEIGHT_PLOT_EH_VISUAL" min="0" max="5" step="0.01" :label="t('settings.search.weight_plot_eh_visual')" color="primary" density="compact" hide-details thumb-label />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_WEIGHT_PLOT_DESC" min="0" max="5" step="0.01" :label="t('settings.search.weight_plot_desc')" color="primary" density="compact" hide-details thumb-label />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_WEIGHT_PLOT_TEXT" min="0" max="5" step="0.01" :label="t('settings.search.weight_plot_text')" color="primary" density="compact" hide-details thumb-label />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_WEIGHT_PLOT_EH_TEXT" min="0" max="5" step="0.01" :label="t('settings.search.weight_plot_eh_text')" color="primary" density="compact" hide-details thumb-label />
      </v-col>

      <v-col cols="12">
        <div class="text-caption text-primary font-weight-bold">{{ t('settings.search.preset.mixed') }}</div>
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_WEIGHT_MIXED_VISUAL" min="0" max="5" step="0.01" :label="t('settings.search.weight_mixed_visual')" color="primary" density="compact" hide-details thumb-label />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_WEIGHT_MIXED_EH_VISUAL" min="0" max="5" step="0.01" :label="t('settings.search.weight_mixed_eh_visual')" color="primary" density="compact" hide-details thumb-label />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_WEIGHT_MIXED_DESC" min="0" max="5" step="0.01" :label="t('settings.search.weight_mixed_desc')" color="primary" density="compact" hide-details thumb-label />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_WEIGHT_MIXED_TEXT" min="0" max="5" step="0.01" :label="t('settings.search.weight_mixed_text')" color="primary" density="compact" hide-details thumb-label />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_WEIGHT_MIXED_EH_TEXT" min="0" max="5" step="0.01" :label="t('settings.search.weight_mixed_eh_text')" color="primary" density="compact" hide-details thumb-label />
      </v-col>

      <v-col cols="12"><v-divider class="my-2" /></v-col>

      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_TAG_FUZZY_THRESHOLD" min="0.2" max="1" step="0.01" :label="t('settings.search.fuzzy_threshold')" color="primary" density="compact" hide-details thumb-label />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_TEXT_WEIGHT" min="0" max="1" step="0.01" :label="t('settings.search.text_weight')" color="primary" density="compact" hide-details thumb-label />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_VISUAL_WEIGHT" min="0" max="1" step="0.01" :label="t('settings.search.visual_weight')" color="primary" density="compact" hide-details thumb-label />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_MIXED_TEXT_WEIGHT" min="0" max="1" step="0.01" :label="t('settings.search.mixed_text_weight')" color="primary" density="compact" hide-details thumb-label />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider v-model="config.SEARCH_MIXED_VISUAL_WEIGHT" min="0" max="1" step="0.01" :label="t('settings.search.mixed_visual_weight')" color="primary" density="compact" hide-details thumb-label />
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
