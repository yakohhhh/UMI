"use client";

import { Check, Flag, Mic, RefreshCw, Scale, Undo2, type LucideIcon } from "lucide-react";
import { useId, useState, type ReactNode } from "react";
import { HAZARD_META } from "@/components/app/ride-events";
import { ClipFace } from "@/components/landing/clip-device";
import { ClipBattery } from "@/components/shell/clip-battery";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Segmented } from "@/components/ui/segmented";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { formatRelative } from "@/lib/format";
import { mockNow } from "@/lib/mock";
import type { ClipStatus, HazardKind } from "@/lib/types";
import { cn } from "@/lib/utils";

/** The three gestures of the flag button; `marks` draws the press pattern (dot = tap, bar = hold). */
const GESTURES: { id: string; name: string; does: string; detail: string; icon: LucideIcon; marks: ("tap" | "hold")[] }[] = [
  { id: "press", name: "Press", does: "Flag the spot", detail: "Time, place and a sensor snapshot", icon: Flag, marks: ["tap"] },
  { id: "hold", name: "Hold ~1 s", does: "Say one word", detail: "A 4-second window, with voice keywords on", icon: Mic, marks: ["hold"] },
  { id: "double", name: "Double press", does: "Undo", detail: "Takes back your last flag", icon: Undo2, marks: ["tap", "tap"] },
];

const HAZARD_KINDS = Object.keys(HAZARD_META) as HazardKind[];

function SettingRow({
  id,
  label,
  detail,
  checked,
  onChange,
  disabled,
  children,
}: {
  id: string;
  label: string;
  detail: ReactNode;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  children?: ReactNode;
}) {
  return (
    <li className="py-3">
      <div className="flex items-center gap-4">
        <label htmlFor={id} className="min-w-0 flex-1 cursor-pointer">
          <span className="block text-sm font-medium text-fg">{label}</span>
          <span className="block text-xs leading-5 text-fg-muted">{detail}</span>
        </label>
        <Switch id={id} checked={checked} onCheckedChange={onChange} disabled={disabled} />
      </div>
      {children}
    </li>
  );
}

