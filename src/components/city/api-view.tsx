"use client";

import { Check, Copy, Eye, EyeOff, KeyRound, Lock, RefreshCw, ShieldCheck, Timer, UsersRound } from "lucide-react";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorState } from "@/components/data/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Segmented } from "@/components/ui/segmented";
import { Skeleton } from "@/components/ui/skeleton";
import { getApiUsage } from "@/lib/api";
import { formatDay, formatInt } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";
import { cn } from "@/lib/utils";
import { PageHeader } from "./page-header";

const BASE = "https://api.umi.city";

const SAMPLE_RESPONSE = `{
  "type": "FeatureCollection",
  "period": { "from": "2026-09-15", "to": "2026-10-15" },
  "aggregation": { "minRiders": 5, "tripEndsTrimmedM": 200 },
  "features": [
    {
      "type": "Feature",
      "id": "seg-034",
      "properties": {
        "street": "Carrer d'Aragó",
        "from": "Nàpols",
        "to": "Marina",
        "district": "Eixample",
        "hour": 8,
        "riders": 1284,
        "scores": { "comfort": 61, "safety": 42, "air": 47, "noise": 31 },
        "surfaceIndex": 24,
        "pm25": { "mean": 20.6, "p90": 27.9, "unit": "µg/m³" },
        "noise": { "mean": 70.8, "unit": "dB(A)" },
        "hardBrakes": 37
      },
      "geometry": {
        "type": "LineString",
        "coordinates": [[2.18241, 41.39934], [2.18712, 41.40291]]
      }
    }
  ]
}`;

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label={copied ? "Copied" : label}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1600);
        } catch {
          setCopied(false);
        }
      }}
    >
      {copied ? <Check className="text-good" /> : <Copy />}
    </Button>
  );
}

function CodeBlock({ code, label, language }: { code: string; label: string; language: string }) {
  return (
    <figure className="overflow-hidden rounded-xl border border-line bg-asphalt-950 text-paper">
      <figcaption className="flex items-center justify-between border-b border-white/10 px-3 py-1.5">
        <span className="label-mono text-[10px] text-asphalt-300">{label}</span>
        <span className="dark">
          <CopyButton text={code} label={`Copy ${label.toLowerCase()}`} />
        </span>
      </figcaption>
      <pre className="max-h-[420px] overflow-auto p-4 font-mono text-[12px] leading-5" tabIndex={0} aria-label={`${label}, ${language}`}>
        <code>{code}</code>
      </pre>
    </figure>
  );
}

const PRIVACY = [
  { icon: Lock, title: "Trimmed on the phone", body: "The first and last 200 m of every trip are cut before upload, so homes and workplaces never reach our servers." },
  { icon: UsersRound, title: "k ≥ 5 riders", body: "A street segment and hour is published only once at least 5 different riders crossed it in the period." },
  { icon: Timer, title: "Hourly aggregates", body: "The API serves means and percentiles per segment and hour. Individual traces and timestamps are never exposed." },
  { icon: ShieldCheck, title: "Opt-in, GDPR-native", body: "Riders choose to share with the city and can withdraw at any time; EU hosting, no resale, Data Act compliant." },
];

