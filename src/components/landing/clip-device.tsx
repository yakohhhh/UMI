import { useId, type CSSProperties } from "react";
import { cn } from "@/lib/utils";

/**
 * The UMI Clip, built in CSS 3D: a stack of rounded slabs gives the rounded
 * extrusion, the front face carries the detailed SVG. Matchbox proportions
 * (36 × 53 × 14 mm).
 */
export const CLIP = { w: 168, h: 248, d: 58, radius: 38 } as const;

/** Front face: wordmark with the status LED, GNSS window, PM2.5 intake, sealed flag button and mic hole. */
export function ClipFace({ className, glow = true }: { className?: string; glow?: boolean }) {
  // the face is drawn more than once per page: scoped ids keep url(#…) on this copy's own gradients
  const uid = useId().replace(/[^\w-]/g, "");
  const id = (name: string) => `clip-${name}-${uid}`;
  const url = (name: string) => `url(#${id(name)})`;
  return (
    <svg viewBox={`0 0 ${CLIP.w} ${CLIP.h}`} className={cn("block size-full", className)} aria-hidden>
      <defs>
        <linearGradient id={id("body")} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2d384c" />
          <stop offset="0.45" stopColor="#1a2335" />
          <stop offset="1" stopColor="#0d1422" />
        </linearGradient>
        <radialGradient id={id("sheen")} cx="0.22" cy="0.12" r="0.75">
          <stop offset="0" stopColor="#fff" stopOpacity="0.16" />
          <stop offset="0.5" stopColor="#fff" stopOpacity="0.02" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={id("slot")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#03060c" />
          <stop offset="1" stopColor="#141c2c" />
        </linearGradient>
        <radialGradient id={id("led")} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#ffd2bd" />
          <stop offset="0.35" stopColor="#ff7a47" />
          <stop offset="1" stopColor="#ff5b1f" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={id("lens")} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#1e2a40" />
          <stop offset="1" stopColor="#070b14" />
        </linearGradient>
      </defs>
      <rect x="0.5" y="0.5" width={CLIP.w - 1} height={CLIP.h - 1} rx={CLIP.radius} fill={url("body")} />
      <rect x="0.5" y="0.5" width={CLIP.w - 1} height={CLIP.h - 1} rx={CLIP.radius} fill={url("sheen")} />
      <rect x="4" y="4" width={CLIP.w - 8} height={CLIP.h - 8} rx={CLIP.radius - 4} fill="none" stroke="#fff" strokeOpacity="0.07" />
      {/* engraved wordmark — the dot of the i is the status LED */}
      <g transform="translate(51 38) scale(1.32)" fill="none" stroke="#f6f4ef" strokeOpacity="0.78" strokeWidth="3.1" strokeLinecap="round">
        <path d="M3.5 8.5v6a5 5 0 0 0 10 0v-6M13.5 14.5V20" />
        <path d="M20 20V8.5M20 13.4a4.6 4.6 0 0 1 9.2 0V20M29.2 13.4a4.6 4.6 0 0 1 9.2 0V20" />
        <path d="M45.4 11.2V20" />
      </g>
      {glow ? <circle cx={51 + 45.4 * 1.32} cy={38 + 4.2 * 1.32} r="11" fill={url("led")} opacity="0.9" /> : null}
      <circle cx={51 + 45.4 * 1.32} cy={38 + 4.2 * 1.32} r="3.4" fill="#ff5b1f" />
      {/* GNSS / sensor window */}
      <circle cx="84" cy="128" r="30" fill={url("lens")} stroke="#3a4a66" strokeOpacity="0.8" />
      <circle cx="84" cy="128" r="22" fill="none" stroke="#fff" strokeOpacity="0.06" />
      <path d="M66 116a22 22 0 0 1 22-10" fill="none" stroke="#fff" strokeOpacity="0.22" strokeWidth="2" strokeLinecap="round" />
      <text x="84" y="132" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="8" letterSpacing="1.5" fill="#8794ab">
        C1
      </text>
      {/* PM2.5 air intake */}
      {Array.from({ length: 3 }).map((_, r) =>
        Array.from({ length: 7 }).map((__, c) => (
          <rect key={`${r}-${c}`} x={31 + c * 15.6} y={178 + r * 10} width="9" height="3.4" rx="1.7" fill={url("slot")} />
        )),
      )}
      {/* sealed flag button: recessed groove, raised cap, engraved flag (press = flag, hold = one keyword) */}
      <rect x="60" y="210" width="48" height="22" rx="11" fill={url("slot")} stroke="#3a4a66" strokeOpacity="0.5" strokeWidth="0.6" />
      <rect x="62" y="212" width="44" height="18" rx="9" fill={url("body")} stroke="#fff" strokeOpacity="0.1" strokeWidth="0.8" />
      <path d="M71 212.7h26" stroke="#fff" strokeOpacity="0.16" strokeLinecap="round" />
      <g fill="none" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M80.5 226.5v-10h8l-2.1 2.7 2.1 2.7h-8" stroke="#03060c" strokeOpacity="0.7" transform="translate(0 0.7)" />
        <path d="M80.5 226.5v-10h8l-2.1 2.7 2.1 2.7h-8" stroke="#f6f4ef" strokeOpacity="0.62" />
      </g>
      {/* MEMS microphone, beside the button you hold to speak */}
      <circle cx="124" cy="221" r="2.2" fill="#03060c" stroke="#3a4a66" strokeWidth="0.6" />
      {/* light pipe */}
      <rect x="54" y={CLIP.h - 7} width="60" height="2" rx="1" fill="#ff5b1f" opacity="0.55" />
    </svg>
  );
}

export function ClipDevice({ className, style, slabs = 18 }: { className?: string; style?: CSSProperties; slabs?: number }) {
  const step = CLIP.d / (slabs - 1);
  return (
    <div className={cn("relative [transform-style:preserve-3d]", className)} style={{ width: CLIP.w, height: CLIP.h, ...style }}>
      {Array.from({ length: slabs }).map((_, i) => {
        const t = i / (slabs - 1); // 0 = front, 1 = back
        const light = Math.round(46 - t * 30);
        return (
          <div
            key={i}
            aria-hidden
            className="absolute inset-0"
            style={{
              borderRadius: CLIP.radius,
              transform: `translateZ(${CLIP.d / 2 - i * step}px)`,
              background: `linear-gradient(135deg, rgb(${light} ${light + 8} ${light + 22}), rgb(${light - 14} ${light - 8} ${light + 4}))`,
              boxShadow: i === 0 ? "none" : "inset 0 0 0 1px rgb(255 255 255 / 0.05)",
            }}
          />
        );
      })}
      <div className="absolute inset-0" style={{ transform: `translateZ(${CLIP.d / 2 + 0.6}px)` }}>
        <ClipFace />
      </div>
      {/* back: quick-release clip rail */}
      <div
        aria-hidden
        className="absolute inset-0 overflow-hidden"
        style={{ borderRadius: CLIP.radius, transform: `rotateY(180deg) translateZ(${CLIP.d / 2 + 0.6}px)`, background: "linear-gradient(160deg,#1b2436,#0a101b)" }}
      >
        <div className="absolute inset-x-10 top-10 bottom-10 rounded-2xl border border-white/10 bg-white/[0.03]" />
        <div className="absolute top-14 bottom-14 left-1/2 w-6 -translate-x-1/2 rounded-full bg-black/40" />
      </div>
    </div>
  );
}