function FlagButton({ clip, micOn }: { clip: ClipStatus; micOn: boolean }) {
  const id = useId();
  const [prefs, setPrefs] = useState<Partial<ClipStatus["flagging"]>>({});
  const set = (key: "voice" | "chirp" | "warnAhead") => (v: boolean) => setPrefs((p) => ({ ...p, [key]: v }));
  const voice = micOn && (prefs.voice ?? clip.flagging.voice);
  const chirp = prefs.chirp ?? clip.flagging.chirp;
  const warnAhead = prefs.warnAhead ?? clip.flagging.warnAhead;

  return (
    <section id="flag-button" aria-labelledby={`${id}-title`} className="mt-6 grid scroll-mt-32 grid-cols-1 gap-x-6 gap-y-4 border-t border-line pt-6 md:grid-cols-[180px_minmax(0,1fr)]">
      <div>
        <h3 id={`${id}-title`} className="text-sm font-semibold text-fg">
          Flag button
        </h3>
        <p className="mt-1 text-xs leading-5 text-fg-muted">Warn other riders without touching your phone. The press says where; a word, or a tap after the ride, says what.</p>
        <p className="mt-3 flex gap-2 text-[11px] leading-4 text-fg-subtle">
          <Scale className="mt-px size-3.5 shrink-0" aria-hidden />
          <span>No phone, no earphones: Spanish traffic rules ban both on a bike or scooter. Everything happens on the Clip.</span>
        </p>
      </div>

      <div className="min-w-0">
        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-3" aria-label="Flag button gestures">
          {GESTURES.map((g) => (
            <li key={g.id} className="rounded-xl border border-line bg-surface-2/60 p-3">
              <div className="flex items-center justify-between">
                <span className="flex size-8 items-center justify-center rounded-lg bg-surface text-accent-ink" aria-hidden>
                  <g.icon className="size-4" />
                </span>
                <span className="flex items-center gap-1" aria-hidden>
                  {g.marks.map((m, i) => (
                    <span key={i} className={cn("h-2 rounded-full bg-signal", m === "hold" ? "w-7" : "w-2")} />
                  ))}
                </span>
              </div>
              <p className="mt-2.5 label-mono text-fg-subtle">{g.name}</p>
              <p className="text-sm font-semibold text-fg">{g.does}</p>
              <p className="mt-0.5 text-xs text-fg-muted">{g.detail}</p>
            </li>
          ))}
        </ul>

        <ul className="mt-2 divide-y divide-line">
          <SettingRow
            id={`${id}-voice`}
            label="Voice keywords"
            detail={
              <>
                Recognised on the Clip. Audio stays in its memory for 4 seconds and is never stored or sent — only the word, the time and the place.
                {!micOn ? <span className="block text-fg">Turn the microphone on above to use them.</span> : null}
              </>
            }
            checked={voice}
            onChange={set("voice")}
            disabled={!micOn}
          >
            <div className={cn("mt-3 rounded-xl border border-line p-3 transition-opacity", !voice && "opacity-60")}>
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="mr-1 label-mono text-fg-subtle">Understands</span>
                {clip.flagging.languages.map((l) => (
                  <Badge key={l} variant="outline" size="sm">
                    {l}
                  </Badge>
                ))}
              </div>
              <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
                {HAZARD_KINDS.map((kind) => {
                  const m = HAZARD_META[kind];
                  return (
                    <div key={kind} className="flex items-baseline gap-2 text-xs">
                      <dt className="flex w-28 shrink-0 items-center gap-1.5 text-fg">
                        <m.icon className="size-3.5 shrink-0 self-center text-fg-muted" aria-hidden />
                        {m.label}
                      </dt>
                      <dd className="min-w-0 font-mono text-fg-muted">{m.keywords}</dd>
                    </div>
                  );
                })}
              </dl>
              <p className="mt-3 text-[11px] leading-4 text-fg-subtle">
                {voice
                  ? "No word, or one it didn't catch? The flag still lands, and you say what it was after the ride."
                  : "Off: a press still drops the flag, and you say what it was after the ride."}
              </p>
            </div>
          </SettingRow>
          <SettingRow id={`${id}-chirp`} label="Chirp to confirm" detail="A short chirp and an LED blink when a flag is saved, so you never look down" checked={chirp} onChange={set("chirp")} />
          <SettingRow
            id={`${id}-ahead`}
            label="Warn me ahead of verified hazards"
            detail="Two low chirps as you approach one, no phone needed"
            checked={warnAhead}
            onChange={set("warnAhead")}
          />
        </ul>
      </div>
    </section>
  );
}

