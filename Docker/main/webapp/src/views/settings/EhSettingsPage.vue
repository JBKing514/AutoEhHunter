<template>
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
    <div class="d-flex ga-2 align-center mb-3">
      <v-text-field v-model="newEhTag" :label="t('settings.eh.filter_tag')" variant="outlined" density="compact" color="primary" @keyup.enter="addEhTag" />
      <v-btn color="primary" @click="addEhTag">Add</v-btn>
    </div>
    <div class="d-flex flex-wrap ga-2">
      <v-chip v-for="tag in ehFilterTags" :key="tag" closable @click:close="removeEhTag(tag)">{{ tag }}</v-chip>
    </div>
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
</template>

<script>
import { useSettingsStore } from "../../stores/settingsStore";

export default {
  setup() {
    return useSettingsStore();
  },
};
</script>
