<template>
  <div class="reader-quick-settings" @click.stop>
    <v-btn-toggle :model-value="readerMode" mandatory density="compact" divided variant="outlined" color="primary" @update:model-value="$emit('update:readerMode', $event)">
      <v-btn value="paged">{{ t("reader.mode.paged") }}</v-btn>
      <v-btn value="continuous">{{ t("reader.mode.continuous") }}</v-btn>
    </v-btn-toggle>
    <v-btn-toggle :model-value="direction" mandatory density="compact" divided variant="outlined" color="primary" @update:model-value="$emit('update:direction', $event)">
      <v-btn value="ltr">LTR</v-btn>
      <v-btn value="rtl">RTL</v-btn>
    </v-btn-toggle>
    <v-btn-toggle :model-value="fitMode" mandatory density="compact" divided variant="outlined" color="primary" @update:model-value="$emit('update:fitMode', $event)">
      <v-btn value="contain">{{ t("settings.reader.fit_contain") }}</v-btn>
      <v-btn value="width">{{ t("settings.reader.fit_width") }}</v-btn>
      <v-btn value="height">{{ t("settings.reader.fit_height") }}</v-btn>
    </v-btn-toggle>
    <v-select
      :model-value="wheelPosition"
      :items="wheelPosItems"
      item-title="title"
      item-value="value"
      density="compact"
      variant="outlined"
      hide-details
      @update:model-value="$emit('update:wheelPosition', $event)"
    />
    <v-slider
      :model-value="wheelCurve"
      :min="0"
      :max="100"
      :step="1"
      density="compact"
      hide-details
      color="deep-orange"
      :label="t('settings.reader.wheel_curve')"
      @update:model-value="$emit('update:wheelCurve', $event)"
    />
    <v-switch
      :model-value="pageAnimEnabled"
      inset
      hide-details
      color="primary"
      :label="t('settings.reader.page_anim')"
      @update:model-value="$emit('update:pageAnimEnabled', $event)"
    />
    <v-btn color="primary" variant="flat" :loading="saving" @click="saveNow">{{ t("settings.save") }}</v-btn>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { useLayoutStore } from "../../stores/layoutStore";
import { useSettingsStore } from "../../stores/settingsStore";

defineProps({
  readerMode: { type: String, default: "paged" },
  direction: { type: String, default: "ltr" },
  fitMode: { type: String, default: "contain" },
  wheelPosition: { type: String, default: "bottom" },
  wheelCurve: { type: Number, default: 55 },
  pageAnimEnabled: { type: Boolean, default: true },
});

defineEmits(["update:readerMode", "update:direction", "update:fitMode", "update:wheelPosition", "update:wheelCurve", "update:pageAnimEnabled"]);

const layoutStore = useLayoutStore();
const settingsStore = useSettingsStore();
const t = (key, vars = {}) => layoutStore.t(key, vars);
const saving = ref(false);

const wheelPosItems = computed(() => [
  { title: t("settings.reader.wheel_pos_bottom"), value: "bottom" },
  { title: t("settings.reader.wheel_pos_left"), value: "left" },
  { title: t("settings.reader.wheel_pos_right"), value: "right" },
]);

async function saveNow() {
  if (saving.value) return;
  saving.value = true;
  try {
    await settingsStore.saveConfig();
  } catch (_e) {
    // store already handles notifications
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.reader-quick-settings {
  position: fixed;
  right: 10px;
  top: calc(max(54px, env(safe-area-inset-top) + 44px));
  z-index: 9;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: color-mix(in srgb, rgb(var(--v-theme-surface)) 86%, transparent);
  border: 1px solid color-mix(in srgb, rgb(var(--v-theme-on-surface)) 18%, transparent);
  border-radius: 12px;
  padding: 10px;
  backdrop-filter: blur(6px);
  color: rgb(var(--v-theme-on-surface));
}
</style>
