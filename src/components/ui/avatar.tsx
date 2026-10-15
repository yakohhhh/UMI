import { cn } from "@/lib/utils";

const GRADIENTS = [
  "from-signal to-[#ff9e78]",
  "from-lane to-[#8cb8ff]",
  "from-[#f5c542] to-[#ff9e78]",
  "from-[#3d9bff] to-[#2fd3b3]",
  "from-[#a78bfa] to-[#3d9bff]",
];

/** Initials avatar (Strava-like default). Colour is stable per name. */
export function Avatar({ name, initials, size = 36, className }: { name: string; initials?: string; size?: number; className?: string }) {
  const hash = [...name].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
  const text = initials ?? name.split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  return (
    <span
      role="img"
      aria-label={name}
      style={{ width: size, height: size, fontSize: Math.max(10, size * 0.36) }}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br font-display font-semibold text-asphalt-900 ring-2 ring-bg",
        GRADIENTS[hash % GRADIENTS.length],
        className,
      )}
    >
      {text}
    </span>
  );
}
