<template>
  <div class="v-card metric-card pa-4 rounded-lg elevation-2">
    <div class="text-caption text-medium-emphasis">{{ title }}</div>
    <div class="text-h5 font-weight-bold mt-1">{{ String(value) }}</div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  value: { type: [String, Number], required: true },
});
</script>
