/**
 * Micro-visualisations for the four dimensions. Pure SVG + CSS keyframes that
 * only animate transform and opacity.
 */

function signal(width: number, seed: number, rough: (x: number) => number) {
  let s = seed;
  const rnd = () => {
    s = (s * 16807) % 2147483647;
    return s / 2147483647;
  };
  const pts: string[] = [];
  for (let x = 0; x <= width; x += 4) {
    const a = rough(x % 480);
    const y = 100 + (rnd() - 0.5) * a + Math.sin(x / 9) * a * 0.18;
    pts.push(`${x === 0 ? "M" : "L"}${x} ${y.toFixed(1)}`);
  }
  return pts.join("");
}

// Smooth asphalt, then a cobbled stretch, then a patched lane — repeated twice for a seamless loop.
const roughness = (x: number) => (x < 150 ? 14 : x < 300 ? 92 : x < 360 ? 46 : 18);
const VIB = signal(960, 7, roughness);

export function VibrationViz() {
  return (
    <svg viewBox="0 0 480 220" className="h-auto w-full" aria-hidden>
      <defs>
        <linearGradient id="vib-fade" x1="0" x2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0" />
          <stop offset="0.12" stopColor="#fff" stopOpacity="1" />
          <stop offset="0.88" stopColor="#fff" stopOpacity="1" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
        <mask id="vib-mask">
          <rect width="480" height="220" fill="url(#vib-fade)" />
        </mask>
      </defs>
      {[40, 70, 100, 130, 160].map((y) => (
        <line key={y} x1="0" x2="480" y1={y} y2={y} stroke="#fff" strokeOpacity={y === 100 ? 0.12 : 0.05} />
      ))}
      <g mask="url(#vib-mask)">
        <g className="viz-marquee">
          <path d={VIB} fill="none" stroke="#3d9bff" strokeWidth="2" strokeLinejoin="round" />
        </g>
      </g>
      <g className="viz-marquee" opacity="0.9">
        {/* surface strip under the trace */}
        {Array.from({ length: 2 }).map((_, k) => (
          <g key={k} transform={`translate(${k * 480} 0)`}>
            <rect x="0" y="190" width="150" height="12" rx="6" fill="#26344f" />
            {Array.from({ length: 13 }).map((__, i) => (
              <rect key={i} x={152 + i * 11.5} y="189" width="9" height="14" rx="3" fill="#3a4a66" />
            ))}
            <rect x="302" y="190" width="58" height="12" rx="6" fill="#33405a" />
            <rect x="362" y="190" width="118" height="12" rx="6" fill="#26344f" />
          </g>
        ))}
      </g>
      <text x="16" y="24" fontFamily="var(--font-mono)" fontSize="11" fill="#8794ab" letterSpacing="1">
        VIBRATION · m/s² RMS
      </text>
    </svg>
  );
}

export function BrakeViz() {
  // speed (km/h) over 12 s, with a hard stop at t = 6 s
  const speed = [22, 22.5, 23, 22.6, 22.8, 21.5, 9, 3.5, 6, 11, 15, 18, 19.5];
  const x = (i: number) => 24 + i * 36;
  const y = (v: number) => 150 - v * 4.6;
  const line = speed.map((v, i) => `${i ? "L" : "M"}${x(i)} ${y(v)}`).join("");
  const decel = speed.map((v, i) => (i ? Math.max(0, ((speed[i - 1] - v) / 3.6) * 0.95) : 0));
  return (
    <svg viewBox="0 0 480 220" className="h-auto w-full" aria-hidden>
      {[50, 90, 130].map((yy) => (
        <line key={yy} x1="24" x2="456" y1={yy} y2={yy} stroke="#fff" strokeOpacity="0.05" />
      ))}
      <path d={line} fill="none" stroke="#f6f4ef" strokeOpacity="0.85" strokeWidth="2.4" strokeLinejoin="round" pathLength={1} className="viz-draw" />
      {decel.map((d, i) =>
        d > 0.2 ? (
          <rect
            key={i}
            x={x(i) - 9}
            y={210 - d * 13}
            width="18"
            height={d * 13}
            rx="4"
            fill={d > 3 ? "#ff5b1f" : "#5b6b86"}
            className="viz-grow"
            style={{ animationDelay: `${0.6 + i * 0.05}s` }}
          />
        ) : null,
      )}
      <line x1="24" x2="456" y1={210 - 3 * 13} y2={210 - 3 * 13} stroke="#ff5b1f" strokeOpacity="0.6" strokeDasharray="4 4" />
      <text x="456" y={205 - 3 * 13} textAnchor="end" fontFamily="var(--font-mono)" fontSize="10" fill="#ff7a47">
        3 m/s² THRESHOLD
      </text>
      <g className="viz-pop">
        <circle cx={x(6)} cy={y(9)} r="14" fill="#ff5b1f" fillOpacity="0.2" className="viz-ping" style={{ transformBox: "fill-box", transformOrigin: "center" }} />
        <circle cx={x(6)} cy={y(9)} r="5" fill="#ff5b1f" />
        <text x={x(6) + 14} y={y(9) - 12} fontFamily="var(--font-display)" fontSize="18" fontWeight="600" fill="#f6f4ef">
          −4.1 m/s²
        </text>
      </g>
      <text x="24" y="24" fontFamily="var(--font-mono)" fontSize="11" fill="#8794ab" letterSpacing="1">
        SPEED · DECELERATION
      </text>
    </svg>
  );
}

