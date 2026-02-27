import { nextTick, ref } from "vue";

export function useContinuousScroll({ continuousRootRef, currentPageRef, onPageChange }) {
  const continuousPageRefs = ref([]);
  let scrollRaf = 0;

  function setContinuousPageRef(el, index) {
    if (!el) return;
    continuousPageRefs.value[index] = el;
  }

  function resetContinuousPageRefs() {
    continuousPageRefs.value = [];
  }

  function scrollToContinuousPage(page) {
    nextTick(() => {
      const root = continuousRootRef?.value;
      const el = continuousPageRefs.value[Number(page) - 1];
      if (!root || !el) return;
      const top = Number(el.offsetTop || 0);
      root.scrollTo({ top, behavior: "smooth" });
    });
  }

  function updateCurrentPageFromContinuous() {
    const root = continuousRootRef?.value;
    if (!root) return;
    const rootTop = Number(root.getBoundingClientRect().top || 0);
    let bestPage = Number(currentPageRef?.value || 1);
    let bestDist = Number.POSITIVE_INFINITY;

    for (let i = 0; i < continuousPageRefs.value.length; i += 1) {
      const el = continuousPageRefs.value[i];
      if (!el) continue;
      const y = Number(el.getBoundingClientRect().top || 0) - rootTop;
      const dist = Math.abs(y);
      if (dist < bestDist) {
        bestDist = dist;
        bestPage = i + 1;
      }
    }

    if (bestPage !== Number(currentPageRef?.value || 1) && typeof onPageChange === "function") {
      onPageChange(bestPage);
    }
  }

  function onContinuousScroll() {
    if (scrollRaf) return;
    scrollRaf = window.requestAnimationFrame(() => {
      scrollRaf = 0;
      updateCurrentPageFromContinuous();
    });
  }

  function disposeContinuousScroll() {
    if (scrollRaf) {
      window.cancelAnimationFrame(scrollRaf);
      scrollRaf = 0;
    }
  }

  return {
    setContinuousPageRef,
    resetContinuousPageRefs,
    scrollToContinuousPage,
    onContinuousScroll,
    disposeContinuousScroll,
  };
}
