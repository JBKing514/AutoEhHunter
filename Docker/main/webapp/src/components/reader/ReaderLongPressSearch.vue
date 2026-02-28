<template>
  <v-dialog
    :model-value="modelValue"
    fullscreen
    scrim="rgba(0, 0, 0, 0.45)"
    transition="fade-transition"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="longpress-overlay" :class="{ 'overlay-open': modelValue }" @click.self="$emit('update:modelValue', false)">
      <div class="fx-bg" :style="bgStyle" @click="$emit('update:modelValue', false)" />
      <div class="fx-aura" />
      <div class="fx-noise" />
      <div class="fx-stars">
        <svg
          v-for="star in stars"
          :key="star.id"
          class="fx-star"
          :style="star.style"
          viewBox="0 0 24 24"
        >
          <path d="M12 0C12 6.627 17.373 12 24 12C17.373 12 12 17.373 12 24C12 17.373 6.627 12 0 12C6.627 12 12 6.627 12 0Z" fill="currentColor" />
        </svg>
      </div>
      <button class="return-zone" type="button" @click="$emit('update:modelValue', false)">
        {{ t("reader.search.back_to_reader") }}
      </button>

      <div
        ref="sheetRef"
        class="search-sheet"
        @click.stop
        @pointerdown="onSheetPointerDown"
        @pointermove="onSheetPointerMove"
        @pointerup="onSheetPointerUp"
        @pointercancel="onSheetPointerUp"
      >
        <div class="d-flex align-center justify-space-between mb-2">
          <div class="text-subtitle-2">{{ t("reader.search.title") }}</div>
          <v-btn icon="mdi-close" size="small" variant="text" @click="$emit('update:modelValue', false)" />
        </div>

        <v-text-field
          v-model="query"
          density="compact"
          variant="outlined"
          color="primary"
          hide-details
          class="mb-2"
          :label="t('reader.search.query')"
          @keyup.enter="runHybridSearch"
        />

        <div class="d-flex ga-2 mb-3">
          <v-btn color="primary" variant="tonal" :loading="searching" @click="runImageSearch">{{ t("reader.search.image") }}</v-btn>
          <v-btn color="deep-orange" variant="tonal" :loading="searching" @click="runHybridSearch">{{ t("reader.search.hybrid") }}</v-btn>
        </div>

        <v-progress-linear v-if="searching" indeterminate color="primary" class="mb-2" />

        <v-alert v-if="errorText" type="warning" variant="tonal" density="compact" class="mb-2">{{ errorText }}</v-alert>

        <div v-if="!searching && resultItems.length" class="result-grid">
          <v-card v-for="item in resultItems" :key="item.id" class="result-card" variant="flat" @click="openItem(item)">
            <div class="result-cover-wrap">
              <img v-if="item.thumb_url" :src="item.thumb_url" class="result-cover" alt="cover" loading="lazy" />
              <div v-else class="result-cover result-fallback"><v-icon>mdi-image-outline</v-icon></div>
            </div>
            <div class="pa-2">
              <div class="text-body-2 text-truncate">{{ item.title || item.title_jpn || item.id }}</div>
              <div class="text-caption text-medium-emphasis text-truncate">{{ item.source === "works" ? "LRR" : "EH" }}</div>
            </div>
          </v-card>
        </div>

        <div v-else-if="!searching" class="text-caption text-medium-emphasis py-2">
          {{ t("reader.search.hint") }}
        </div>
      </div>
    </div>
  </v-dialog>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { searchByImageUpload } from "../../api";
import { useLayoutStore } from "../../stores/layoutStore";
import { useSettingsStore } from "../../stores/settingsStore";

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  arcid: { type: String, default: "" },
  currentPage: { type: Number, default: 1 },
  currentImageSrc: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue"]);

const router = useRouter();
const layoutStore = useLayoutStore();
const settingsStore = useSettingsStore();
const query = ref("");
const searching = ref(false);
const resultItems = ref([]);
const errorText = ref("");
const stars = ref([]);
const sheetRef = ref(null);
const dragState = ref({ active: false, startY: 0, translateY: 0 });

const t = (key, vars = {}) => layoutStore.t(key, vars);

function getMixedWeights() {
  let tw = Number(settingsStore.config?.SEARCH_MIXED_TEXT_WEIGHT ?? 0.5);
  let vw = Number(settingsStore.config?.SEARCH_MIXED_VISUAL_WEIGHT ?? 0.5);
  if (!Number.isFinite(tw)) tw = 0.5;
  if (!Number.isFinite(vw)) vw = 0.5;
  tw = Math.max(0, tw);
  vw = Math.max(0, vw);
  if (tw + vw <= 0) {
    tw = 0.5;
    vw = 0.5;
  }
  return { textWeight: tw, visualWeight: vw };
}

