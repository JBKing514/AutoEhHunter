import { defineStore } from "pinia";

export function createModuleStore(id) {
  return defineStore(id, {
    state: () => ({
      module: {},
    }),
    actions: {
      setModule(module) {
        this.module = module || {};
      },
      clearModule() {
        this.module = {};
      },
    },
  });
}
