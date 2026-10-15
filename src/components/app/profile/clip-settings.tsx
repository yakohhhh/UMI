"use client";

import { Check, RefreshCw } from "lucide-react";
import { useId, useState } from "react";
import { ClipFace } from "@/components/landing/clip-device";
import { ClipBattery } from "@/components/shell/clip-battery";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Segmented } from "@/components/ui/segmented";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { formatRelative } from "@/lib/format";
import { mockNow } from "@/lib/mock";
import type { ClipStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

function SettingRow({ id, label, detail, checked, onChange, disabled }: { id: string; label: string; detail: string; checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <li className="flex items-center gap-4 py-3">
      <label htmlFor={id} className="min-w-0 flex-1 cursor-pointer">
        <span className="block text-sm font-medium text-fg">{label}</span>
        <span className="block text-xs text-fg-muted">{detail}</span>
      </label>
      <Switch id={id} checked={checked} onCheckedChange={onChange} disabled={disabled} />
    </li>
  );
}

/** Device status, sensors and recording preferences. */
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

  return (
    <Card id="clip" className="scroll-mt-24">
      <CardHeader>
        <div>
          <CardTitle>UMI Clip</CardTitle>
          <p className="mt-0.5 text-xs text-fg-muted">Your sensor, its battery and what it records</p>
        </div>
        <span className="inline-flex items-center gap-1.5 text-xs text-good">
          <span className="size-1.5 rounded-full bg-good-fill" aria-hidden /> Connected
        </span>
      </CardHeader>
      <CardContent>
        {!clip ? (
          <Skeleton className="h-64" />
        ) : (
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
              <p className="mt-1 text-[11px] text-fg-subtle">GNSS can't be turned off: every measurement needs a position.</p>

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
        )}
      </CardContent>
    </Card>
  );
}
