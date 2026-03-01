<template>
  <div class="reader-root">
    <div
      v-if="readerMode === 'paged'"
      class="reader-stage"
      @click="toggleUi"
      @contextmenu.prevent
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @pointerleave="onPointerUp"
    >
      <transition :name="pageTransitionName" mode="out-in">
        <img
          :key="`p-${currentPage}`"
          :src="pageImageUrl(currentPage)"
          class="reader-image"
          :class="`fit-${fitMode}`"
          alt="page"
          draggable="false"
          @dragstart.prevent
        />
      </transition>

      <div v-if="tapToTurn" class="tap-zones">
        <button class="tap-zone left" @click.stop="onLeftZone" aria-label="Turn from left zone" />
        <button class="tap-zone center" @click.stop="toggleUi" aria-label="Toggle UI" />
        <button class="tap-zone right" @click.stop="onRightZone" aria-label="Turn from right zone" />
      </div>
    </div>

    <div
      v-else
      ref="continuousRoot"
      class="reader-stage continuous-stage"
      @click="toggleUi"
      @contextmenu.prevent
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @pointerleave="onPointerUp"
      @scroll.passive="onContinuousScroll"
    >
      <div class="continuous-list">
        <div
          v-for="page in totalPages"
          :key="`c-${page}`"
          class="continuous-page"
          :ref="(el) => setContinuousPageRef(el, page - 1)"
        >
          <img
            :src="pageImageUrl(page)"
            class="reader-image continuous-image"
            :class="`fit-${fitMode}`"
            alt="page"
            loading="lazy"
            draggable="false"
            @dragstart.prevent
          />
        </div>
      </div>
    </div>

    <v-fade-transition>
      <ReaderTopBar
        v-if="showUi"
        :title="title || arcid"
        :settings-open="showQuickSettings"
        @back="closeReader"
        @home="goHome"
        @toggle-settings="showQuickSettings = !showQuickSettings"
      />
    </v-fade-transition>

    <v-fade-transition>
      <ReaderNavWheel
        v-if="showUi"
        :current-page="currentPage"
        :total-pages="totalPages"
        :wheel-pages="wheelPages"
        :wheel-position="wheelPosition"
        :wheel-radius="wheelRadius"
        :rtl="isRtl"
        @jump-to-page="jumpToPage"
      />
    </v-fade-transition>

    <v-fade-transition>
      <ReaderQuickSettings
        v-if="showUi && showQuickSettings"
        :reader-mode="readerMode"
        :direction="direction"
        :fit-mode="fitMode"
        :wheel-position="wheelPosition"
        :wheel-curve="wheelCurve"
        :page-anim-enabled="pageAnimEnabled"
        @update:reader-mode="readerMode = $event"
        @update:direction="direction = $event"
        @update:fit-mode="fitMode = $event"
        @update:wheel-position="wheelPosition = $event"
        @update:wheel-curve="wheelCurve = $event"
        @update:page-anim-enabled="pageAnimEnabled = $event"
      />
    </v-fade-transition>

    <ReaderLongPressSearch
      v-model="longPressSearchOpen"
      :arcid="arcid"
      :current-page="currentPage"
      :current-image-src="pageImageUrl(currentPage)"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getReaderManifest, postReaderReadEvent } from "../api";
import { useSettingsStore } from "../stores/settingsStore";
import { useViewportFit } from "../composables/useViewportFit";
import { useContinuousScroll } from "../composables/useContinuousScroll";
import ReaderNavWheel from "../components/reader/ReaderNavWheel.vue";
import ReaderTopBar from "../components/reader/ReaderTopBar.vue";
import ReaderQuickSettings from "../components/reader/ReaderQuickSettings.vue";
import ReaderLongPressSearch from "../components/reader/ReaderLongPressSearch.vue";

const route = useRoute();
const router = useRouter();
const settingsStore = useSettingsStore();

const arcid = computed(() => String(route.params.arcid || "").trim());
const title = ref("");
const totalPages = ref(1);
const currentPage = ref(1);
const showUi = ref(false);
const showQuickSettings = ref(false);
const transitionName = ref("reader-slide-next");
const touchStart = ref({ x: 0, y: 0 });
const continuousRoot = ref(null);
const longPressSearchOpen = ref(false);
const longPressTriggered = ref(false);
let longPressTimer = 0;
let lastReadEventAt = 0;

