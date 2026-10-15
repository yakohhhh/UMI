import { AlertTriangle, ArrowLeft, Bike, CircleDot, Leaf, Navigation, Wind } from "lucide-react";
import { forwardRef } from "react";
import { BAND_COLORS, scoreBand } from "@/lib/score";
import { phoneMap, rideMap } from "./data/geo";

const ring = (score: number, label: string) => {
  const r = 17;
  const c = 2 * Math.PI * r;
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="44" height="44" viewBox="0 0 44 44" aria-hidden>
        <circle cx="22" cy="22" r={r} fill="none" stroke="#1d2a46" strokeWidth="4" />
        <circle
          cx="22"
          cy="22"
          r={r}
          fill="none"
          stroke={BAND_COLORS.dark[scoreBand(score)]}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={`${(score / 100) * c} ${c}`}
          transform="rotate(-90 22 22)"
        />
        <text x="22" y="26.5" textAnchor="middle" fontFamily="var(--font-display)" fontSize="12" fontWeight="600" fill="#f6f4ef">
          {score}
        </text>
      </svg>
      <span className="text-[9px] text-asphalt-300">{label}</span>
    </div>
  );
};

function StatusBar({ time = "08:09" }: { time?: string }) {
  return (
    <div className="flex items-center justify-between px-6 pt-3.5 pb-1 text-[11px] font-semibold text-paper">
      <span className="font-num">{time}</span>
      <span className="flex items-center gap-1">
        <span className="flex items-end gap-[2px]">
          {[4, 6, 8, 10].map((h) => (
            <span key={h} className="w-[3px] rounded-sm bg-paper" style={{ height: h }} />
          ))}
        </span>
        <span className="ml-1 h-[10px] w-[20px] rounded-[3px] border border-paper/70 p-[1.5px]">
          <span className="block h-full w-3/4 rounded-[1px] bg-paper" />
        </span>
      </span>
    </div>
  );
}

