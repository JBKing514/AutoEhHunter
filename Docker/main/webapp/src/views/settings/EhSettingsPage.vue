<template>
  <v-card class="pa-4 mb-4">
    <div class="d-flex align-center justify-space-between">
      <div class="text-subtitle-1 font-weight-medium">{{ t('settings.tab.eh') }}</div>
      <v-btn size="small" variant="tonal" color="primary" :prepend-icon="settingsLocked ? 'mdi-lock' : 'mdi-lock-open-variant'" @click="settingsLocked = !settingsLocked">
        {{ settingsLocked ? t('settings.lock.unlock') : t('settings.lock.lock') }}
      </v-btn>
    </div>
    <v-alert v-if="settingsLocked" type="warning" variant="tonal" class="mt-3">{{ t('settings.lock.hint') }}</v-alert>
  </v-card>

  <div :class="{ 'settings-locked': settingsLocked }">
    <v-card class="pa-4 mb-4">
      <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.eh.cookie') }} <v-chip size="small" class="ml-2" variant="tonal">{{ secretHint('EH_COOKIE') }}</v-chip></div>
      <v-row>
        <v-col cols="12" md="6"><v-text-field v-model="cookieParts.ipb_member_id" label="ipb_member_id" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="6"><v-text-field v-model="cookieParts.ipb_pass_hash" label="ipb_pass_hash" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="6"><v-text-field v-model="cookieParts.sk" label="sk" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="6"><v-text-field v-model="cookieParts.igneous" label="igneous" variant="outlined" density="compact" color="primary" /></v-col>
      </v-row>
    </v-card>

    <v-card class="pa-4 mb-4">
      <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.eh.filter_category') }}</div>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 16px;">
        <v-btn
          v-for="cat in ehCategoryDefs"
          :key="cat.key"
          class="category-btn font-weight-bold"
          rounded="lg"
          variant="flat"
          :style="categoryStyle(cat.key, cat.color)"
          @click="toggleCategory(cat.key)"
        >
          <span class="text-truncate">{{ cat.label }}</span>
        </v-btn>
      </div>
    </v-card>

    <v-card class="pa-4 mb-4">
      <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.eh.filter_tag') }}</div>
      <v-combobox
        v-model="ehFilterTags"
        v-model:search="newEhTag"
        :items="ehTagSuggestions"
        hide-no-data
        multiple
        chips
        closable-chips
        clearable
        variant="outlined"
        density="compact"
        color="primary"
        :label="t('settings.eh.filter_tag')"
        :hint="t('settings.eh.filter_tag.help')"
        persistent-hint
        @keydown.enter.prevent="onEhTagEnter"
      />
    </v-card>

    <v-card class="pa-4 mb-4">
      <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.eh_crawler') }}</div>
      <v-row>
        <v-col cols="12" md="4"><v-text-field v-model="config.EH_BASE_URL" :label="t('settings.eh.base_url')" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="4"><v-text-field v-model="config.EH_FETCH_MAX_PAGES" :label="t('settings.eh.max_pages')" type="number" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="4"><v-text-field v-model="config.EH_REQUEST_SLEEP" :label="t('settings.eh.request_sleep')" type="number" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="4"><v-text-field v-model="config.EH_SAMPLING_DENSITY" :label="t('settings.eh.sampling_density')" type="number" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="4"><v-text-field v-model="config.EH_USER_AGENT" :label="t('settings.eh.user_agent')" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="4"><v-text-field v-model="config.EH_MIN_RATING" :label="t('settings.eh.min_rating')" type="number" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="4"><v-text-field v-model="config.EH_QUEUE_LIMIT" :label="t('settings.eh.queue_limit')" type="number" variant="outlined" density="compact" color="primary" /></v-col>
      </v-row>
    </v-card>
  </div>
</template>

<script>
import { ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { useSettingsStore } from "../../stores/settingsStore";

export default {
  setup() {
    const settingsStore = useSettingsStore();
    const storeRefs = storeToRefs(settingsStore);

    function onEhTagEnter() {
      const raw = String(settingsStore.newEhTag || "").trim();
      if (!raw) return;
      const v = raw.toLowerCase();
      if (!Array.isArray(settingsStore.ehFilterTags)) {
        settingsStore.ehFilterTags = [];
      }
      if (!settingsStore.ehFilterTags.includes(v)) {
        settingsStore.ehFilterTags.push(v);
      }
      settingsStore.newEhTag = "";
      settingsStore.ehTagSuggestions = [];
    }

    watch(
      () => settingsStore.newEhTag,
      (newVal) => {
        if (newVal) {
          settingsStore.loadEhTagSuggestions().catch(() => null);
        } else {
          settingsStore.ehTagSuggestions = [];
        }
      },
    );

    return {
      ...settingsStore,
      ...storeRefs,
      settingsLocked: ref(true),
      onEhTagEnter,
    };
  },
};
</script>

<style scoped>
.settings-locked {
  pointer-events: none;
  opacity: 0.58;
}
</style>