const tapToTurn = computed(() => settingsStore.config?.READER_TAP_TO_TURN !== false);
const swipeEnabled = computed(() => settingsStore.config?.READER_SWIPE_ENABLED !== false);
const preloadCount = computed(() => Math.max(0, Math.min(4, Number(settingsStore.config?.READER_PRELOAD_COUNT ?? 2))));

const readerMode = computed({
  get: () => String(settingsStore.config?.READER_MODE || "paged"),
  set: (v) => {
    settingsStore.config.READER_MODE = String(v || "paged");
  },
});

const direction = computed({
  get: () => String(settingsStore.config?.READER_DIRECTION || "ltr"),
  set: (v) => {
    settingsStore.config.READER_DIRECTION = String(v || "ltr");
  },
});

const fitMode = computed({
  get: () => String(settingsStore.config?.READER_FIT_MODE || "contain"),
  set: (v) => {
    settingsStore.config.READER_FIT_MODE = String(v || "contain");
  },
});

const wheelPosition = computed({
  get: () => String(settingsStore.config?.READER_WHEEL_POSITION || "bottom"),
  set: (v) => {
    settingsStore.config.READER_WHEEL_POSITION = String(v || "bottom");
  },
});

const wheelCurve = computed({
  get: () => {
    const n = Number(settingsStore.config?.READER_WHEEL_CURVE ?? 55);
    if (!Number.isFinite(n)) return 55;
    return Math.max(0, Math.min(100, Math.round(n)));
  },
  set: (v) => {
    const n = Number(v ?? 55);
    settingsStore.config.READER_WHEEL_CURVE = Number.isFinite(n) ? Math.max(0, Math.min(100, Math.round(n))) : 55;
  },
});

const wheelRadius = computed(() => {
  const t = wheelCurve.value / 100;
  const minR = 120;
  const maxR = 1000000;
  return minR * Math.exp(Math.log(maxR / minR) * t);
});
const pageAnimEnabled = computed({
  get: () => settingsStore.config?.READER_PAGE_ANIM_ENABLED !== false,
  set: (v) => {
    settingsStore.config.READER_PAGE_ANIM_ENABLED = !!v;
  },
});
const pageTransitionName = computed(() => (pageAnimEnabled.value ? transitionName.value : ""));

const isRtl = computed(() => direction.value === "rtl");

const wheelPages = computed(() => {
  const out = [];
  const range = 4;
  const max = Math.max(1, totalPages.value);
  for (let p = Math.max(1, currentPage.value - range); p <= Math.min(max, currentPage.value + range); p += 1) {
    out.push({ page: p, src: pageImageUrl(p) });
  }
  return isRtl.value ? out.reverse() : out;
});

const { setContinuousPageRef, resetContinuousPageRefs, scrollToContinuousPage, onContinuousScroll, disposeContinuousScroll } = useContinuousScroll({
  continuousRootRef: continuousRoot,
  currentPageRef: currentPage,
  onPageChange: (nextPage) => {
    currentPage.value = nextPage;
    updateRoutePage();
  },
});

useViewportFit(computed(() => settingsStore.config?.READER_VIEWPORT_FIT_COVER !== false));

function pageImageUrl(page) {
  return `/api/reader/${encodeURIComponent(arcid.value)}/page/${page}`;
}

function pageFromRoute() {
  const p = Number(route.query.page || 1);
  if (!Number.isFinite(p) || p < 1) return 1;
  return Math.floor(p);
}

function toggleFullscreen() {
  if (typeof document === "undefined") return;
  if (!document.fullscreenElement) {
    const el = document.documentElement;
    if (!el || typeof el.requestFullscreen !== "function") return;
    const p = el.requestFullscreen();
    if (p && typeof p.catch === "function") {
      p.catch((err) => {
        console.warn("全屏请求被拒绝:", err);
      });
    }
  } else {
    if (typeof document.exitFullscreen !== "function") return;
    const p = document.exitFullscreen();
    if (p && typeof p.catch === "function") {
      p.catch(() => null);
    }
  }
}

