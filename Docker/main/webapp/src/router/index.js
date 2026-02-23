import { createRouter, createWebHashHistory } from "vue-router";

const routes = [
  {
    path: "/",
    component: () => import("../layouts/MainLayout.vue"),
    children: [
      { path: "", redirect: "/dashboard" },
      { path: "dashboard", name: "dashboard", component: () => import("../views/DashboardPage.vue") },
      { path: "chat", name: "chat", component: () => import("../views/ChatPage.vue") },
      { path: "control", name: "control", component: () => import("../views/ControlPage.vue") },
      { path: "audit", name: "audit", component: () => import("../views/AuditPage.vue") },
      { path: "xp", name: "xp", component: () => import("../views/XpPage.vue") },
      {
        path: "settings",
        component: () => import("../views/SettingsPage.vue"),
        children: [
          { path: "", redirect: { name: "settings-general" } },
          { path: "general", name: "settings-general", component: () => import("../views/settings/GeneralSettingsPage.vue") },
          { path: "eh", name: "settings-eh", component: () => import("../views/settings/EhSettingsPage.vue") },
          { path: "data-clean", name: "settings-data-clean", component: () => import("../views/settings/DataCleanSettingsPage.vue") },
          { path: "search", name: "settings-search", component: () => import("../views/settings/SearchSettingsPage.vue") },
          { path: "recommend", name: "settings-recommend", component: () => import("../views/settings/RecommendSettingsPage.vue") },
          { path: "llm", name: "settings-llm", component: () => import("../views/settings/LlmSettingsPage.vue") },
          { path: "plugins", name: "settings-plugins", component: () => import("../views/settings/PluginsSettingsPage.vue") },
          { path: "other", name: "settings-other", component: () => import("../views/settings/OtherSettingsPage.vue") },
          { path: "developer", name: "settings-developer", component: () => import("../views/settings/DeveloperSettingsPage.vue") },
        ],
      },
    ],
  },
  {
    path: "/login",
    name: "login",
    component: () => import("../views/AuthPage.vue"),
  },
  {
    path: "/:pathMatch(.*)*",
    redirect: "/dashboard",
  },
];

export const router = createRouter({
  history: createWebHashHistory(),
  routes,
});