export function ApiView() {
  const usage = useApi(getApiUsage);
  const [reveal, setReveal] = useState(false);
  const [lang, setLang] = useState<"curl" | "python" | "js">("curl");
  const u = usage.data;

  const request = useMemo(() => {
    const key = "$UMI_API_KEY";
    const url = `${BASE}/v1/city/segments?bbox=2.16,41.38,2.20,41.41&hour=8&mode=bike&period=30d`;
    if (lang === "curl")
      return [`curl -G "${BASE}/v1/city/segments" \\`, "  -d bbox=2.16,41.38,2.20,41.41 \\", "  -d hour=8 -d mode=bike -d period=30d \\", `  -H "Authorization: Bearer ${key}" \\`, '  -H "Accept: application/geo+json"'].join("\n");
    if (lang === "python")
      return `import os, requests\n\nres = requests.get(\n    "${BASE}/v1/city/segments",\n    params={"bbox": "2.16,41.38,2.20,41.41", "hour": 8, "mode": "bike", "period": "30d"},\n    headers={"Authorization": f"Bearer {os.environ['UMI_API_KEY']}"},\n    timeout=10,\n)\nsegments = res.json()["features"]`;
    return `const res = await fetch(\n  "${url}",\n  { headers: { Authorization: \`Bearer \${process.env.UMI_API_KEY}\` } },\n);\nconst { features } = await res.json();`;
  }, [lang]);

  if (usage.error) {
    return (
      <div className="mx-auto max-w-[1480px] px-4 py-5 sm:px-6">
        <ErrorState error={usage.error} onRetry={usage.retry} />
      </div>
    );
  }

  const masked = u ? `${u.key.slice(0, 12)}${"•".repeat(16)}${u.key.slice(-4)}` : "";
  const pct = u ? Math.round((u.quota.used / u.quota.limit) * 100) : 0;

  return (
    <div className="mx-auto max-w-[1480px] space-y-5 px-4 py-5 sm:px-6">
      <PageHeader
        eyebrow="API · open data"
        title="Plug the street data into your tools"
        description="The same aggregates you see here, as GeoJSON and JSON, for your GIS, your dashboards or your open-data portal."
      />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>API key</CardTitle>
              <p className="mt-0.5 text-xs text-fg-muted">{u?.plan ?? "Loading plan…"}</p>
            </div>
            <Badge variant="lane" size="sm">
              Live
            </Badge>
          </CardHeader>
          <CardContent className="space-y-5">
            {u ? (
              <>
                <div className="flex items-center gap-2 rounded-xl border border-line bg-surface-2 py-1.5 pr-1.5 pl-3">
                  <KeyRound className="size-4 shrink-0 text-fg-subtle" aria-hidden />
                  <code className="min-w-0 flex-1 truncate font-mono text-[13px] text-fg" aria-label={reveal ? "API key" : "API key, hidden"}>
                    {reveal ? u.key : masked}
                  </code>
                  <Button variant="ghost" size="icon-sm" onClick={() => setReveal((r) => !r)} aria-label={reveal ? "Hide the key" : "Reveal the key"} aria-pressed={reveal}>
                    {reveal ? <EyeOff /> : <Eye />}
                  </Button>
                  <CopyButton text={u.key} label="Copy the API key" />
                </div>
                <div className="flex flex-wrap items-center gap-3 text-xs text-fg-muted">
                  <span>Keep it server-side. Rotating it revokes the old key within 60 seconds.</span>
                  <Button variant="secondary" size="sm" className="ml-auto">
                    <RefreshCw /> Rotate key
                  </Button>
                </div>
                <div>
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="font-medium text-fg">Monthly quota</span>
                    <span className="font-num text-fg">
                      {formatInt(u.quota.used)} <span className="text-fg-muted">/ {formatInt(u.quota.limit)} calls</span>
                    </span>
                  </div>
                  <Progress value={u.quota.used} max={u.quota.limit} label="Monthly API quota used" className="mt-2" barClassName={cn(pct > 85 ? "bg-bad-fill" : "bg-lane")} />
                  <p className="mt-1.5 text-xs text-fg-muted">
                    {pct}% used · resets {formatDay(u.quota.resetsAt, { day: "numeric", month: "long" })} · rate limit {u.rateLimit}
                  </p>
                </div>
                <figure aria-label={`API calls per day over the last 14 days, between ${formatInt(Math.min(...u.daily.map((d) => d.calls)))} and ${formatInt(Math.max(...u.daily.map((d) => d.calls)))}.`}>
                  <figcaption className="text-xs font-medium text-fg-muted">Calls per day · last 14 days</figcaption>
                  <div className="mt-2 h-36" aria-hidden>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={u.daily} margin={{ top: 4, right: 0, bottom: 0, left: -18 }}>
                        <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                        <XAxis dataKey="day" tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "var(--fg-subtle)", fontFamily: "var(--font-mono)" }} tickFormatter={(d: string) => d.slice(8)} interval={1} />
                        <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "var(--fg-subtle)", fontFamily: "var(--font-mono)" }} tickFormatter={(v: number) => `${Math.round(v / 1000)}k`} width={40} />
                        <Tooltip
                          cursor={{ fill: "var(--surface-2)", opacity: 0.6 }}
                          isAnimationActive={false}
                          content={({ active, payload }) =>
                            active && payload?.length ? (
                              <div className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs shadow-[var(--shadow-lift)]">
                                {formatDay(`${payload[0].payload.day}T12:00:00Z`, { weekday: "short", day: "numeric", month: "short" })} ·{" "}
                                <span className="font-num font-semibold">{formatInt(Number(payload[0].value))}</span> calls
                              </div>
                            ) : null
                          }
                        />
                        <Bar dataKey="calls" fill="var(--color-lane)" radius={[3, 3, 0, 0]} maxBarSize={22} isAnimationActive={false} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </figure>
              </>
            ) : (
              <Skeleton className="h-72" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Endpoints</CardTitle>
              <p className="mt-0.5 text-xs text-fg-muted">
                Base URL <code className="font-mono text-fg">{BASE}</code>
              </p>
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            {u ? (
              <ul className="divide-y divide-line">
                {u.endpoints.map((e) => (
                  <li key={e.path} className="py-3">
                    <p className="flex items-center gap-2 font-mono text-[12.5px] text-fg">
                      <span className="rounded bg-good-fill/15 px-1.5 py-0.5 text-[10px] font-semibold text-good">{e.method}</span>
                      <span className="truncate">{e.path}</span>
                    </p>
                    <p className="mt-1 text-xs text-fg-muted">{e.description}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <Skeleton className="h-64" />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-wrap gap-3">
          <div>
            <CardTitle>Try it</CardTitle>
            <p className="mt-0.5 text-xs text-fg-muted">Scored segments around Glòries at 08:00, bikes only, last 30 days</p>
          </div>
          <Segmented
            size="sm"
            value={lang}
            onChange={setLang}
            label="Code language"
            options={[
              { value: "curl", label: "cURL" },
              { value: "python", label: "Python" },
              { value: "js", label: "JavaScript" },
            ]}
          />
        </CardHeader>
        <CardContent className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
          <CodeBlock code={request} label="Request" language={lang} />
          <CodeBlock code={SAMPLE_RESPONSE} label="Response · 200 OK" language="JSON" />
        </CardContent>
      </Card>

      <section id="privacy" aria-labelledby="privacy-title" className="scroll-mt-40 rounded-3xl border border-good-fill/25 bg-good-fill/[0.05] p-5 sm:p-7">
        <p className="label-mono flex items-center gap-2 text-good">
          <ShieldCheck className="size-3.5" aria-hidden /> Privacy by design
        </p>
        <h2 id="privacy-title" className="mt-2 font-display text-2xl font-semibold tracking-tight">
          What the city never sees
        </h2>
        <p className="mt-1.5 max-w-2xl text-sm text-fg-muted">
          City Insights is built so that no figure on this dashboard, or in the API, can be traced back to a person.
        </p>
        <ul className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {PRIVACY.map((p) => (
            <li key={p.title} className="rounded-2xl border border-line bg-surface p-4">
              <p.icon className="size-5 text-good" aria-hidden />
              <h3 className="mt-3 text-sm font-semibold text-fg">{p.title}</h3>
              <p className="mt-1 text-xs leading-5 text-fg-muted">{p.body}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
