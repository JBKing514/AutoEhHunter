<template>
  <v-card class="pa-4 mb-4">
    <div class="text-subtitle-1 font-weight-medium mb-3">{{ t("settings.reader.title") }}</div>
    <div class="text-caption text-medium-emphasis mb-4">{{ t("settings.reader.hint") }}</div>

    <v-row>
      <v-col cols="12" md="6">
        <v-select
          v-model="config.READER_MODE"
          :items="modeItems"
          item-title="title"
          item-value="value"
          :label="t('settings.reader.mode')"
          variant="outlined"
          density="compact"
          hide-details
        />
      </v-col>
      <v-col cols="12" md="6">
        <v-select
          v-model="config.READER_DIRECTION"
          :items="directionItems"
          item-title="title"
          item-value="value"
          :label="t('settings.reader.direction')"
          variant="outlined"
          density="compact"
          hide-details
        />
      </v-col>
      <v-col cols="12" md="6">
        <v-select
          v-model="config.READER_FIT_MODE"
          :items="fitItems"
          item-title="title"
          item-value="value"
          :label="t('settings.reader.fit_mode')"
          variant="outlined"
          density="compact"
          hide-details
        />
      </v-col>
      <v-col cols="12" md="6">
        <v-slider
          v-model="config.READER_WHEEL_CURVE"
          :min="0"
          :max="100"
          :step="1"
          :label="t('settings.reader.wheel_curve')"
          color="primary"
          density="compact"
          hide-details
        />
      </v-col>
      <v-col cols="12" md="6">
        <v-select
          v-model="config.READER_WHEEL_POSITION"
          :items="wheelPosItems"
          item-title="title"
          item-value="value"
          :label="t('settings.reader.wheel_position')"
          variant="outlined"
          density="compact"
          hide-details
        />
      </v-col>
      <v-col cols="12" md="6">
        <v-text-field
          v-model="config.READER_PRELOAD_COUNT"
          type="number"
          min="0"
          max="4"
          :label="t('settings.reader.preload')"
          variant="outlined"
          density="compact"
          hide-details
        />
      </v-col>
      <v-col cols="12" md="6" class="d-flex align-center">
        <v-switch v-model="config.READER_SWIPE_ENABLED" :label="t('settings.reader.swipe')" color="primary" inset hide-details />
      </v-col>
      <v-col cols="12" md="6" class="d-flex align-center">
        <v-switch v-model="config.READER_TAP_TO_TURN" :label="t('settings.reader.tap_turn')" color="primary" inset hide-details />
      </v-col>
      <v-col cols="12" md="6" class="d-flex align-center">
        <v-switch v-model="config.READER_PAGE_ANIM_ENABLED" :label="t('settings.reader.page_anim')" color="primary" inset hide-details />
      </v-col>
      <v-col cols="12" md="6" class="d-flex align-center">
        <v-switch v-model="config.READER_HIDE_START_BUTTON" :label="t('settings.reader.hide_start_button')" color="primary" inset hide-details />
      </v-col>
      <v-col cols="12" md="6" class="d-flex align-center">
        <v-switch v-model="config.READER_HIDE_APP_UI" :label="t('settings.reader.hide_app_ui')" color="primary" inset hide-details />
      </v-col>
      <v-col cols="12" md="6" class="d-flex align-center">
        <v-switch v-model="config.READER_VIEWPORT_FIT_COVER" :label="t('settings.reader.viewport_fit_cover')" color="primary" inset hide-details />
      </v-col>
    </v-row>
  </v-card>
</template>

<script>
import { computed } from "vue";
import { useSettingsStore } from "../../stores/settingsStore";

export default {
  setup() {
    const settingsStore = useSettingsStore();
    const directionItems = computed(() => [
      { title: settingsStore.t("settings.reader.direction_ltr"), value: "ltr" },
      { title: settingsStore.t("settings.reader.direction_rtl"), value: "rtl" },
    ]);
    const modeItems = computed(() => [
      { title: settingsStore.t("reader.mode.paged"), value: "paged" },
      { title: settingsStore.t("reader.mode.continuous"), value: "continuous" },
    ]);
    const fitItems = computed(() => [
      { title: settingsStore.t("settings.reader.fit_contain"), value: "contain" },
      { title: settingsStore.t("settings.reader.fit_width"), value: "width" },
      { title: settingsStore.t("settings.reader.fit_height"), value: "height" },
    ]);
    const wheelPosItems = computed(() => [
      { title: settingsStore.t("settings.reader.wheel_pos_bottom"), value: "bottom" },
      { title: settingsStore.t("settings.reader.wheel_pos_left"), value: "left" },
      { title: settingsStore.t("settings.reader.wheel_pos_right"), value: "right" },
    ]);
    return {
      ...settingsStore,
      modeItems,
      directionItems,
      fitItems,
      wheelPosItems,
    };
  },
};
</script>