const PARTICLES = Array.from({ length: 64 }, (_, i) => {
  const r = (n: number) => {
    const v = Math.sin(i * 12.9898 + n * 78.233) * 43758.5453;
    return v - Math.floor(v);
  };
  const dense = i < 40; // traffic side is denser
  return {
    x: dense ? 30 + r(1) * 230 : 230 + r(1) * 220,
    y: 40 + r(2) * 150,
    size: 1.6 + r(3) * 3.4,
    dur: 5 + r(4) * 6,
    delay: -r(5) * 8,
    o: 0.35 + r(6) * 0.6,
  };
});

export function ParticlesViz() {
  return (
    <svg viewBox="0 0 480 220" className="h-auto w-full" aria-hidden>
      <defs>
        <radialGradient id="pm-haze" cx="0.3" cy="0.55" r="0.5">
          <stop offset="0" stopColor="#ff5b1f" stopOpacity="0.22" />
          <stop offset="1" stopColor="#ff5b1f" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="480" height="220" fill="url(#pm-haze)" />
      {PARTICLES.map((p, i) => (
        <circle
          key={i}
          cx={p.x}
          cy={p.y}
          r={p.size}
          fill={i % 5 === 0 ? "#ff7a47" : "#b6c0d0"}
          opacity={p.o}
          className="viz-drift"
          style={{ animationDuration: `${p.dur}s`, animationDelay: `${p.delay}s` }}
        />
      ))}
      <g fontFamily="var(--font-mono)" fontSize="11" letterSpacing="1">
        <text x="24" y="24" fill="#8794ab">
          PM2.5 · µg/m³
        </text>
        <text x="40" y="208" fill="#ff7a47">
          8:00 · 21
        </text>
        <text x="330" y="208" fill="#3d9bff">
          15:00 · 11
        </text>
      </g>
    </svg>
  );
}

const BARS = Array.from({ length: 36 }, (_, i) => ({
  h: 20 + Math.abs(Math.sin(i * 0.7) * 60 + Math.sin(i * 1.9) * 30),
  dur: 0.9 + ((i * 37) % 10) / 10,
  delay: -((i * 13) % 10) / 10,
}));

export function NoiseViz() {
  return (
    <svg viewBox="0 0 480 220" className="h-auto w-full" aria-hidden>
      <line x1="24" x2="456" y1="120" y2="120" stroke="#fff" strokeOpacity="0.08" />
      {BARS.map((b, i) => (
        <rect
          key={i}
          x={28 + i * 12}
          y={120 - b.h / 2}
          width="6"
          height={b.h}
          rx="3"
          fill={b.h > 70 ? "#f5c542" : "#8794ab"}
          className="viz-eq"
          style={{ animationDuration: `${b.dur}s`, animationDelay: `${b.delay}s`, transformBox: "fill-box", transformOrigin: "center" }}
        />
      ))}
      <g fontFamily="var(--font-mono)" fontSize="11" letterSpacing="1">
        <text x="24" y="24" fill="#8794ab">
          SOUND LEVEL · dB(A)
        </text>
      </g>
      <g transform="translate(24 192)">
        <rect width="432" height="6" rx="3" fill="#1b2740" />
        <rect width="259" height="6" rx="3" fill="#f5c542" />
        <rect x="140" y="-5" width="2" height="16" rx="1" fill="#3d9bff" />
        <text x="146" y="20" fontFamily="var(--font-mono)" fontSize="10" fill="#3d9bff">
          WHO 53
        </text>
        <text x="262" y="20" fontFamily="var(--font-mono)" fontSize="10" fill="#f5c542">
          68
        </text>
      </g>
    </svg>
  );
}
