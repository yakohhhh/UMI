"use client";

import { useRef, type ReactNode } from "react";
import { CLIP, ClipFace } from "./clip-device";
import { gsap, ScrollTrigger, useGSAP } from "./motion";

type Layer = {
  id: string;
  label: string;
  detail: string;
  w: number;
  h: number;
  /** vertical offset of the part inside the shell footprint */
  dy?: number;
  thick: number;
  edge: string;
  radius: number;
  art: ReactNode;
};

const Pcb = () => (
  <svg viewBox="0 0 150 226" className="size-full" aria-hidden>
    <defs>
      <linearGradient id="pcb" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#14202f" />
        <stop offset="1" stopColor="#0a121d" />
      </linearGradient>
      <linearGradient id="can" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#d8dee8" />
        <stop offset="1" stopColor="#7d8798" />
      </linearGradient>
    </defs>
    <rect width="150" height="226" rx="30" fill="url(#pcb)" stroke="#c9a24a" strokeOpacity="0.35" />
    <g stroke="#c9a24a" strokeOpacity="0.55" strokeWidth="1.2" fill="none">
      <path d="M20 40h30v20h18M20 60h22v30M130 50h-24v40M30 190h40v-24h30M120 196v-30h-14M44 120H20M106 120h24M75 170v20" />
      <path d="M36 150h18M36 156h18M36 162h18M96 150h18M96 156h18M96 162h18" strokeOpacity="0.4" />
    </g>
    {[[20, 40], [20, 60], [130, 50], [30, 190], [120, 196], [75, 190]].map(([x, y], i) => (
      <circle key={i} cx={x} cy={y} r="2.6" fill="#c9a24a" />
    ))}
    <rect x="43" y="72" width="64" height="72" rx="5" fill="url(#can)" />
    <rect x="47" y="76" width="56" height="64" rx="3" fill="none" stroke="#fff" strokeOpacity="0.4" />
    <text x="75" y="104" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="8.5" fontWeight="600" fill="#2a3242">
      ESP32-S3
    </text>
    <text x="75" y="116" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="6" fill="#4a5568">
      EDGE AI · 240 MHz
    </text>
    <rect x="58" y="24" width="34" height="14" rx="2" fill="#1d2738" stroke="#3a4a66" />
    <rect x="62" y="196" width="26" height="12" rx="3" fill="#2b3446" stroke="#5b6b86" />
  </svg>
);

const Gnss = () => (
  <svg viewBox="0 0 84 84" className="size-full" aria-hidden>
    <rect width="84" height="84" rx="14" fill="#101a29" stroke="#c9a24a" strokeOpacity="0.35" />
    <rect x="12" y="12" width="60" height="60" rx="6" fill="#d9cbb0" />
    <rect x="16" y="16" width="52" height="52" rx="4" fill="#cdbd9e" />
    <rect x="30" y="30" width="24" height="24" rx="2" fill="#e8ecf2" stroke="#9aa6bb" />
    <circle cx="44" cy="40" r="2.6" fill="#7d8798" />
  </svg>
);

const Imu = () => (
  <svg viewBox="0 0 60 60" className="size-full" aria-hidden>
    <rect width="60" height="60" rx="12" fill="#101a29" stroke="#c9a24a" strokeOpacity="0.35" />
    <rect x="17" y="17" width="26" height="26" rx="3" fill="#06090f" stroke="#3a4a66" />
    <circle cx="22" cy="22" r="1.6" fill="#5b6b86" />
    {[0, 1, 2, 3].map((i) => (
      <g key={i} fill="#c9a24a">
        <rect x={20 + i * 6} y="12" width="2.4" height="4" rx="1" />
        <rect x={20 + i * 6} y="44" width="2.4" height="4" rx="1" />
      </g>
    ))}
  </svg>
);

const Pm = () => (
  <svg viewBox="0 0 128 92" className="size-full" aria-hidden>
    <defs>
      <linearGradient id="pmbox" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#c7ced9" />
        <stop offset="1" stopColor="#8a94a5" />
      </linearGradient>
    </defs>
    <rect width="128" height="92" rx="12" fill="url(#pmbox)" />
    <circle cx="40" cy="46" r="26" fill="#1c2433" />
    <circle cx="40" cy="46" r="22" fill="none" stroke="#5b6b86" strokeWidth="1.5" strokeDasharray="3 3" />
    <g stroke="#9aa6bb" strokeWidth="2.6" strokeLinecap="round">
      {[0, 60, 120, 180, 240, 300].map((a) => (
        <path key={a} d="M40 46l0-17" transform={`rotate(${a} 40 46)`} />
      ))}
    </g>
    <circle cx="40" cy="46" r="5" fill="#ff5b1f" />
    {[0, 1, 2, 3, 4].map((i) => (
      <rect key={i} x="80" y={20 + i * 12} width="34" height="5" rx="2.5" fill="#3a4556" />
    ))}
  </svg>
);

