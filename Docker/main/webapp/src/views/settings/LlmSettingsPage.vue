<template>
<v-card  class="pa-4 mb-4">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.tab.llm') }}</div>
            <v-row>
              <v-col cols="12" md="8"><v-text-field v-model="config.LLM_API_BASE" :label="labelFor('LLM_API_BASE')" /></v-col>
              <v-col cols="12" md="4" class="d-flex align-center"><v-btn variant="outlined" block @click="reloadLlmModels">{{ t('settings.models.reload') }}</v-btn></v-col>
              <v-col cols="12" md="6"><v-combobox v-model="config.LLM_MODEL" :items="llmModelOptions" :label="labelFor('LLM_MODEL')" clearable /></v-col>
              <v-col cols="12" md="6"><v-combobox v-model="config.EMB_MODEL" :items="llmModelOptions" :label="labelFor('EMB_MODEL')" clearable /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.LLM_TIMEOUT_S" type="number" min="5" max="600" :label="labelFor('LLM_TIMEOUT_S')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.LLM_MAX_TOKENS_CHAT" type="number" min="64" max="8192" :label="labelFor('LLM_MAX_TOKENS_CHAT')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.LLM_MAX_TOKENS_INTENT" type="number" min="16" max="2048" :label="labelFor('LLM_MAX_TOKENS_INTENT')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.LLM_MAX_TOKENS_TAG_EXTRACT" type="number" min="64" max="8192" :label="labelFor('LLM_MAX_TOKENS_TAG_EXTRACT')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.LLM_MAX_TOKENS_PROFILE" type="number" min="64" max="4096" :label="labelFor('LLM_MAX_TOKENS_PROFILE')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.LLM_MAX_TOKENS_REPORT" type="number" min="64" max="4096" :label="labelFor('LLM_MAX_TOKENS_REPORT')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.LLM_MAX_TOKENS_SEARCH_NARRATIVE" type="number" min="64" max="4096" :label="labelFor('LLM_MAX_TOKENS_SEARCH_NARRATIVE')" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.LLM_MODEL_CUSTOM" :label="labelFor('LLM_MODEL_CUSTOM')" clearable /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.EMB_MODEL_CUSTOM" :label="labelFor('EMB_MODEL_CUSTOM')" clearable /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="config.LLM_API_KEY" :label="labelFor('LLM_API_KEY')" type="password" :placeholder="t('settings.secret.keep')" :hint="secretHint('LLM_API_KEY')" persistent-hint /></v-col>
              <v-col cols="12"><v-textarea v-model="config.PROMPT_SEARCH_NARRATIVE_SYSTEM" :label="labelFor('PROMPT_SEARCH_NARRATIVE_SYSTEM')" rows="4" auto-grow /></v-col>
              <v-col cols="12"><v-textarea v-model="config.PROMPT_INTENT_ROUTER_SYSTEM" :label="labelFor('PROMPT_INTENT_ROUTER_SYSTEM')" rows="6" auto-grow /></v-col>
              <v-col cols="12"><v-textarea v-model="config.PROMPT_PROFILE_SYSTEM" :label="labelFor('PROMPT_PROFILE_SYSTEM')" rows="4" auto-grow /></v-col>
              <v-col cols="12"><v-textarea v-model="config.PROMPT_REPORT_SYSTEM" :label="labelFor('PROMPT_REPORT_SYSTEM')" rows="4" auto-grow /></v-col>
              <v-col cols="12"><v-textarea v-model="config.PROMPT_TAG_EXTRACT_SYSTEM" :label="labelFor('PROMPT_TAG_EXTRACT_SYSTEM')" rows="4" auto-grow /></v-col>
              <v-col cols="12">
                <div class="text-subtitle-2 mb-2">{{ t('skills.builtin.title') }}</div>
                <div class="d-flex flex-wrap ga-2">
                  <v-chip v-for="s in builtinSkills" :key="`bi-${s.name}`" color="primary" variant="tonal">{{ s.name }}</v-chip>
                </div>
              </v-col>
              <v-col cols="12">
                <div class="text-subtitle-2 mb-2">{{ t('skills.user.title') }}</div>
                <div class="d-flex ga-2 align-center mb-2">
                  <input ref="pluginUploadRef" type="file" accept=".py" @change="onPluginUploadChange" />
                  <v-btn variant="outlined" @click="loadSkillsData">{{ t('skills.reload') }}</v-btn>
                </div>
                <div class="d-flex flex-wrap ga-2">
                  <v-chip v-for="s in userSkills" :key="`usr-${s.name}`" variant="outlined">{{ s.name }}</v-chip>
                </div>
                <div class="text-caption text-medium-emphasis mt-2">{{ (pluginFiles || []).join(', ') || '-' }}</div>
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
