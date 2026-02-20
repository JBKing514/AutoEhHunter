import en from "./en.json";
import zh from "./zh.json";

const dict = { en, zh };

export function getInitialLang() {
  const fromStorage = (localStorage.getItem("autoeh_lang") || "").toLowerCase();
  if (fromStorage === "en" || fromStorage === "zh") return fromStorage;
  return "zh";
}

export function setLang(lang) {
  const next = lang === "en" ? "en" : "zh";
  localStorage.setItem("autoeh_lang", next);
  return next;
}

export function t(lang, key, vars = {}) {
  const base = dict[lang] || dict.zh;
  const fallback = dict.en;
  let text = base[key] || fallback[key] || key;
  Object.entries(vars).forEach(([k, v]) => {
    text = text.replaceAll(`{${k}}`, String(v));
  });
  return text;
}
