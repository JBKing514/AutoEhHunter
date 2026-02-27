<template>
  <v-dialog
    :model-value="modelValue"
    fullscreen
    scrim="rgba(0, 0, 0, 0.45)"
    transition="fade-transition"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="longpress-overlay" @click.self="$emit('update:modelValue', false)">
      <div class="fx-bg" :style="bgStyle" @click="$emit('update:modelValue', false)" />
      <div class="fx-stars">
        <span v-for="star in stars" :key="star.id" class="fx-star" :style="star.style" />
      </div>
      <button class="return-zone" type="button" @click="$emit('update:modelValue', false)">
        {{ t("reader.search.back_to_reader") }}
      </button>

      <div class="search-sheet" @click.stop>
        <div class="d-flex align-center justify-space-between mb-2">
          <div class="text-subtitle-2 text-white">{{ t("reader.search.title") }}</div>
          <v-btn icon="mdi-close" size="small" variant="text" color="white" @click="$emit('update:modelValue', false)" />
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

defineEmits(["update:modelValue"]);

const router = useRouter();
const layoutStore = useLayoutStore();
const settingsStore = useSettingsStore();
const query = ref("");
const searching = ref(false);
const resultItems = ref([]);
const errorText = ref("");
const stars = ref([]);

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
  for (let i = 0; i < 32; i += 1) {
    const size = 8 + Math.random() * 16;
    const left = Math.random() * 100;
    const top = Math.random() * 70;
    const delay = Math.random() * 4;
    const dur = 2.8 + Math.random() * 4.5;
    arr.push({
      id: `s-${i}`,
      style: {
        width: `${size}px`,
        height: `${size}px`,
        left: `${left}%`,
        top: `${top}%`,
        animationDelay: `${delay}s`,
        animationDuration: `${dur}s`,
      },
    });
  }
  stars.value = arr;
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
  filter: blur(24px) saturate(0.72) brightness(0.62);
  transform: scale(1.08);
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
  transform: rotate(45deg);
  opacity: 0.72;
  animation-name: twinkle;
  animation-timing-function: ease-in-out;
  animation-iteration-count: infinite;
}

.fx-star::before,
.fx-star::after {
  content: "";
  position: absolute;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 999px;
}

.fx-star::before {
  inset: 45% 0;
}

.fx-star::after {
  inset: 0 45%;
}

.search-sheet {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 12px 12px calc(12px + env(safe-area-inset-bottom));
  border-radius: 16px 16px 0 0;
  background: rgba(12, 14, 20, 0.86);
  border-top: 1px solid rgba(255, 255, 255, 0.16);
  backdrop-filter: blur(10px);
  max-height: min(62vh, 560px);
  overflow-y: auto;
}

@keyframes twinkle {
  0%, 100% {
    opacity: 0.28;
    transform: rotate(45deg) scale(0.75);
  }
  50% {
    opacity: 0.92;
    transform: rotate(45deg) scale(1.12);
  }
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
}

.result-card {
  overflow: hidden;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.12);
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