function closeReader() {
  if (typeof window !== "undefined" && window.history.length <= 1) {
    goHome();
    return;
  }
  router.back();
}

function goHome() {
  router.replace({ name: "dashboard" }).catch(() => null);
}

function updateRoutePage() {
  router.replace({
    name: "reader",
    params: { arcid: arcid.value },
    query: { page: String(currentPage.value) },
  }).catch(() => null);
}

function setPage(next, directionHint = 1, opts = {}) {
  const clamped = Math.max(1, Math.min(totalPages.value, Number(next) || 1));
  if (clamped === currentPage.value && !opts.force) return;
  transitionName.value = directionHint >= 0 ? "reader-slide-next" : "reader-slide-prev";
  currentPage.value = clamped;
  if (!opts.skipRoute) updateRoutePage();
  if (readerMode.value === "continuous") scrollToContinuousPage(clamped);
  else preloadNearby();
}

function nextPage() {
  setPage(currentPage.value + 1, isRtl.value ? -1 : 1);
}

function prevPage() {
  setPage(currentPage.value - 1, isRtl.value ? 1 : -1);
}

function onLeftZone() {
  if (longPressTriggered.value) {
    longPressTriggered.value = false;
    return;
  }
  if (isRtl.value) nextPage();
  else prevPage();
}

function onRightZone() {
  if (longPressTriggered.value) {
    longPressTriggered.value = false;
    return;
  }
  if (isRtl.value) prevPage();
  else nextPage();
}

function jumpToPage(page) {
  const p = Number(page || 1);
  if (!Number.isFinite(p)) return;
  const dirHint = p >= currentPage.value ? 1 : -1;
  setPage(p, dirHint);
}

function toggleUi() {
  recordReadEvent("reader-click");
  if (longPressTriggered.value) {
    longPressTriggered.value = false;
    return;
  }
  showUi.value = !showUi.value;
  if (!showUi.value) showQuickSettings.value = false;
}

function clearLongPressTimer() {
  if (longPressTimer) {
    window.clearTimeout(longPressTimer);
    longPressTimer = 0;
  }
}

function onPointerDown(event) {
  if (event?.pointerType === "mouse" && Number(event?.button) !== 0) return;
  touchStart.value = { x: Number(event?.clientX || 0), y: Number(event?.clientY || 0) };
  longPressTriggered.value = false;
  clearLongPressTimer();
  longPressTimer = window.setTimeout(() => {
    longPressTriggered.value = true;
    longPressSearchOpen.value = true;
  }, 520);
}

function onPointerMove(event) {
  if (!longPressTimer) return;
  const dx = Math.abs(Number(event?.clientX || 0) - touchStart.value.x);
  const dy = Math.abs(Number(event?.clientY || 0) - touchStart.value.y);
  if (dx > 15 || dy > 15) clearLongPressTimer();
}

function onPointerUp(event) {
  clearLongPressTimer();
  if (longPressTriggered.value) return;
  recordReadEvent("reader-pointer-up");
  if (!swipeEnabled.value || readerMode.value !== "paged") return;
  if (event?.pointerType !== "touch" && event?.pointerType !== "pen") return;
  const dx = Number(event?.clientX || 0) - touchStart.value.x;
  const dy = Number(event?.clientY || 0) - touchStart.value.y;
  if (Math.abs(dx) < 48 || Math.abs(dx) < Math.abs(dy) * 1.25) return;
  if (dx < 0) {
    if (isRtl.value) prevPage();
    else nextPage();
  } else if (isRtl.value) {
    nextPage();
  } else {
    prevPage();
  }
}

async function recordReadEvent(source = "reader-ui") {
  const nowMs = Date.now();
  if (!arcid.value) return;
  if (nowMs - lastReadEventAt < 15000) return;
  lastReadEventAt = nowMs;
  try {
    await postReaderReadEvent({
      arcid: arcid.value,
      read_time: Math.floor(nowMs / 1000),
      source_file: String(source || "reader-ui"),
      ingested_at: new Date(nowMs).toISOString(),
      raw: {
        arcid: arcid.value,
        page: Number(currentPage.value || 1),
        mode: String(readerMode.value || "paged"),
      },
    });
  } catch {
    // ignore read event failures in reader flow
  }
}

