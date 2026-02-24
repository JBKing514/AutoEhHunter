<template>
  <div>
    <!-- LLM Provider -->
    <v-card class="pa-4 mb-4">
      <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.tab.llm') }}</div>
      <v-row>
        <v-col cols="12" md="8"><v-text-field v-model="config.LLM_API_BASE" :label="t('settings.provider.llm_api_base')" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="4" class="d-flex align-center"><v-btn variant="outlined" block @click="reloadLlmModels">{{ t('settings.models.reload') }}</v-btn></v-col>
        <v-col cols="12" md="6"><v-combobox v-model="config.LLM_MODEL" :items="llmModelOptions" :label="t('settings.provider.llm_model')" clearable variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="6"><v-combobox v-model="config.EMB_MODEL" :items="llmModelOptions" :label="t('settings.provider.emb_model')" clearable variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="6"><v-text-field v-model="config.LLM_TIMEOUT_S" type="number" min="5" max="600" :label="t('settings.provider.llm_timeout_s')" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="6"><v-text-field v-model="config.LLM_MAX_TOKENS_CHAT" type="number" min="64" max="8192" :label="t('settings.provider.llm_max_tokens_chat')" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="6"><v-text-field v-model="config.LLM_MAX_TOKENS_INTENT" type="number" min="16" max="2048" :label="t('settings.provider.llm_max_tokens_intent')" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="6"><v-text-field v-model="config.LLM_MAX_TOKENS_TAG_EXTRACT" type="number" min="64" max="8192" :label="t('settings.provider.llm_max_tokens_tag_extract')" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="6"><v-text-field v-model="config.LLM_MAX_TOKENS_PROFILE" type="number" min="64" max="4096" :label="t('settings.provider.llm_max_tokens_profile')" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="6"><v-text-field v-model="config.LLM_MAX_TOKENS_REPORT" type="number" min="64" max="4096" :label="t('settings.provider.llm_max_tokens_report')" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="6"><v-text-field v-model="config.LLM_MAX_TOKENS_SEARCH_NARRATIVE" type="number" min="64" max="4096" :label="t('settings.provider.llm_max_tokens_search_narrative')" variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="6"><v-text-field v-model="config.LLM_MODEL_CUSTOM" :label="t('settings.provider.llm_model_custom')" clearable variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="6"><v-text-field v-model="config.EMB_MODEL_CUSTOM" :label="t('settings.provider.emb_model_custom')" clearable variant="outlined" density="compact" color="primary" /></v-col>
        <v-col cols="12" md="6"><v-text-field v-model="config.LLM_API_KEY" :label="t('settings.provider.llm_api_key')" type="password" :placeholder="t('settings.secret.keep')" :hint="secretHint('LLM_API_KEY')" persistent-hint variant="outlined" density="compact" color="primary" /></v-col>
      </v-row>
    </v-card>

    <!-- Prompts -->
    <v-card class="pa-4 mb-4">
      <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.prompts') }}</div>
      <v-row>
        <!-- 1. CHAT_CUSTOM_PERSONA — top-level persona -->
        <v-col cols="12">
          <v-textarea
            v-model="config.CHAT_CUSTOM_PERSONA"
            :label="t('settings.prompt.custom_persona')"
            rows="4"
            auto-grow
            :hint="t('settings.prompt.custom_persona_hint')"
            persistent-hint
          />
        </v-col>
        <!-- 2. PROMPT_SEARCH_NARRATIVE_SYSTEM -->
        <v-col cols="12">
          <v-textarea v-model="config.PROMPT_SEARCH_NARRATIVE_SYSTEM" :label="t('settings.prompt.search_narrative')" rows="4" auto-grow />
        </v-col>
        <!-- 3. PROMPT_PROFILE_SYSTEM -->
        <v-col cols="12">
          <v-textarea v-model="config.PROMPT_PROFILE_SYSTEM" :label="t('settings.prompt.profile')" rows="4" auto-grow />
        </v-col>
        <!-- 4. PROMPT_REPORT_SYSTEM -->
        <v-col cols="12">
          <v-textarea v-model="config.PROMPT_REPORT_SYSTEM" :label="t('settings.prompt.report')" rows="4" auto-grow />
        </v-col>
        <!-- 5. PROMPT_INTENT_ROUTER_SYSTEM — system-critical, orange warning -->
        <v-col cols="12">
          <div style="border: 2px solid #f97316; border-radius: 8px; padding: 12px;">
            <div class="d-flex align-center ga-2 mb-2">
              <v-icon color="orange-darken-1">mdi-alert</v-icon>
              <span class="text-caption font-weight-medium" style="color: #f97316;">{{ t('settings.prompt.hard_func_warning') }}</span>
            </div>
            <v-textarea v-model="config.PROMPT_INTENT_ROUTER_SYSTEM" :label="t('settings.prompt.intent_router')" rows="6" auto-grow />
          </div>
        </v-col>
        <!-- 6. PROMPT_TAG_EXTRACT_SYSTEM — system-critical, orange warning -->
        <v-col cols="12">
          <div style="border: 2px solid #f97316; border-radius: 8px; padding: 12px;">
            <div class="d-flex align-center ga-2 mb-2">
              <v-icon color="orange-darken-1">mdi-alert</v-icon>
              <span class="text-caption font-weight-medium" style="color: #f97316;">{{ t('settings.prompt.hard_func_warning') }}</span>
            </div>
            <v-textarea v-model="config.PROMPT_TAG_EXTRACT_SYSTEM" :label="t('settings.prompt.tag_extract')" rows="4" auto-grow />
          </div>
        </v-col>
      </v-row>
    </v-card>

    <!-- Memory config -->
    <v-card class="pa-4 mb-4">
      <div class="text-subtitle-1 font-weight-medium mb-3">{{ t('settings.section.memory') }}</div>
      <v-row>
        <v-col cols="12" md="4">
          <v-switch
            v-model="config.MEMORY_SHORT_TERM_ENABLED"
            :label="t('settings.memory.short_term_enabled')"
            color="primary"
            hide-details
            inset
          />
        </v-col>
        <v-col cols="12" md="4">
          <v-switch
            v-model="config.MEMORY_LONG_TERM_ENABLED"
            :label="t('settings.memory.long_term_enabled')"
            color="primary"
            hide-details
            inset
          />
        </v-col>
        <v-col cols="12" md="4">
          <v-switch
            v-model="config.MEMORY_SEMANTIC_ENABLED"
            :label="t('settings.memory.semantic_enabled')"
            color="primary"
            hide-details
            inset
          />
        </v-col>
        <v-col cols="12" md="4">
          <v-text-field
            v-model="config.MEMORY_SHORT_TERM_LIMIT"
            type="number" min="2" max="60"
            :label="t('settings.memory.short_term_limit')"
            :disabled="!config.MEMORY_SHORT_TERM_ENABLED"
            variant="outlined"
            density="compact"
            color="primary"
          />
        </v-col>
        <v-col cols="12" md="4">
          <v-text-field
            v-model="config.MEMORY_LONG_TERM_TOP_TAGS"
            type="number" min="0" max="30"
            :label="t('settings.memory.long_term_top_tags')"
            :disabled="!config.MEMORY_LONG_TERM_ENABLED"
            variant="outlined"
            density="compact"
            color="primary"
          />
        </v-col>
        <v-col cols="12" md="4">
          <v-text-field
            v-model="config.MEMORY_SEMANTIC_TOP_FACTS"
            type="number" min="0" max="20"
            :label="t('settings.memory.semantic_top_facts')"
            :disabled="!config.MEMORY_SEMANTIC_ENABLED"
            variant="outlined"
            density="compact"
            color="primary"
          />
        </v-col>
      </v-row>
    </v-card>
  </div>
</template>

<script>
import { useSettingsStore } from "../../stores/settingsStore";

export default {
  setup() {
    return useSettingsStore();
  },
};
</script>
