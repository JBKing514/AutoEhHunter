<template>
  <div
    class="wheel-shell"
    :class="`wheel-${wheelPosition}`"
    :style="shellStyle"
    @touchstart.passive="onWheelTouchStart"
    @touchmove.prevent="onWheelTouchMove"
    @wheel.prevent="onWheelMouse"
  >
    <div v-if="wheelPosition !== 'bottom'" class="wheel-side-mask" :class="`mask-${wheelPosition}`" />

    <div class="wheel-track-clip">
      <div class="wheel-track" :class="`wheel-track-${wheelPosition}`">
        <button
          v-for="entry in wheelPages"
          :key="`w-${entry.page}`"
          class="wheel-item"
          :class="{ active: Number(entry.page) === currentPage }"
          :style="wheelItemStyle(entry.page)"
          @click="$emit('jump-to-page', Number(entry.page || 1))"
        >
          <img :src="String(entry.src || '')" alt="thumb" class="wheel-thumb" loading="lazy" />
          <div class="wheel-mask" />
          <div class="wheel-label-wrap">
            <span class="wheel-label">{{ entry.page }}</span>
          </div>
        </button>
      </div>
    </div>

    <div class="wheel-slider-row" :class="`wheel-slider-${wheelPosition}`">
      <div class="wheel-progress-text">{{ progressText }}</div>
      <v-slider
        :model-value="sliderValue"
        :min="1"
        :max="Math.max(1, totalPages)"
        :step="1"
        :direction="wheelPosition === 'bottom' ? 'horizontal' : 'vertical'"
        :reverse="sliderReverse"
        hide-details
        color="deep-orange"
        thumb-color="white"
        track-color="rgba(255,255,255,0.35)"
        @update:model-value="onSliderChange"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  currentPage: { type: Number, required: true },
  totalPages: { type: Number, required: true },
  wheelPages: { type: Array, default: () => [] },
  wheelPosition: { type: String, default: "bottom" },
  wheelRadius: { type: Number, default: 320 },
  rtl: { type: Boolean, default: false },
});

const emit = defineEmits(["jump-to-page"]);

const touchAnchor = ref({ x: 0, y: 0, accum: 0 });

const sliderValue = computed(() => Number(props.currentPage || 1));

const sliderReverse = computed(() => {
  if (props.wheelPosition === "bottom") return !!props.rtl;
  return true;
});

const progressText = computed(() => `${Number(props.currentPage || 1)} / ${Math.max(1, Number(props.totalPages || 1))}`);

const shellStyle = computed(() => {
  const r = Math.max(120, Number(props.wheelRadius || 320));
  const maskSize = Math.max(170, Math.min(440, Math.round(r * 0.92)));
  return {
    "--edge-mask-size": `${maskSize}px`,
  };
});

function wheelItemStyle(page) {
  const rawOffset = Number(page) - Number(props.currentPage || 1);
  const offset = props.rtl ? -rawOffset : rawOffset;
  const abs = Math.abs(offset);
  const spacing = props.wheelPosition === "bottom" ? 88 : 74;
  const r = Math.max(120, Number(props.wheelRadius || 320));
  const flat = r >= 900000;

  let x = 0;
  let y = 0;
  let rotate = "";
  if (props.wheelPosition === "bottom") {
    x = offset * spacing;
    y = flat ? 0 : (x * x) / (2 * r);
    rotate = ` rotateY(${offset * -2.4}deg)`;
  } else {
    y = -offset * spacing;
    const curve = flat ? 0 : (y * y) / (2 * r);
    x = props.wheelPosition === "left" ? -curve : curve;
    rotate = ` rotateX(${offset * 1.8}deg)`;
  }

  const scale = Math.max(0.56, 1.12 - abs * 0.12);
  const opacity = Math.max(0.28, 1 - abs * 0.16);
  const zIndex = 400 - abs;
  const blur = Math.min(2.4, abs * 0.45);

  return {
    transform: `translate3d(${x}px, ${y}px, 0) scale(${scale})${rotate}`,
    opacity: String(opacity),
    zIndex: String(zIndex),
    filter: `saturate(${1 + Math.max(0, 2 - abs) * 0.08}) blur(${blur}px)`,
  };
}

function onWheelTouchStart(event) {
  const t = event?.changedTouches?.[0];
  if (!t) return;
  touchAnchor.value = { x: Number(t.clientX || 0), y: Number(t.clientY || 0), accum: 0 };
}

function emitStep(step) {
  const next = Math.max(1, Math.min(Number(props.totalPages || 1), Number(props.currentPage || 1) + step));
  if (next !== Number(props.currentPage || 1)) emit("jump-to-page", next);
}

function onSliderChange(v) {
  const raw = Number(v || 1);
  const max = Math.max(1, Number(props.totalPages || 1));
  emit("jump-to-page", Math.max(1, Math.min(max, raw)));
}

