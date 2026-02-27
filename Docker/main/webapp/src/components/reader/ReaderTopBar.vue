<template>
  <div class="reader-topbar">
    <v-btn icon="mdi-arrow-left" variant="text" color="white" @click="$emit('back')" />
    <v-btn icon="mdi-home-outline" variant="text" color="white" @click="$emit('home')" />
    <div class="reader-title-wrap">
      <div class="reader-title-marquee">
        <span>{{ title || "-" }}</span>
        <span>{{ title || "-" }}</span>
      </div>
    </div>
    <v-btn
      icon="mdi-tune-variant"
      variant="text"
      color="white"
      :class="{ active: settingsOpen }"
      @click="$emit('toggle-settings')"
    />
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: "" },
  settingsOpen: { type: Boolean, default: false },
});

defineEmits(["back", "home", "toggle-settings"]);
</script>

<style scoped>
.reader-topbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  padding: max(10px, env(safe-area-inset-top)) 10px 10px;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.72) 0%, rgba(0, 0, 0, 0.08) 100%);
  display: flex;
  align-items: center;
  gap: 8px;
  color: #fff;
  z-index: 8;
}

.reader-title-wrap {
  flex: 1;
  overflow: hidden;
}

.reader-title-marquee {
  display: inline-flex;
  min-width: 100%;
  white-space: nowrap;
  gap: 48px;
  animation: reader-marquee 14s linear infinite;
}

.reader-title-marquee span {
  font-size: 14px;
  opacity: 0.95;
}

.active {
  color: rgb(var(--v-theme-primary));
}

@keyframes reader-marquee {
  0% {
    transform: translateX(0);
  }
  100% {
    transform: translateX(-50%);
  }
}
</style>
