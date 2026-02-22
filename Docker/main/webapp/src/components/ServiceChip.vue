<template>
  <div>
    <div :class="chipClass" class="v-chip v-chip--size-default text-white px-3 py-2">
      {{ title }}: {{ message || 'n/a' }}
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  title: { type: String, required: true },
  ok: { type: [Boolean, null], default: null },
  message: { type: String, default: "n/a" },
});

const chipClass = computed(() => {
  if (props.ok === true) return "bg-success";
  if (props.ok === false) return "bg-error";
  return "bg-grey-lighten-1";
});
</script>
