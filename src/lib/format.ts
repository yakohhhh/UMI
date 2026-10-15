/** Formatting helpers. Dates are always rendered in Barcelona time. */

export const TIME_ZONE = "Europe/Madrid";
const LOCALE = "en-GB";

const numberFmt = new Intl.NumberFormat("en-US");

export function formatNumber(n: number, digits = 0) {
  return new Intl.NumberFormat("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
}

export function formatInt(n: number) {
  return numberFmt.format(Math.round(n));
}

export function formatKm(meters: number, digits = 1) {
  return `${(meters / 1000).toFixed(digits)} km`;
}

export function formatDuration(seconds: number, style: "short" | "clock" = "short") {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.round(seconds % 60);
  if (style === "clock") {
    return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
  }
  if (h) return `${h}h ${String(m).padStart(2, "0")}m`;
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

/** Pace in min/km for runs. */
export function formatPace(distanceM: number, seconds: number) {
  if (!distanceM) return "–";
  const secPerKm = seconds / (distanceM / 1000);
  const m = Math.floor(secPerKm / 60);
  const s = Math.round(secPerKm % 60);
  return `${m}:${String(s === 60 ? 0 : s).padStart(2, "0")} /km`;
}

export function formatSpeed(kmh: number) {
  return `${kmh.toFixed(1)} km/h`;
}

function partsInTz(date: Date) {
  const f = new Intl.DateTimeFormat(LOCALE, {
    timeZone: TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const p = Object.fromEntries(f.formatToParts(date).map((x) => [x.type, x.value]));
  return { y: +p.year, mo: +p.month, d: +p.day, h: +p.hour % 24, mi: +p.minute };
}

export function formatTime(iso: string | Date) {
  const { h, mi } = partsInTz(new Date(iso));
  return `${String(h).padStart(2, "0")}:${String(mi).padStart(2, "0")}`;
}

/** "Today at 07:52", "Yesterday at 18:31", "Mon 12 Oct at 07:54". */
export function formatActivityDate(iso: string, now = new Date()) {
  const date = new Date(iso);
  const a = partsInTz(date);
  const b = partsInTz(now);
  const dayA = Date.UTC(a.y, a.mo - 1, a.d);
  const dayB = Date.UTC(b.y, b.mo - 1, b.d);
  const diff = Math.round((dayB - dayA) / 86_400_000);
  const time = formatTime(date);
  if (diff === 0) return `Today at ${time}`;
  if (diff === 1) return `Yesterday at ${time}`;
  const day = new Intl.DateTimeFormat(LOCALE, { timeZone: TIME_ZONE, weekday: "short", day: "numeric", month: "short" }).format(date);
  return `${day} at ${time}`;
}

export function formatDay(iso: string, opts: Intl.DateTimeFormatOptions = { weekday: "long", day: "numeric", month: "long" }) {
  return new Intl.DateTimeFormat(LOCALE, { timeZone: TIME_ZONE, ...opts }).format(new Date(iso));
}

export function formatMonth(isoMonth: string, style: "short" | "long" = "short") {
  const [y, m] = isoMonth.split("-").map(Number);
  return new Intl.DateTimeFormat(LOCALE, { month: style, year: style === "long" ? "numeric" : undefined, timeZone: "UTC" }).format(
    new Date(Date.UTC(y, m - 1, 15)),
  );
}

export function formatRelative(iso: string, now = new Date()) {
  const diffS = Math.max(0, (now.getTime() - new Date(iso).getTime()) / 1000);
  if (diffS < 60) return "just now";
  if (diffS < 3600) return `${Math.floor(diffS / 60)} min ago`;
  if (diffS < 86_400) return `${Math.floor(diffS / 3600)} h ago`;
  const d = Math.floor(diffS / 86_400);
  return d === 1 ? "yesterday" : `${d} days ago`;
}

export function hourLabel(h: number) {
  return `${String(h).padStart(2, "0")}:00`;
}

export function greeting(now = new Date()) {
  const { h } = partsInTz(now);
  if (h < 5) return "Good night";
  if (h < 12) return "Good morning";
  if (h < 19) return "Good afternoon";
  return "Good evening";
}

export function signed(n: number, digits = 0, unit = "") {
  const v = n.toFixed(digits);
  return `${n > 0 ? "+" : n < 0 ? "−" : "±"}${v.replace("-", "")}${unit}`;
}

/** "1 ride", "1,257 rides". */
export function pluralize(n: number, one: string, many = `${one}s`) {
  return `${formatInt(n)} ${plural(n, one, many)}`;
}

/** The word only: "ride" / "rides". */
export function plural(n: number, one: string, many = `${one}s`) {
  return n === 1 ? one : many;
}

/** Compact street name for dense lists: "Pg. de Sant Joan", "Av. Diagonal", "Consell de Cent". */
export function shortStreet(name: string) {
  return name
    .replace(/^Carrer (de la |de l'|de l’|del |dels |de |d'|d’)?/, "")
    .replace(/^Avinguda (de la |de l'|del |de )?/, "Av. ")
    .replace(/^Passeig (de la |del |de )?/, (_m, p: string | undefined) => `Pg. ${p ?? ""}`)
    .replace(/^Gran Via de les Corts Catalanes$/, "Gran Via")
    .replace(/^./, (c) => c.toUpperCase());
}
