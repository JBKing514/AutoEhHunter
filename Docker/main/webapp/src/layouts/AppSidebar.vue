<template>
  <v-navigation-drawer
    :model-value="modelValue"
    :rail="rail"
    permanent
    border
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="drawer-brand px-4 py-4">
      <img :src="brandLogo" alt="AutoEhHunter" class="brand-logo" />
      <div v-if="!rail" class="brand-title">AutoEhHunter</div>
    </div>
    <v-divider />
    <v-list nav density="comfortable">
      <v-list-item
        v-for="item in navItems"
        :key="item.key"
        :active="tab === item.key"
        :prepend-icon="item.icon"
        :title="t(item.title)"
        @click="emit('go-tab', item.key)"
      />
    </v-list>
    <template #append>
      <v-divider />
      <v-list density="compact">
        <v-list-item
          :title="t('nav.compact')"
          prepend-icon="mdi-dock-left"
          @click="emit('update:rail', !rail)"
        />
      </v-list>
    </template>
  </v-navigation-drawer>
</template>

<script setup>
defineProps({
  modelValue: { type: Boolean, default: true },
  rail: { type: Boolean, default: false },
  brandLogo: { type: String, default: "" },
  navItems: { type: Array, default: () => [] },
  tab: { type: String, default: "dashboard" },
  t: { type: Function, required: true },
});

const emit = defineEmits(["update:modelValue", "update:rail", "go-tab"]);
</script>
