export function asBool(v) {
  return String(v).toLowerCase() === "true" || String(v) === "1";
}

export function ensureHexColor(value, fallback) {
  const s = String(value || "").trim();
  return /^#[0-9a-fA-F]{6}$/.test(s) ? s : fallback;
}

export function shiftHex(hex, delta) {
  const clean = String(hex || "").replace("#", "");
  if (!/^[0-9a-fA-F]{6}$/.test(clean)) return hex;
  const num = Number.parseInt(clean, 16);
  const r = Math.max(0, Math.min(255, ((num >> 16) & 255) + delta));
  const g = Math.max(0, Math.min(255, ((num >> 8) & 255) + delta));
  const b = Math.max(0, Math.min(255, (num & 255) + delta));
  return `#${[r, g, b].map((x) => x.toString(16).padStart(2, "0")).join("")}`;
}

export function resolveTimezone(timezoneValue) {
  const tz = String(timezoneValue || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  return tz || "UTC";
}

export function formatDateTime(value, lang, timezoneValue) {
  if (!value || value === "-") return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return new Intl.DateTimeFormat(lang === "zh" ? "zh-CN" : "en-US", {
    timeZone: resolveTimezone(timezoneValue),
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(d);
}

export function formatDateMinute(value, lang, timezoneValue) {
  if (!value || value === "-") return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value).slice(0, 16).replace("T", " ");
  return new Intl.DateTimeFormat(lang === "zh" ? "zh-CN" : "en-US", {
    timeZone: resolveTimezone(timezoneValue),
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);
}

export function parseCookie(raw) {
  const out = { ipb_member_id: "", ipb_pass_hash: "", sk: "", igneous: "" };
  String(raw || "").split(";").forEach((part) => {
    const i = part.indexOf("=");
    if (i < 0) return;
    const k = part.slice(0, i).trim();
    const v = part.slice(i + 1).trim();
    if (k in out) out[k] = v;
  });
  return out;
}

export function buildCookie(parts) {
  return ["ipb_member_id", "ipb_pass_hash", "sk", "igneous"]
    .map((k) => (parts[k] ? `${k}=${parts[k]}` : ""))
    .filter(Boolean)
    .join("; ");
}

export function parseCsv(raw) {
  return String(raw || "")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}
