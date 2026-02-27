import { onBeforeUnmount, onMounted, ref, watch } from "vue";

export function useViewportFit(enabledRef) {
  const oldViewportContent = ref("");

  function applyViewportFitCover() {
    if (typeof document === "undefined") return;
    const meta = document.querySelector("meta[name='viewport']");
    if (!meta) return;
    if (!oldViewportContent.value) {
      oldViewportContent.value = String(meta.getAttribute("content") || "width=device-width, initial-scale=1.0");
    }
    const enabled = enabledRef?.value !== false;
    if (enabled) {
      let next = oldViewportContent.value;
      if (!/viewport-fit\s*=\s*cover/i.test(next)) next = `${next}, viewport-fit=cover`;
      meta.setAttribute("content", next);
    } else {
      const next = oldViewportContent.value.replace(/,?\s*viewport-fit\s*=\s*cover/ig, "").trim();
      meta.setAttribute("content", next || "width=device-width, initial-scale=1.0");
    }
  }

  function restoreViewport() {
    if (typeof document === "undefined") return;
    const meta = document.querySelector("meta[name='viewport']");
    if (!meta) return;
    if (oldViewportContent.value) meta.setAttribute("content", oldViewportContent.value);
  }

  watch(enabledRef, () => {
    applyViewportFitCover();
  });

  onMounted(() => {
    applyViewportFitCover();
  });

  onBeforeUnmount(() => {
    restoreViewport();
  });

  return {
    applyViewportFitCover,
    restoreViewport,
  };
}
