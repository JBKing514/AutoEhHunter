<template>
<v-card  class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.eh.cookie') }} <v-chip size="small" class="ml-2" variant="tonal">{{ secretHint('EH_COOKIE') }}</v-chip></div>
            <v-row>
              <v-col cols="12" md="6"><v-text-field v-model="cookieParts.ipb_member_id" label="ipb_member_id" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="cookieParts.ipb_pass_hash" label="ipb_pass_hash" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="cookieParts.sk" label="sk" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="cookieParts.igneous" label="igneous" /></v-col>
            </v-row>
          </v-card>

<v-card  class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.eh.filter_category') }}</div>
            <div class="category-grid">
              <v-btn
                v-for="cat in ehCategoryDefs"
                :key="cat.key"
                class="category-btn"
                :style="categoryStyle(cat.key, cat.color)"
                @click="toggleCategory(cat.key)"
              >
                {{ cat.label }}
              </v-btn>
            </div>
          </v-card>

<v-card  class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.eh.filter_tag') }}</div>
            <div class="d-flex ga-2 align-center mb-3">
              <v-text-field v-model="newEhTag" :label="t('settings.eh.filter_tag')" @keyup.enter="addEhTag" />
              <v-btn color="primary" @click="addEhTag">Add</v-btn>
            </div>
            <div class="d-flex flex-wrap ga-2">
              <v-chip v-for="tag in ehFilterTags" :key="tag" closable @click:close="removeEhTag(tag)">{{ tag }}</v-chip>
            </div>
          </v-card>

<v-card  class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.eh_crawler') }}</div>
            <v-row>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_BASE_URL" :label="labelFor('EH_BASE_URL')" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_FETCH_MAX_PAGES" :label="labelFor('EH_FETCH_MAX_PAGES')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_REQUEST_SLEEP" :label="labelFor('EH_REQUEST_SLEEP')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_SAMPLING_DENSITY" :label="labelFor('EH_SAMPLING_DENSITY')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_USER_AGENT" :label="labelFor('EH_USER_AGENT')" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_MIN_RATING" :label="labelFor('EH_MIN_RATING')" type="number" /></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="config.EH_QUEUE_LIMIT" :label="labelFor('EH_QUEUE_LIMIT')" type="number" /></v-col>
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
