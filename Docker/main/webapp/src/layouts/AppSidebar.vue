<template>
  <v-navigation-drawer
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :rail="!mobile && rail"
    :width="280"
    class="app-sidebar-drawer"
  >
    <div class="drawer-brand px-3 py-4 d-flex align-center" style="min-height: 64px;">
      <v-avatar rounded="lg" size="36" class="mr-3">
        <img :src="brandLogo" alt="AutoEhHunter" style="width: 100%; height: 100%; object-fit: cover;" />
      </v-avatar>
      <div v-if="!(!mobile && rail)" class="text-subtitle-1 font-weight-bold text-truncate">AutoEhHunter</div>
    </div>

    <v-divider />

    <v-list nav density="comfortable" class="px-2">
      <v-list-item
        v-for="item in navItems"
        :key="item.key"
        :active="tab === item.key"
        :prepend-icon="item.icon"
        :title="t(item.title)"
        color="primary" 
        rounded="lg" 
        class="mb-1"
        @click="emit('go-tab', item.key)"
      />
    </v-list>

    <template #append v-if="!mobile">
      <v-divider />
      <div class="pa-2">
        <v-btn
          block
          variant="outlined"
          color="primary"
          prepend-icon="mdi-bug-outline"
          class="mb-2"
          href="https://github.com/JBKing514/AutoEhHunter/issues"
          target="_blank"
          rel="noopener noreferrer"
        >
          Feedback
        </v-btn>
        <v-btn
          block
          variant="text"
          color="medium-emphasis"
          @click="emit('update:rail', !rail)"
        >
          <v-icon>{{ rail ? 'mdi-chevron-right' : 'mdi-chevron-left' }}</v-icon>
          <span v-if="!rail" class="ml-2">{{ t('nav.compact') }}</span>
        </v-btn>
      </div>
    </template>
  </v-navigation-drawer>
</template>

<script setup>
import { useDisplay } from "vuetify";

const props = defineProps({
  modelValue: { type: Boolean, default: true },
  rail: { type: Boolean, default: false },
  brandLogo: { type: String, default: "" },
  navItems: { type: Array, default: () => [] },
  tab: { type: String, default: "dashboard" },
  t: { type: Function, required: true },
});

const emit = defineEmits(["update:modelValue", "update:rail", "go-tab"]);

// 引入 Vuetify 的响应式断点探测
const { mobile } = useDisplay();
</script>

<style scoped>
.app-sidebar-drawer {
  flex-shrink: 0;
}
</style>