function onWheelTouchMove(event) {
  const t = event?.changedTouches?.[0];
  if (!t) return;
  const dx = Number(t.clientX || 0) - touchAnchor.value.x;
  const dy = Number(t.clientY || 0) - touchAnchor.value.y;
  let raw = props.wheelPosition === "bottom" ? -dx : -dy;
  if (props.rtl && props.wheelPosition === "bottom") raw = -raw;
  const total = touchAnchor.value.accum + raw;
  const stepPx = props.wheelPosition === "bottom" ? 18 : 16;
  const step = total > 0 ? Math.floor(total / stepPx) : Math.ceil(total / stepPx);
  if (step !== 0) {
    emitStep(step);
    touchAnchor.value = { x: Number(t.clientX || 0), y: Number(t.clientY || 0), accum: total - step * stepPx };
  }
}

function onWheelMouse(event) {
  const dy = Number(event?.deltaY || 0);
  if (!Number.isFinite(dy) || Math.abs(dy) < 4) return;
  emitStep(dy > 0 ? 1 : -1);
}
</script>

<style scoped>
.wheel-shell {
  position: fixed;
  z-index: 7;
  pointer-events: none;
  display: flex;
}

.wheel-bottom {
  left: 0;
  right: 0;
  bottom: 0;
  padding-bottom: calc(16px + env(safe-area-inset-bottom));
  flex-direction: column;
  gap: 12px;
  background: radial-gradient(ellipse 100% var(--edge-mask-size) at bottom center, rgba(15, 15, 15, 0.82) 0%, rgba(15, 15, 15, 0.36) 40%, transparent 100%);
}

.wheel-left,
.wheel-right {
  top: 50%;
  transform: translateY(-50%);
  align-items: center;
  gap: 12px;
}

.wheel-left {
  left: 0;
  padding-left: calc(16px + env(safe-area-inset-left));
  flex-direction: row;
}

.wheel-right {
  right: 0;
  padding-right: calc(16px + env(safe-area-inset-right));
  flex-direction: row-reverse;
}

.wheel-side-mask {
  position: absolute;
  top: 0;
  bottom: 0;
  width: var(--edge-mask-size);
  pointer-events: none;
  filter: blur(10px);
}

.mask-left {
  left: 0;
  background: radial-gradient(ellipse var(--edge-mask-size) 100% at left center, rgba(96, 96, 96, 0.42) 0%, rgba(96, 96, 96, 0.22) 46%, transparent 100%);
}

.mask-right {
  right: 0;
  background: radial-gradient(ellipse var(--edge-mask-size) 100% at right center, rgba(96, 96, 96, 0.42) 0%, rgba(96, 96, 96, 0.22) 46%, transparent 100%);
}

.wheel-track-clip {
  pointer-events: auto;
  overflow: hidden;
}

.wheel-bottom .wheel-track-clip {
  height: 124px;
}

.wheel-left .wheel-track-clip,
.wheel-right .wheel-track-clip {
  width: 136px;
  height: 360px;
}

.wheel-track {
  position: relative;
}

.wheel-track-bottom {
  height: 118px;
}

.wheel-track-left,
.wheel-track-right {
  width: 130px;
  height: 356px;
}

.wheel-item {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 74px;
  height: 96px;
  margin-left: -37px;
  margin-top: -48px;
  border: 0;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.16);
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.4);
  pointer-events: auto;
  cursor: pointer;
  padding: 0;
  transition: transform 0.25s cubic-bezier(0.25, 1, 0.5, 1), opacity 0.25s ease, filter 0.25s ease;
}

.wheel-mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  transition: background 0.25s ease;
  pointer-events: none;
}

.wheel-item.active .wheel-mask {
  background: rgba(0, 0, 0, 0);
}

.wheel-label-wrap {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.wheel-label {
  background: rgba(12, 14, 20, 0.85);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  padding: 4px 14px;
  border-radius: 999px;
  backdrop-filter: blur(6px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.wheel-item:not(.active) .wheel-label {
  opacity: 0.5;
  transform: scale(0.85);
}

.wheel-item.active {
  outline: 2px solid rgba(255, 255, 255, 0.85);
  box-shadow: 0 0 0 3px rgba(255, 136, 0, 0.45), 0 12px 22px rgba(0, 0, 0, 0.46);
}

.wheel-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.wheel-slider-row {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}

.wheel-slider-bottom {
  width: min(60vw, 560px);
  max-width: calc(100vw - 24px);
  margin: 0 auto;
  flex-direction: column;
}

.wheel-slider-bottom :deep(.v-slider) {
  width: 100%;
}

.wheel-slider-left,
.wheel-slider-right {
  width: auto;
  min-width: 72px;
  height: 280px;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

.wheel-progress-text {
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
  text-align: center;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.8);
}

.wheel-slider-left :deep(.v-slider),
.wheel-slider-right :deep(.v-slider) {
  height: 100%;
  width: 28px;
}

.wheel-slider-left :deep(.v-slider .v-input__control),
.wheel-slider-right :deep(.v-slider .v-input__control) {
  min-height: 100%;
}
</style>
