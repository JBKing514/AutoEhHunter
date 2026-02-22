import { nextTick, ref, watch } from "vue";
import { defineStore } from "pinia";
import { getXpMap } from "../api";

export const useXpStore = defineStore("xp", () => {
  const xpChartEl = ref(null);
  const dendroChartEl = ref(null);

  const xp = ref({
    mode: "read_history",
    time_basis: "read_time",
    max_points: 1800,
    days: 30,
    k: 3,
    topn: 3,
    exclude_language_tags: true,
    exclude_other_tags: false,
    start_date: "",
    end_date: "",
    dendro_page: 1,
    dendro_page_size: 100,
  });
  const xpTimeMode = ref("window");
  const xpResult = ref({ meta: {}, clusters: [], points: [], dendrogram: null });
  const xpExcludeTags = ref([]);
  const newXpExcludeTag = ref("");

  let _t = (k) => k;
  let plotlyInstance = null;
  let xpTimer = null;

  function init(deps = {}) {
    if (typeof deps.t === "function") _t = deps.t;
  }

  function t(key, vars = {}) {
    return _t(key, vars);
  }

  async function ensurePlotly() {
    if (plotlyInstance) return plotlyInstance;
    const mod = await import("plotly.js-dist-min");
    plotlyInstance = mod.default;
    return plotlyInstance;
  }

  async function renderXpChart() {
    if (!xpChartEl.value) return;
    const Plotly = await ensurePlotly();
    const points = xpResult.value.points || [];
    const byCluster = new Map();
    points.forEach((p) => {
      const key = p.cluster || "cluster";
      if (!byCluster.has(key)) byCluster.set(key, []);
      byCluster.get(key).push(p);
    });
    const traces = [];
    byCluster.forEach((arr, name) => {
      traces.push({
        x: arr.map((x) => x.x),
        y: arr.map((x) => x.y),
        text: arr.map((x) => `${x.title}<br>${x.arcid}`),
        mode: "markers",
        type: "scattergl",
        name,
        hovertemplate: "%{text}<extra></extra>",
        marker: { size: 8, opacity: 0.85 },
      });
    });
    await Plotly.react(
      xpChartEl.value,
      traces,
      {
        margin: { l: 40, r: 220, t: 20, b: 60 },
        paper_bgcolor: "#ffffff",
        plot_bgcolor: "#ffffff",
        legend: { orientation: "v", x: 1.02, y: 1, xanchor: "left", yanchor: "top" },
        xaxis: { title: xpResult.value.meta?.x_axis_title || "PC1", automargin: true },
        yaxis: { title: xpResult.value.meta?.y_axis_title || "PC2", automargin: true, scaleanchor: "x", scaleratio: 1 },
      },
      { displayModeBar: false, responsive: true },
    );
  }

  async function renderDendrogram() {
    if (!dendroChartEl.value || !xpResult.value.dendrogram?.available) return;
    const Plotly = await ensurePlotly();
    const fig = xpResult.value.dendrogram.figure;
    if (!fig?.data || !fig?.layout) return;
    await Plotly.react(dendroChartEl.value, fig.data, fig.layout, { displayModeBar: false, responsive: true });
  }

  async function loadXp() {
    const params = {
      ...xp.value,
      exclude_tags: xpExcludeTags.value.join(","),
      start_date: xpTimeMode.value === "range" ? xp.value.start_date : "",
      end_date: xpTimeMode.value === "range" ? xp.value.end_date : "",
      days: xpTimeMode.value === "window" ? xp.value.days : 30,
    };
    xpResult.value = await getXpMap(params);
    await nextTick();
    await renderXpChart();
    await renderDendrogram();
  }

  function addXpExcludeTag() {
    const v = String(newXpExcludeTag.value || "").trim().toLowerCase();
    if (!v) return;
    if (!xpExcludeTags.value.includes(v)) xpExcludeTags.value.push(v);
    newXpExcludeTag.value = "";
  }

  function removeXpExcludeTag(tag) {
    xpExcludeTags.value = xpExcludeTags.value.filter((x) => x !== tag);
  }

  function resetXpConfig() {
    xp.value = {
      ...xp.value,
      days: 30,
      start_date: "",
      end_date: "",
      max_points: 1800,
      k: 3,
      topn: 3,
      exclude_language_tags: true,
      exclude_other_tags: false,
      dendro_page: 1,
      dendro_page_size: 100,
    };
    xpTimeMode.value = "window";
    xpExcludeTags.value = [];
  }

  function scheduleXpRefresh() {
    if (xpTimer) clearTimeout(xpTimer);
    xpTimer = setTimeout(() => {
      loadXp().catch(() => null);
    }, 500);
  }

  function clearXpTimer() {
    if (xpTimer) {
      clearTimeout(xpTimer);
      xpTimer = null;
    }
  }

  watch(
    xp,
    (next) => {
      if (next.mode === "read_history" && next.time_basis !== "read_time") {
        xp.value.time_basis = "read_time";
      }
      if (xpTimeMode.value === "window") {
        xp.value.start_date = "";
        xp.value.end_date = "";
      }
      scheduleXpRefresh();
    },
    { deep: true },
  );

  watch(xpTimeMode, (mode) => {
    if (mode === "window") {
      xp.value.start_date = "";
      xp.value.end_date = "";
    }
    if (mode === "range") {
      xp.value.days = 30;
    }
    scheduleXpRefresh();
  });

  watch(xpExcludeTags, () => scheduleXpRefresh(), { deep: true });

  return {
    xpChartEl,
    dendroChartEl,
    xp,
    xpTimeMode,
    xpResult,
    xpExcludeTags,
    newXpExcludeTag,
    init,
    t,
    ensurePlotly,
    renderXpChart,
    renderDendrogram,
    loadXp,
    addXpExcludeTag,
    removeXpExcludeTag,
    resetXpConfig,
    scheduleXpRefresh,
    clearXpTimer,
  };
});