function preloadNearby() {
  const count = preloadCount.value;
  for (let i = 1; i <= count; i += 1) {
    const p1 = currentPage.value + i;
    const p2 = currentPage.value - i;
    if (p1 <= totalPages.value) {
      const img = new Image();
      img.src = pageImageUrl(p1);
    }
    if (p2 >= 1) {
      const img = new Image();
      img.src = pageImageUrl(p2);
    }
  }
}

async function loadManifest() {
  if (!arcid.value) return;
  const res = await getReaderManifest(arcid.value);
  totalPages.value = Math.max(1, Number(res?.page_count || 1));
  title.value = String(res?.title || "");
  currentPage.value = Math.max(1, Math.min(totalPages.value, pageFromRoute()));
  updateRoutePage();
  await nextTick();
  if (readerMode.value === "continuous") scrollToContinuousPage(currentPage.value);
  else preloadNearby();
}

watch(() => route.query.page, () => {
  const p = pageFromRoute();
  if (p !== currentPage.value) {
    const dirHint = p > currentPage.value ? 1 : -1;
    setPage(p, dirHint, { skipRoute: true, force: true });
  }
});

watch(() => route.params.arcid, () => {
  resetContinuousPageRefs();
  loadManifest().catch(() => null);
});

watch(() => readerMode.value, async (next) => {
  await nextTick();
  if (next === "continuous") scrollToContinuousPage(currentPage.value);
  else preloadNearby();
});

onMounted(() => {
  if (typeof document !== "undefined" && !document.fullscreenElement) {
    toggleFullscreen();
  }
  loadManifest().catch(() => null);
});

watch(() => route.fullPath, () => {
  if (route.name !== "reader") {
    disposeContinuousScroll();
  }
});

onBeforeUnmount(() => {
  if (typeof document !== "undefined" && document.fullscreenElement) {
    toggleFullscreen();
  }
  clearLongPressTimer();
  disposeContinuousScroll();
});
</script>

<style scoped>
.reader-root {
  background: #090909;
  min-height: 100dvh;
  height: 100dvh;
  overflow: hidden;
  position: relative;
}

.reader-stage {
  position: relative;
  width: 100%;
  height: 100dvh;
  overflow: hidden;
  touch-action: pan-y;
  -webkit-touch-callout: none;
  user-select: none;
}

.continuous-stage {
  overflow-y: auto;
  overflow-x: hidden;
}

.continuous-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 6px 0 calc(20px + env(safe-area-inset-bottom));
}

.continuous-page {
  min-height: 32px;
}

.reader-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  user-select: none;
  display: block;
  pointer-events: none;
  -webkit-user-drag: none;
  -webkit-touch-callout: none;
}

.continuous-image {
  width: 100%;
  height: auto;
  min-height: 180px;
}

.reader-image.fit-width,
.continuous-image.fit-width {
  width: 100%;
  height: auto;
  min-height: 100%;
}

.reader-image.fit-height,
.continuous-image.fit-height {
  width: auto;
  height: 100%;
  min-width: 100%;
}

.tap-zones {
  position: absolute;
  inset: 0;
  display: grid;
  grid-template-columns: 1fr 2fr 1fr;
}

.tap-zone {
  border: 0;
  background: transparent;
  cursor: pointer;
}

.reader-slide-next-enter-active,
.reader-slide-next-leave-active,
.reader-slide-prev-enter-active,
.reader-slide-prev-leave-active {
  transition: transform 0.2s ease-out, opacity 0.2s ease-out;
}

.reader-slide-next-enter-from {
  transform: translateX(28px);
  opacity: 0.75;
}

.reader-slide-next-leave-to {
  transform: translateX(-28px);
  opacity: 0.75;
}

.reader-slide-prev-enter-from {
  transform: translateX(-28px);
  opacity: 0.75;
}

.reader-slide-prev-leave-to {
  transform: translateX(28px);
  opacity: 0.75;
}
</style>