const Mic = () => (
  <svg viewBox="0 0 52 52" className="size-full" aria-hidden>
    <rect width="52" height="52" rx="12" fill="#101a29" stroke="#c9a24a" strokeOpacity="0.35" />
    <rect x="12" y="12" width="28" height="28" rx="5" fill="#b8c0cc" />
    <circle cx="26" cy="26" r="4" fill="#1c2433" />
  </svg>
);

const Battery = () => (
  <svg viewBox="0 0 146 208" className="size-full" aria-hidden>
    <defs>
      <linearGradient id="lipo" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#e6ebf2" />
        <stop offset="0.5" stopColor="#b9c2cf" />
        <stop offset="1" stopColor="#8892a3" />
      </linearGradient>
    </defs>
    <rect width="146" height="208" rx="26" fill="url(#lipo)" />
    <rect x="10" y="10" width="126" height="188" rx="20" fill="none" stroke="#fff" strokeOpacity="0.5" />
    <rect x="34" y="78" width="78" height="52" rx="6" fill="#0b1220" />
    <text x="73" y="100" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="9" fontWeight="600" fill="#f6f4ef">
      3.7 V
    </text>
    <text x="73" y="115" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="8" fill="#ff7a47">
      900 mAh
    </text>
  </svg>
);

const LAYERS: Layer[] = [
  { id: "housing", label: "Housing", detail: "Recycled aluminium & polycarbonate · IP54", w: CLIP.w, h: CLIP.h, thick: 10, edge: "#0b111c", radius: CLIP.radius, art: <ClipFace /> },
  { id: "pcb", label: "ESP32-S3 board", detail: "Edge AI scores the ride on the Clip itself", w: 150, h: 226, thick: 4, edge: "#6b5a2c", radius: 30, art: <Pcb /> },
  { id: "gnss", label: "GNSS", detail: "Multi-band GPS + Galileo, street-level fixes", w: 84, h: 84, dy: 58, thick: 6, edge: "#5c5240", radius: 14, art: <Gnss /> },
  { id: "imu", label: "IMU · 6-axis", detail: "Vibration and hard brakes, 100 times a second", w: 60, h: 60, dy: 70, thick: 4, edge: "#0d141f", radius: 12, art: <Imu /> },
  { id: "pm", label: "PM2.5 sensor", detail: "Laser scattering, a reading every 10 s", w: 128, h: 92, dy: 64, thick: 14, edge: "#5d6677", radius: 12, art: <Pm /> },
  { id: "mic", label: "MEMS microphone", detail: "Sound level in dB(A) — never records audio", w: 52, h: 52, dy: 84, thick: 4, edge: "#0d141f", radius: 12, art: <Mic /> },
  { id: "battery", label: "Battery", detail: "900 mAh LiPo · a week of commutes", w: 146, h: 208, thick: 10, edge: "#69717f", radius: 26, art: <Battery /> },
];

const FLUSH_Z = [27, 18, 14, 12, 4, -6, -16];
const EXPLODED_Z = [318, 214, 118, 30, -64, -160, -270];