/** Device status, sensors, the flag button and recording preferences. */
export function ClipSettings({ clip }: { clip?: ClipStatus }) {
  const id = useId();
  const [sensors, setSensors] = useState<Record<string, boolean>>({});
  const [wifiOnly, setWifiOnly] = useState(false);
  const [autoPause, setAutoPause] = useState(true);
  const [mount, setMount] = useState<"handlebar" | "stem" | "bag">("handlebar");
  const [syncState, setSyncState] = useState<"idle" | "syncing" | "done">("idle");

  const sync = () => {
    setSyncState("syncing");
    window.setTimeout(() => setSyncState("done"), 1400);
  };

  const micOn = clip ? (sensors.mic ?? clip.sensors.find((s) => s.id === "mic")?.enabled ?? true) : true;

  return (
    <Card id="clip" className="scroll-mt-32">
      <CardHeader>
        <div>
          <CardTitle>UMI Clip</CardTitle>
          <p className="mt-0.5 text-xs text-fg-muted">Your sensor, its flag button and what it records</p>
        </div>
        <span className="inline-flex items-center gap-1.5 text-xs text-good">
          <span className="size-1.5 rounded-full bg-good-fill" aria-hidden /> Connected
        </span>
      </CardHeader>
      <CardContent>
        {!clip ? (
          <Skeleton className="h-64" />
        ) : (
          <>
            <div className="grid grid-cols-1 gap-6 md:grid-cols-[180px_minmax(0,1fr)]">
              <div className="flex flex-row items-center gap-5 md:flex-col md:items-start">
                <div className="relative w-24 shrink-0 md:w-32">
                  <div aria-hidden className="absolute inset-x-2 -bottom-3 h-6 rounded-full bg-asphalt-950/40 blur-lg" />
                  <ClipFace className="relative h-auto drop-shadow-xl" />
                </div>
                <dl className="grid flex-1 grid-cols-2 content-start gap-x-4 gap-y-2.5 text-xs md:w-full md:flex-none md:grid-cols-1">
                  <div>
                    <dt className="text-fg-muted">Battery</dt>
                    <dd className="mt-0.5 flex items-center gap-2">
                      <ClipBattery level={clip.battery} /> <span className="text-fg-subtle">≈ 5 days</span>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-fg-muted">Last sync</dt>
                    <dd className="mt-0.5 text-fg">{syncState === "done" ? "Just now" : formatRelative(clip.lastSync, mockNow())}</dd>
                  </div>
                  <div>
                    <dt className="text-fg-muted">Firmware</dt>
                    <dd className="mt-0.5 font-mono text-fg">
                      {clip.firmware} <span className="font-sans text-good">· up to date</span>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-fg-muted">Serial</dt>
                    <dd className="mt-0.5 font-mono text-fg">{clip.serial}</dd>
                  </div>
                </dl>
              </div>

              <div className="min-w-0">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="text-sm font-semibold text-fg">Sensors</h3>
                  <Button variant="secondary" size="sm" onClick={sync} disabled={syncState === "syncing"} aria-live="polite">
                    {syncState === "done" ? <Check /> : <RefreshCw className={cn(syncState === "syncing" && "animate-spin")} />}
                    {syncState === "syncing" ? "Syncing…" : syncState === "done" ? "Synced" : "Sync now"}
                  </Button>
                </div>
                <ul className="mt-1 divide-y divide-line">
                  {clip.sensors.map((s) => (
                    <SettingRow
                      key={s.id}
                      id={`${id}-${s.id}`}
                      label={s.label}
                      detail={s.detail}
                      checked={sensors[s.id] ?? s.enabled}
                      onChange={(v) => setSensors((m) => ({ ...m, [s.id]: v }))}
                      disabled={s.id === "gnss"}
                    />
                  ))}
                </ul>
                <p className="mt-1 text-[11px] text-fg-subtle">GNSS can&apos;t be turned off: every measurement needs a position.</p>

                <h3 className="mt-6 text-sm font-semibold text-fg">Recording</h3>
                <ul className="mt-1 divide-y divide-line">
                  <SettingRow id={`${id}-pause`} label="Auto-pause at lights" detail="Stops the clock below 2 km/h, keeps measuring air" checked={autoPause} onChange={setAutoPause} />
                  <SettingRow id={`${id}-wifi`} label="Upload on Wi-Fi only" detail="Rides wait on your phone until you're on Wi-Fi" checked={wifiOnly} onChange={setWifiOnly} />
                </ul>
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-fg">Mounted on</p>
                    <p className="text-xs text-fg-muted">Calibrates the vibration and noise readings</p>
                  </div>
                  <Segmented
                    size="sm"
                    value={mount}
                    onChange={setMount}
                    label="Where the Clip is mounted"
                    options={[
                      { value: "handlebar", label: "Handlebar" },
                      { value: "stem", label: "Stem" },
                      { value: "bag", label: "Bag strap" },
                    ]}
                  />
                </div>
              </div>
            </div>

            <FlagButton clip={clip} micOn={micOn} />
          </>
        )}
      </CardContent>
    </Card>
  );
}