function openItem(item) {
  const source = String(item?.source || "").toLowerCase();
  const worksArcid = String(item?.arcid || "").trim();
  if (source === "works") {
    const byId = String(item?.id || "").trim();
    const fallbackArcid = byId.startsWith("works:") ? byId.slice("works:".length) : "";
    const arcid = worksArcid || fallbackArcid;
    if (arcid) {
      router.push({ name: "reader", params: { arcid: String(arcid) }, query: { page: "1" } }).catch(() => null);
      return;
    }
  }
  if (source === "works" && !worksArcid) {
    return;
  }
  const url = String(item?.ex_url || item?.eh_url || "").trim();
  if (url && typeof window !== "undefined") {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

async function getCurrentImageFile() {
  const src = String(props.currentImageSrc || "").trim();
  if (!src) throw new Error("empty image src");
  const resp = await fetch(src, { cache: "no-store" });
  if (!resp.ok) throw new Error(`image fetch failed: ${resp.status}`);
  const blob = await resp.blob();
  const ext = String(blob.type || "image/jpeg").split("/")[1] || "jpg";
  return new File([blob], `reader-page-${Date.now()}.${ext}`, { type: blob.type || "image/jpeg" });
}

async function runImageSearch() {
  searching.value = true;
  errorText.value = "";
  try {
    const file = await getCurrentImageFile();
    const resUp = await searchByImageUpload(file, { scope: "both", limit: 18 });
    const items = Array.isArray(resUp?.items) ? resUp.items : [];
    resultItems.value = items;
    if (!items.length) errorText.value = t("reader.search.empty");
  } catch (err) {
    errorText.value = String(err?.message || err || "search failed");
    resultItems.value = [];
  } finally {
    searching.value = false;
  }
}

async function runHybridSearch() {
  const q = String(query.value || "").trim();
  searching.value = true;
  errorText.value = "";
  try {
    const { textWeight, visualWeight } = getMixedWeights();
    const file = await getCurrentImageFile();
    const resUp = await searchByImageUpload(file, {
      scope: "both",
      limit: 18,
      query: q,
      text_weight: textWeight,
      visual_weight: visualWeight,
    });
    const items = Array.isArray(resUp?.items) ? resUp.items : [];
    resultItems.value = items;
    if (!items.length) errorText.value = t("reader.search.empty");
  } catch (err) {
    errorText.value = String(err?.message || err || "search failed");
    resultItems.value = [];
  } finally {
    searching.value = false;
  }
}

const bgStyle = computed(() => ({
  backgroundImage: `url(${String(props.currentImageSrc || "")})`,
}));

function buildStars() {
  const arr = [];
  const colors = ["#FFFFFF", "#8AB4F8", "#C58AF9", "#FDE293"];
  for (let i = 0; i < 28; i += 1) {
    const size = 12 + Math.random() * 20;
    const left = Math.random() * 100;
    const top = Math.random() * 70;
    const delay = Math.random() * 3;
    const dur = 2.5 + Math.random() * 3;
    const color = colors[Math.floor(Math.random() * colors.length)];
    arr.push({
      id: `s-${i}`,
      style: {
        width: `${size}px`,
        height: `${size}px`,
        left: `${left}%`,
        top: `${top}%`,
        color,
        animationDelay: `${delay}s`,
        animationDuration: `${dur}s`,
      },
    });
  }
  stars.value = arr;
}

function onSheetPointerDown(event) {
  if (event?.pointerType === "mouse" && Number(event?.button) !== 0) return;
  if (sheetRef.value && Number(sheetRef.value.scrollTop || 0) > 0) return;
  dragState.value = {
    active: true,
    startY: Number(event?.clientY || 0),
    translateY: 0,
  };
  const el = sheetRef.value;
  if (el) {
    el.style.transition = "none";
  }
}

function onSheetPointerMove(event) {
  if (!dragState.value.active) return;
  const dy = Number(event?.clientY || 0) - dragState.value.startY;
  const offset = Math.max(0, dy);
  dragState.value.translateY = offset;
  const el = sheetRef.value;
  if (el) {
    el.style.transform = `translateY(${offset}px)`;
  }
}

function onSheetPointerUp() {
  if (!dragState.value.active) return;
  const moved = Number(dragState.value.translateY || 0);
  dragState.value = { active: false, startY: 0, translateY: 0 };
  const el = sheetRef.value;
  if (el) {
    el.style.transition = "transform 220ms ease";
    el.style.transform = "translateY(0)";
  }
  if (moved > 120) {
    emitClose();
  }
}

function emitClose() {
  query.value = "";
  resultItems.value = [];
  errorText.value = "";
  searching.value = false;
  emit("update:modelValue", false);
}

watch(() => props.modelValue, (open) => {
  if (typeof window === "undefined") return;
  if (open) {
    buildStars();
    runImageSearch().catch(() => null);
  }
});

onMounted(() => {
  if (props.modelValue) buildStars();
});
</script>

<style scoped>
.longpress-overlay {
  position: fixed;
  inset: 0;
  overflow: hidden;
  background: rgba(2, 8, 20, 0.68);
}

.fx-bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  background-size: cover;
  background-position: center;
  filter: blur(32px) saturate(1.2) brightness(0.4);
  transform: scale(1.1);
  opacity: 0;
}

.overlay-open .fx-bg {
  animation: bg-in 240ms ease-out forwards;
}

.fx-aura {
  position: absolute;
  inset: -20%;
  width: 140%;
  height: 140%;
  background:
    radial-gradient(circle at 30% 30%, rgba(138, 180, 248, 0.25) 0%, transparent 40%),
    radial-gradient(circle at 70% 60%, rgba(197, 138, 249, 0.2) 0%, transparent 40%),
    radial-gradient(circle at 50% 80%, rgba(253, 226, 147, 0.15) 0%, transparent 40%);
  mix-blend-mode: color-dodge;
  pointer-events: none;
  animation: aura-drift 12s ease-in-out infinite alternate;
}

.fx-noise {
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
  opacity: 0.04;
  pointer-events: none;
  mix-blend-mode: overlay;
}

.fx-stars {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.return-zone {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  bottom: min(62vh, 560px);
  margin-bottom: 10px;
  border: 1px solid rgba(255, 255, 255, 0.28);
  background: rgba(0, 0, 0, 0.36);
  color: #fff;
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 12px;
  backdrop-filter: blur(6px);
}

.fx-star {
  position: absolute;
  opacity: 0;
  animation-name: ai-twinkle;
  animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  animation-iteration-count: infinite;
  filter: drop-shadow(0 0 8px currentColor);
}

.search-sheet {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 12px 12px calc(12px + env(safe-area-inset-bottom));
  border-radius: 16px 16px 0 0;
  background: color-mix(in srgb, rgb(var(--v-theme-surface)) 88%, transparent);
  border-top: 1px solid color-mix(in srgb, rgb(var(--v-theme-on-surface)) 16%, transparent);
  backdrop-filter: blur(10px);
  max-height: min(62vh, 560px);
  overflow-y: auto;
  color: rgb(var(--v-theme-on-surface));
  transform: translateY(18px);
  opacity: 0;
  animation: sheet-in 300ms cubic-bezier(0.22, 1, 0.36, 1) 160ms forwards;
}

@keyframes bg-in {
  0% {
    opacity: 0;
    filter: blur(12px) saturate(0.9) brightness(0.22);
  }
  100% {
    opacity: 1;
    filter: blur(32px) saturate(1.2) brightness(0.4);
  }
}

@keyframes aura-drift {
  0% {
    transform: rotate(0deg) scale(1);
  }
  50% {
    transform: rotate(3deg) scale(1.05) translate(-2%, 2%);
  }
  100% {
    transform: rotate(-2deg) scale(0.95) translate(2%, -2%);
  }
}

@keyframes ai-twinkle {
  0% {
    opacity: 0;
    transform: scale(0.2) rotate(-15deg);
  }
  50% {
    opacity: 0.9;
    transform: scale(1) rotate(0deg);
  }
  100% {
    opacity: 0;
    transform: scale(0.2) rotate(15deg);
  }
}

@keyframes sheet-in {
  0% {
    transform: translateY(26px);
    opacity: 0;
  }
  100% {
    transform: translateY(0);
    opacity: 1;
  }
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
}

.result-card {
  overflow: hidden;
  background: color-mix(in srgb, rgb(var(--v-theme-surface-variant)) 42%, transparent);
  border: 1px solid color-mix(in srgb, rgb(var(--v-theme-on-surface)) 14%, transparent);
  cursor: pointer;
}

.result-cover-wrap {
  aspect-ratio: 0.72;
  background: rgba(0, 0, 0, 0.35);
}

.result-cover {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.result-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.8);
}
</style>