export function ExplodedView() {
  const root = useRef<HTMLElement>(null);
  const sceneRef = useRef<HTMLDivElement>(null);
  const stackRef = useRef<HTMLDivElement>(null);
  const layerRefs = useRef<(HTMLDivElement | null)[]>([]);
  const labelRefs = useRef<(HTMLDivElement | null)[]>([]);
  const lineRefs = useRef<(SVGLineElement | null)[]>([]);
  const dotRefs = useRef<(SVGCircleElement | null)[]>([]);

  useGSAP(
    () => {
      const scene = sceneRef.current!;
      const state = { rx: 0, rz: 0, scale: 1, explode: 0, shift: 0, labels: LAYERS.map(() => 0) };
      let compact = false;
      let spread = 1;

      const apply = () => {
        const P = 1800;
        const rx = (state.rx * Math.PI) / 180;
        const rz = (state.rz * Math.PI) / 180;
        stackRef.current!.style.transform = `perspective(${P}px) scale(${state.scale}) rotateX(${state.rx}deg) rotateZ(${state.rz}deg)`;
        const sceneW = scene.clientWidth;
        const anchor = stackRef.current!.parentElement!;
        const shiftPx = -state.shift * sceneW * 0.2;
        anchor.style.transform = `translate3d(${shiftPx}px, 0, 0)`;
        // mobile: stack moves to the left third, labels take the right-hand side
        const column = compact ? Math.max(70, sceneW * 0.26) : Math.min(sceneW / 2 - 40, 300);
        const projected = LAYERS.map((l, i) => {
          const z = FLUSH_Z[i] + (EXPLODED_Z[i] * spread - FLUSH_Z[i]) * state.explode;
          const el = layerRefs.current[i];
          if (el) el.style.transform = `translate3d(-50%, calc(-50% + ${l.dy ?? 0}px), ${z}px)`;
          const side = compact ? 1 : i % 2 === 0 ? 1 : -1;
          const x0 = (side * l.w) / 2;
          const y0 = l.dy ?? 0;
          const x1 = x0 * Math.cos(rz) - y0 * Math.sin(rz);
          const y1 = x0 * Math.sin(rz) + y0 * Math.cos(rz);
          const y2 = y1 * Math.cos(rx) - z * Math.sin(rx);
          const z2 = y1 * Math.sin(rx) + z * Math.cos(rx);
          const k = (P / (P - z2)) * state.scale;
          return { side, sx: x1 * k, sy: y2 * k };
        });
        // keep labels on the same side at least 24 px apart
        const labelY = projected.map((p) => p.sy);
        if (compact) for (let i = 1; i < labelY.length; i++) labelY[i] = Math.max(labelY[i], labelY[i - 1] + 26);
        projected.forEach(({ side, sx, sy }, i) => {
          const o = state.labels[i];
          const ly = labelY[i];
          const lx = side > 0 ? column : -column;
          const label = labelRefs.current[i];
          if (label) {
            label.style.opacity = String(o);
            label.style.transform = `translate3d(${lx}px, ${ly}px, 0) translate(${side > 0 ? "0" : "-100%"}, -50%) translateX(${(1 - o) * 14 * side}px)`;
          }
          const line = lineRefs.current[i];
          if (line) {
            const ex = lx - side * 10;
            const startX = sx + side * 6;
            line.setAttribute("x1", String(startX));
            line.setAttribute("y1", String(sy));
            line.setAttribute("x2", String(startX + (ex - startX) * o));
            line.setAttribute("y2", String(sy + (ly - sy) * o));
            line.style.opacity = String(o);
          }
          const dot = dotRefs.current[i];
          if (dot) {
            dot.setAttribute("cx", String(sx));
            dot.setAttribute("cy", String(sy));
            dot.style.opacity = String(o);
          }
        });
      };

      const mm = gsap.matchMedia();
      mm.add({ desktop: "(min-width: 768px)", mobile: "(max-width: 767px)", reduce: "(prefers-reduced-motion: reduce)" }, (ctx) => {
        const { mobile, reduce } = ctx.conditions as { desktop: boolean; mobile: boolean; reduce: boolean };
        compact = mobile;
        spread = mobile ? 0.72 : 1;
        if (reduce) {
          Object.assign(state, { rx: 66, rz: -28, scale: mobile ? 0.72 : 0.92, explode: 1, shift: mobile ? 1 : 0, labels: LAYERS.map(() => 1) });
          apply();
          gsap.set(".xv-final", { opacity: 1 });
          return;
        }
        state.rx = 0;
        state.rz = 0;
        state.scale = mobile ? 0.8 : 1;
        state.explode = 0;
        state.shift = 0;
        state.labels = LAYERS.map(() => 0);
        apply();

        const tl = gsap.timeline({
          defaults: { ease: "power2.inOut", duration: 1 },
          onUpdate: apply,
          scrollTrigger: {
            trigger: root.current,
            start: "top top",
            end: mobile ? "+=220%" : "+=300%",
            pin: true,
            scrub: 1,
            anticipatePin: 1,
          },
        });
        tl.to(state, { rx: 66, rz: -28, scale: mobile ? 0.72 : 0.92, duration: 2 })
          .to(".xv-intro", { opacity: 0, y: -30, duration: 1 }, 1.2)
          .to(state, { explode: 1, duration: 3.6 }, 2)
          .to(state, { shift: mobile ? 1 : 0, duration: 1.6 }, 2)
          .to(".xv-progress", { scaleX: 1, ease: "none", duration: 8.4 }, 0);
        LAYERS.forEach((_, i) => {
          tl.to(state.labels, { [i]: 1, duration: 0.7, ease: "power2.out" }, 2.6 + i * 0.4);
        });
        tl.to({}, { duration: 1.1 }) // hold the exploded state
          .to(state.labels, { ...Object.fromEntries(LAYERS.map((_, i) => [i, 0])), duration: 0.6 }, 7.2)
          .to(state, { explode: 0, shift: 0, rx: 18, rz: -10, scale: mobile ? 0.86 : 1, duration: 1.8 }, 7.2)
          .to(".xv-final", { opacity: 1, y: 0, duration: 0.8 }, 8.4);
        return () => ScrollTrigger.refresh();
      });
    },
    { scope: root },
  );

  return (
    <section ref={root} id="product" aria-labelledby="xv-title" className="relative h-[100svh] overflow-hidden bg-asphalt-900">
      <div aria-hidden className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_55%,rgb(47_127_255/0.10),transparent_60%)]" />
      <div className="xv-intro absolute inset-x-0 top-24 z-10 mx-auto max-w-3xl px-6 text-center sm:top-28">
        <p className="label-mono text-signal">Inside the Clip</p>
        <h2 id="xv-title" className="mt-3 font-display text-4xl font-semibold tracking-tight text-balance text-paper sm:text-6xl">
          Seven sensors. One clip.
        </h2>
        <p className="mx-auto mt-4 max-w-md text-asphalt-200">Scroll to take it apart. Everything that measures your street fits in a matchbox.</p>
      </div>

      <div ref={sceneRef} className="absolute inset-0 [--cx:50%]">
        <div className="absolute [transform-style:preserve-3d]" style={{ left: "var(--cx)", top: "calc(50% + 3vh)" }}>
          <div
            ref={stackRef}
            className="absolute [transform-style:preserve-3d]"
            style={{ width: CLIP.w, height: CLIP.h, left: -CLIP.w / 2, top: -CLIP.h / 2, transform: "perspective(1800px)" }}
          >
            {LAYERS.map((l, i) => (
              <div
                key={l.id}
                ref={(el) => {
                  layerRefs.current[i] = el;
                }}
                className="absolute top-1/2 left-1/2 [transform-style:preserve-3d]"
                style={{ width: l.w, height: l.h, transform: `translate3d(-50%, calc(-50% + ${l.dy ?? 0}px), ${FLUSH_Z[i]}px)` }}
              >
                {Array.from({ length: Math.max(1, Math.round(l.thick / 3)) }).map((_, k) => (
                  <div
                    key={k}
                    aria-hidden
                    className="absolute inset-0"
                    style={{ borderRadius: l.radius, background: l.edge, transform: `translateZ(${-(k + 1) * 3}px)`, filter: `brightness(${1 - k * 0.12})` }}
                  />
                ))}
                <div className="absolute inset-0" style={{ borderRadius: l.radius }}>
                  {l.art}
                </div>
              </div>
            ))}
          </div>

          <svg className="pointer-events-none absolute top-0 left-0 overflow-visible" width="1" height="1" aria-hidden>
            {LAYERS.map((l, i) => (
              <g key={l.id}>
                <line
                  ref={(el) => {
                    lineRefs.current[i] = el;
                  }}
                  stroke="#8794ab"
                  strokeOpacity="0.6"
                  strokeWidth="1"
                  strokeDasharray="2 3"
                  style={{ opacity: 0 }}
                />
                <circle
                  ref={(el) => {
                    dotRefs.current[i] = el;
                  }}
                  r="3"
                  fill="#ff5b1f"
                  style={{ opacity: 0 }}
                />
              </g>
            ))}
          </svg>
          <ol className="pointer-events-none absolute top-0 left-0" aria-label="Components of the UMI Clip">
            {LAYERS.map((l, i) => (
              <li key={l.id}>
                <div
                  ref={(el) => {
                    labelRefs.current[i] = el;
                  }}
                  className={`absolute top-0 left-0 w-max max-w-[150px] opacity-0 sm:max-w-[240px] ${i % 2 === 1 ? "md:text-right" : ""}`}
                >
                  <div className={`flex items-baseline gap-2 ${i % 2 === 1 ? "md:justify-end" : ""}`}>
                    <span className="font-mono text-[10px] text-signal">{String(i + 1).padStart(2, "0")}</span>
                    <span className="font-display text-sm font-semibold text-paper sm:text-base">{l.label}</span>
                  </div>
                  <p className="mt-0.5 hidden text-xs leading-5 text-asphalt-300 sm:block">{l.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <div className="xv-final absolute inset-x-0 bottom-16 z-10 mx-auto max-w-xl translate-y-6 px-6 text-center opacity-0">
        <p className="font-display text-2xl font-semibold text-paper sm:text-3xl">38 g. 53 × 36 × 14 mm.</p>
        <p className="mt-2 text-sm text-asphalt-300">A week of commutes per charge · USB-C · Tool-free clip</p>
      </div>
      <div aria-hidden className="absolute inset-x-0 bottom-0 h-[2px] bg-white/5">
        <div className="xv-progress h-full origin-left scale-x-0 bg-signal/70" />
      </div>
    </section>
  );
}
