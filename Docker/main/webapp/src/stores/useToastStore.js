import { defineStore } from "pinia";

export const useToastStore = defineStore("toast", {
  state: () => ({
    show: false,
    text: "",
    color: "success",
  }),
  actions: {
    open(text, color = "success") {
      this.text = String(text || "");
      this.color = color;
      this.show = true;
    },
    success(text) {
      this.open(text, "success");
    },
    warning(text) {
      this.open(text, "warning");
    },
    error(text) {
      this.open(text, "error");
    },
    info(text) {
      this.open(text, "info");
    },
    close() {
      this.show = false;
    },
  },
});
