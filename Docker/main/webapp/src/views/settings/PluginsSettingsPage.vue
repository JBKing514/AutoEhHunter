<template>
<v-card class="pa-4 mb-4">
  <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.tab.plugins') }}</div>

  <!-- Built-in Skills -->
  <div class="text-subtitle-2 mb-2">{{ t('skills.builtin.title') }}</div>
  <div class="d-flex flex-wrap ga-2 mb-4">
    <v-chip v-for="s in builtinSkills" :key="`bi-${s.name}`" color="primary" variant="tonal">{{ s.name }}</v-chip>
    <span v-if="!builtinSkills.length" class="text-caption text-medium-emphasis">-</span>
  </div>

  <!-- User Plugins -->
  <div class="text-subtitle-2 mb-2">{{ t('skills.user.title') }}</div>
  <div class="d-flex ga-2 align-center mb-2">
    <input ref="pluginUploadRef" type="file" accept=".py" @change="onPluginUploadChange" />
    <v-btn variant="outlined" @click="loadSkillsData">{{ t('skills.reload') }}</v-btn>
  </div>
  <div class="d-flex flex-wrap ga-2 mb-2">
    <v-chip v-for="s in userSkills" :key="`usr-${s.name}`" variant="outlined">{{ s.name }}</v-chip>
    <span v-if="!userSkills.length" class="text-caption text-medium-emphasis">-</span>
  </div>
  <div class="text-caption text-medium-emphasis">{{ (pluginFiles || []).join(', ') || '-' }}</div>
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
