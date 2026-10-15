"use client";

import { Download, FileJson, Loader2, ShieldCheck, Trash2 } from "lucide-react";
import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { CURRENT_ATHLETE_ID, getClipStatus, getCurrentAthlete, getExposure, getFeed, getProfileStats } from "@/lib/api";
import { mockNow } from "@/lib/mock";

/** Builds the Data Act / GDPR export from the same API the app uses, and hands it to the browser. */
async function buildExport() {
  const [athlete, profile, feed, exposure, clip] = await Promise.all([getCurrentAthlete(), getProfileStats(), getFeed(), getExposure(), getClipStatus()]);
  const own = feed.filter((a) => a.athleteId === CURRENT_ATHLETE_ID);
  const payload = {
    format: "umi-export/1",
    exportedAt: mockNow().toISOString(),
    legalBasis: ["GDPR Art. 15 & 20 (access, portability)", "EU Data Act Art. 4 (user access to connected-product data)"],
    athlete,
    device: { name: clip.name, serial: clip.serial, firmware: clip.firmware },
    profile,
    activities: own.map(({ preview: _preview, kudoedBy: _kudoedBy, ...a }) => a),
    exposure: { thresholds: exposure.thresholds, days: exposure.days },
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `umi-export-${CURRENT_ATHLETE_ID}-${payload.exportedAt.slice(0, 10)}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
  return { activities: own.length, days: exposure.days.length, bytes: blob.size };
}

function ExportDialog() {
  const [state, setState] = useState<"idle" | "working" | { activities: number; days: number; bytes: number }>("idle");
  return (
    <Dialog onOpenChange={(o) => !o && setState("idle")}>
      <DialogTrigger asChild>
        <Button variant="secondary" size="sm">
          <Download /> Export my data
        </Button>
      </DialogTrigger>
      <DialogContent title="Export your data" description="A complete, machine-readable copy of everything your Clip and the app recorded about you.">
        <ul className="space-y-2.5 text-sm">
          {[
            "Every ride and run, with scores and events",
            "12 months of PM2.5 and noise exposure, day by day",
            "Your profile, records, badges and Clip settings",
          ].map((t) => (
            <li key={t} className="flex gap-2.5">
              <FileJson className="mt-0.5 size-4 shrink-0 text-fg-subtle" aria-hidden />
              <span className="text-fg">{t}</span>
            </li>
          ))}
        </ul>
        <p className="mt-4 rounded-xl bg-surface-2 px-3 py-2.5 text-xs leading-5 text-fg-muted">
          JSON format, ready to import elsewhere. This is your right under the GDPR (Art. 15 and 20) and the EU Data Act for connected devices.
        </p>
        <div className="mt-5 flex items-center justify-end gap-2" aria-live="polite">
          {typeof state === "object" ? (
            <p className="mr-auto text-xs text-good">
              Downloaded: {state.activities} activities, {state.days} days · {Math.round(state.bytes / 1024)} KB
            </p>
          ) : null}
          <DialogClose asChild>
            <Button variant="ghost" size="sm">
              Close
            </Button>
          </DialogClose>
          <Button
            size="sm"
            disabled={state === "working"}
            onClick={async () => {
              setState("working");
              try {
                setState(await buildExport());
              } catch {
                setState("idle");
              }
            }}
          >
            {state === "working" ? <Loader2 className="animate-spin" /> : <Download />}
            {state === "working" ? "Preparing…" : typeof state === "object" ? "Download again" : "Download JSON"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function DeleteDialog() {
  const id = useId();
  const [text, setText] = useState("");
  const [done, setDone] = useState(false);
  return (
    <Dialog
      onOpenChange={(o) => {
        if (!o) {
          setText("");
          setDone(false);
        }
      }}
    >
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="text-bad hover:bg-bad/10 hover:text-bad">
          <Trash2 /> Delete account
        </Button>
      </DialogTrigger>
      <DialogContent title="Delete your account?" description="Your rides, exposure history, profile and Clip pairing are erased within 30 days. Street scores you helped build stay, because they are anonymised and can't be traced back to you.">
        {done ? (
          <p role="status" className="rounded-xl bg-surface-2 px-3 py-3 text-sm text-fg">
            Request received. We sent a confirmation to your email; you have 14 days to change your mind.
          </p>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (text.trim().toUpperCase() === "DELETE") setDone(true);
            }}
          >
            <label htmlFor={id} className="text-sm text-fg-muted">
              Type <span className="font-mono font-semibold text-fg">DELETE</span> to confirm
            </label>
            <input
              id={id}
              value={text}
              onChange={(e) => setText(e.target.value)}
              autoComplete="off"
              className="mt-2 h-10 w-full rounded-xl border border-line bg-surface-2 px-3 font-mono text-sm text-fg focus-visible:border-bad/50 focus-visible:ring-4 focus-visible:ring-bad/15 focus-visible:outline-none"
            />
            <div className="mt-5 flex justify-end gap-2">
              <DialogClose asChild>
                <Button variant="ghost" size="sm" type="button">
                  Keep my account
                </Button>
              </DialogClose>
              <Button size="sm" type="submit" disabled={text.trim().toUpperCase() !== "DELETE"} className="bg-signal-ink text-white shadow-none hover:bg-signal-ink/90 active:bg-signal-ink">
                Delete everything
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function PrivacySettings() {
  const id = useId();
  const [share, setShare] = useState(true);
  const [publicProfile, setPublicProfile] = useState(true);
  const [trim, setTrim] = useState(200);

  return (
    <Card id="privacy" className="scroll-mt-24">
      <CardHeader>
        <div>
          <CardTitle>Privacy & data</CardTitle>
          <p className="mt-0.5 text-xs text-fg-muted">You decide what leaves your phone</p>
        </div>
        <ShieldCheck className="size-4 text-fg-subtle" aria-hidden />
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-line">
          <li className="flex items-start gap-4 pb-4">
            <label htmlFor={`${id}-share`} className="min-w-0 flex-1 cursor-pointer">
              <span className="block text-sm font-medium text-fg">Help Barcelona fix its streets</span>
              <span className="mt-0.5 block text-xs leading-5 text-fg-muted">
                Share anonymised street measurements with City Insights. Data is aggregated with at least 5 other riders and never includes your identity.
              </span>
            </label>
            <Switch id={`${id}-share`} checked={share} onCheckedChange={setShare} className="mt-0.5" />
          </li>
          <li className="flex items-start gap-4 py-4">
            <label htmlFor={`${id}-public`} className="min-w-0 flex-1 cursor-pointer">
              <span className="block text-sm font-medium text-fg">Public profile</span>
              <span className="mt-0.5 block text-xs leading-5 text-fg-muted">People you don't follow can see your rides and badges. Exposure data is always private.</span>
            </label>
            <Switch id={`${id}-public`} checked={publicProfile} onCheckedChange={setPublicProfile} className="mt-0.5" />
          </li>
          <li className="py-4">
            <div className="flex items-baseline justify-between gap-4">
              <span id={`${id}-trim-label`} className="text-sm font-medium text-fg">
                Hide the start and end of every trip
              </span>
              <span className="font-num text-sm font-semibold text-fg" aria-live="polite">
                {trim} m
              </span>
            </div>
            <p className="mt-0.5 text-xs leading-5 text-fg-muted">Trimmed on your phone, before upload, so your home and office never appear in any dataset.</p>
            <Slider
              value={[trim]}
              onValueChange={([v]) => setTrim(v)}
              min={100}
              max={500}
              step={50}
              thumbLabel="Distance hidden at the start and end of trips, in metres"
              aria-labelledby={`${id}-trim-label`}
              className="mt-3"
            />
            <div className="mt-1 flex justify-between font-mono text-[10px] text-fg-subtle" aria-hidden>
              <span>100 m</span>
              <span>500 m</span>
            </div>
          </li>
        </ul>
        <div className="mt-2 rounded-2xl border border-line bg-surface-2/60 p-4">
          <p className="text-sm font-medium text-fg">Your data, your copy</p>
          <p className="mt-1 text-xs leading-5 text-fg-muted">
            Under the GDPR and the EU Data Act, the data your Clip generates is yours: download it at any time or have it erased.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <ExportDialog />
            <DeleteDialog />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