export function RideReportScreen() {
  const { ride } = rideMap;
  return (
    <div className="flex h-full flex-col bg-asphalt-900">
      <StatusBar />
      <div className="flex items-center gap-2 px-4 pt-2">
        <ArrowLeft className="size-4 text-asphalt-300" />
        <span className="text-[11px] text-asphalt-300">Feed</span>
      </div>
      <div className="px-4 pt-2">
        <div className="flex items-center gap-1.5 text-[10px] text-asphalt-300">
          <Bike className="size-3 text-signal" /> Today · 07:52 · Gràcia → 22@
        </div>
        <h4 className="mt-1 font-display text-lg font-semibold text-paper">Morning commute</h4>
      </div>
      <div className="relative mx-4 mt-3 h-[150px] overflow-hidden rounded-2xl bg-asphalt-950">
        <svg viewBox={`${phoneMap.w * 0.05} ${phoneMap.h * 0.12} ${phoneMap.w * 0.95} ${phoneMap.h * 0.55}`} className="size-full" aria-hidden>
          {phoneMap.streets.map((s, i) => (
            <path key={i} d={s.d} fill="none" stroke="#26344f" strokeWidth="2" />
          ))}
          <path d={phoneMap.ride} fill="none" stroke="#ff5b1f" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div className="mx-4 mt-3 grid grid-cols-3 gap-2 text-center">
        {[
          [`${ride.distanceKm}`, "km"],
          [`${ride.durationMin}:02`, "min"],
          ["13.9", "km/h"],
        ].map(([v, u]) => (
          <div key={u} className="rounded-xl bg-asphalt-800 py-2">
            <div className="font-num text-sm font-semibold text-paper">{v}</div>
            <div className="text-[9px] text-asphalt-300">{u}</div>
          </div>
        ))}
      </div>
      <div className="mx-4 mt-3 flex justify-between rounded-2xl bg-asphalt-800 px-3 py-2.5">
        {ring(ride.scores.comfort, "Comfort")}
        {ring(ride.scores.safety, "Safety")}
        {ring(ride.scores.air, "Air")}
        {ring(ride.scores.noise, "Noise")}
      </div>
      <ul className="mx-4 mt-3 space-y-1.5">
        {[
          { icon: AlertTriangle, t: "Hard brake", d: "07:59 · Diagonal × Sant Joan", c: "#ff5b1f" },
          { icon: CircleDot, t: "Pothole", d: "08:01 · Av. Diagonal", c: "#f5c542" },
          { icon: Wind, t: "PM2.5 spike", d: "08:05 · Glòries · 34 µg/m³", c: "#ff5b1f" },
        ].map((e) => (
          <li key={e.t} className="flex items-center gap-2 rounded-xl bg-asphalt-800/70 px-2.5 py-2">
            <e.icon className="size-3.5" style={{ color: e.c }} />
            <span className="text-[11px] font-medium text-paper">{e.t}</span>
            <span className="ml-auto text-[9.5px] text-asphalt-300">{e.d}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Street map screen. Path colours are updated imperatively by the showcase when the hour changes. */
export const StreetMapScreen = forwardRef<HTMLDivElement, { hour: number }>(function StreetMapScreen({ hour }, ref) {
  return (
    <div ref={ref} className="relative flex h-full flex-col bg-asphalt-950">
      <StatusBar time="17:58" />
      <div className="mx-4 mt-2 flex items-center justify-between">
        <h4 className="font-display text-base font-semibold text-paper">Street map</h4>
        <span className="rounded-full bg-asphalt-800 px-2 py-0.5 text-[10px] text-asphalt-200">Overall</span>
      </div>
      <div className="relative mt-2 flex-1 overflow-hidden">
        <svg viewBox={`0 0 ${phoneMap.w} ${phoneMap.h}`} className="absolute inset-0 size-full" preserveAspectRatio="xMidYMid slice" aria-hidden>
          {phoneMap.streets.map((s, i) => (
            <path key={i} data-street={i} d={s.d} fill="none" stroke={BAND_COLORS.dark[scoreBand(s.overall[hour])]} strokeWidth="3.2" strokeLinecap="round" />
          ))}
        </svg>
      </div>
      <div className="mx-3 mb-5 rounded-2xl border border-white/10 bg-asphalt-900/90 p-3 backdrop-blur">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-asphalt-300">Hour</span>
          <span className="phone-hour font-num text-sm font-semibold text-paper">{String(hour).padStart(2, "0")}:00</span>
        </div>
        <div className="relative mt-2 h-1.5 rounded-full bg-asphalt-700">
          <div className="phone-hour-fill absolute inset-y-0 left-0 w-full origin-left rounded-full bg-signal" style={{ transform: `scaleX(${hour / 23})` }} />
          <div className="phone-hour-thumb absolute top-1/2 left-0 size-3.5 -translate-y-1/2 rounded-full border-2 border-signal bg-white" style={{ transform: `translate(calc(${(hour / 23) * 236}px - 50%), -50%)` }} />
        </div>
        <div className="mt-2.5 flex justify-between text-[9px] text-asphalt-300">
          <span className="flex items-center gap-1">
            <span className="h-1 w-3 rounded-full bg-score-good" />
            Calm
          </span>
          <span className="flex items-center gap-1">
            <span className="h-1 w-3 rounded-full bg-score-mid" />
            Mixed
          </span>
          <span className="flex items-center gap-1">
            <span className="h-1 w-3 rounded-full bg-score-bad" />
            Stressful
          </span>
        </div>
      </div>
    </div>
  );
});

export function RoutesScreen() {
  return (
    <div className="flex h-full flex-col bg-asphalt-900">
      <StatusBar time="07:41" />
      <div className="mx-4 mt-2">
        <h4 className="font-display text-base font-semibold text-paper">Choose a route</h4>
        <p className="text-[10px] text-asphalt-300">Gràcia → 22@ · leaving now</p>
      </div>
      <div className="relative mx-4 mt-2 h-[176px] overflow-hidden rounded-2xl bg-asphalt-950">
        <svg viewBox={`${phoneMap.w * 0.05} ${phoneMap.h * 0.1} ${phoneMap.w * 0.95} ${phoneMap.h * 0.62}`} className="size-full" aria-hidden>
          {phoneMap.streets.map((s, i) => (
            <path key={i} d={s.d} fill="none" stroke="#1b2740" strokeWidth="2" />
          ))}
          <path d={phoneMap.routes.fastest} fill="none" stroke="#8794ab" strokeWidth="3.5" strokeDasharray="6 5" strokeLinecap="round" />
          <path d={phoneMap.routes.calmest} fill="none" stroke="#ff5b1f" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div className="mx-4 mt-3 space-y-2">
        <div className="rounded-2xl border border-white/8 bg-asphalt-800 p-3">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-paper">
              <Navigation className="size-3.5 text-asphalt-300" /> Fastest · 18 min
            </span>
            <span className="text-[10px] text-asphalt-300">3.7 km</span>
          </div>
          <p className="mt-1 text-[10px] text-asphalt-300">Diagonal · Air 54 · Comfort 66</p>
        </div>
        <div className="route-calm rounded-2xl border border-signal/50 bg-signal/10 p-3">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-paper">
              <Leaf className="size-3.5 text-signal" /> Calmest · 21 min
            </span>
            <span className="rounded-full bg-signal px-1.5 py-0.5 text-[9px] font-semibold text-asphalt-900">+3 min</span>
          </div>
          <p className="mt-1 text-[10px] text-asphalt-200">Air 78 · Comfort 82 · Consell de Cent</p>
          <p className="mt-0.5 text-[10px] text-signal-300">A far calmer ride for 3 extra minutes</p>
        </div>
        <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-asphalt-800 px-3 py-2.5">
          <span className="flex items-center gap-1.5 text-xs font-semibold text-paper">
            <Wind className="size-3.5 text-score-good" /> Cleanest · 20 min
          </span>
          <span className="text-[10px] text-asphalt-300">Air 86 · +2 min</span>
        </div>
      </div>
      <div className="mx-4 mt-auto mb-6">
        <div className="go-calm flex h-11 items-center justify-center rounded-full bg-signal text-sm font-semibold text-asphalt-900">Go calm</div>
      </div>
    </div>
  );
}
