#!/usr/bin/env node
/**
 * Generates the mock datasets used by the UMI front-end (src/lib/mock/data).
 *
 * Geometry is anchored on real Barcelona open data (districts, neighbourhoods and
 * census sections from https://github.com/martgnz/bcn-geodata, © Ajuntament de
 * Barcelona, CC BY 4.0). The Cerdà grid is fitted from census boundaries
 * (orientation 45.1°, ~133.4 m pitch); every measurement value is synthetic.
 *
 * Usage: node scripts/generate-mock-data.mjs <path-to-bcn-geodata>
 */
import fs from "node:fs";
import path from "node:path";

const GEO = path.resolve(process.argv[2] || process.env.BCN_GEODATA || "../bcn-geodata");
const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const OUT = path.join(ROOT, "src/lib/mock/data");
const LANDING_OUT = path.join(ROOT, "src/components/landing/data");
fs.mkdirSync(OUT, { recursive: true });
fs.mkdirSync(LANDING_OUT, { recursive: true });

const readJson = (p) => JSON.parse(fs.readFileSync(path.join(GEO, p), "utf8"));

// ------------------------------------------------------------------ random
function mulberry32(seed) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
let rand = mulberry32(20261015);
const rnd = (a = 0, b = 1) => a + (b - a) * rand();
const rint = (a, b) => Math.floor(rnd(a, b + 1));
const pick = (arr) => arr[Math.floor(rand() * arr.length)];
const gauss = () => {
  let u = 0;
  let v = 0;
  while (u === 0) u = rand();
  while (v === 0) v = rand();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
};
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const round = (x, d = 0) => Math.round(x * 10 ** d) / 10 ** d;

// ------------------------------------------------------------------ projection
const LAT0 = 41.39;
const LON0 = 2.17;
const KX = Math.cos((LAT0 * Math.PI) / 180) * 111320;
const KY = 110574;
const BEARING = (45.11 * Math.PI) / 180;
const E1 = [Math.sin(BEARING), Math.cos(BEARING)]; // NE — along streets parallel to the sea
const E2 = [Math.sin(BEARING + Math.PI / 2), Math.cos(BEARING + Math.PI / 2)]; // SE — towards the sea
const proj = ([lng, lat]) => [(lng - LON0) * KX, (lat - LAT0) * KY];
const unproj = ([x, y]) => [LON0 + x / KX, LAT0 + y / KY];
const toUV = (ll) => {
  const [x, y] = proj(ll);
  return [x * E1[0] + y * E1[1], x * E2[0] + y * E2[1]];
};
const fromUV = (u, v) => unproj([u * E1[0] + v * E2[0], u * E1[1] + v * E2[1]]);
const ll5 = ([lng, lat]) => [round(lng, 5), round(lat, 5)];
const distM = (a, b) => {
  const [x1, y1] = proj(a);
  const [x2, y2] = proj(b);
  return Math.hypot(x2 - x1, y2 - y1);
};
const lineLength = (coords) => coords.slice(1).reduce((s, c, i) => s + distM(coords[i], c), 0);

// Avinguda Diagonal, least-squares fit on census boundaries (bearing ≈ 71.7°).
const vDiag = (u) => -152.1 + 0.4989 * (u - 1842.3);
const uDiagAtV = (v) => 1842.3 + (v + 152.1) / 0.4989;

// ------------------------------------------------------------------ polygons
const districtsFc = readJson("districtes/districtes.geojson");
const barrisFc = readJson("barris/barris.geojson");
const cityFc = readJson("terme-municipal/terme-municipal.geojson");

function ringsOf(geom) {
  return geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
}
function pip(pt, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > pt[1] !== yj > pt[1] && pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
function makeArea(features) {
  const polys = features.flatMap((f) => ringsOf(f.geometry).map((p) => p.map((r) => r.map(proj))));
  return (ll) => {
    const pt = proj(ll);
    return polys.some((p) => pip(pt, p[0]) && !p.slice(1).some((h) => pip(pt, h)));
  };
}
const districtByName = Object.fromEntries(districtsFc.features.map((f) => [f.properties.NOM, f]));
const barriByName = Object.fromEntries(barrisFc.features.map((f) => [f.properties.NOM, f]));
const inDistrict = Object.fromEntries(districtsFc.features.map((f) => [f.properties.NOM, makeArea([f])]));
const ZONES = {
  eixample: inDistrict["Eixample"],
  gracia: inDistrict["Gràcia"],
  poblenou: makeArea(
    ["el Parc i la Llacuna del Poblenou", "el Poblenou", "Provençals del Poblenou", "la Vila Olímpica del Poblenou", "Diagonal Mar i el Front Marítim del Poblenou"].map(
      (n) => barriByName[n],
    ),
  ),
  santmarti: inDistrict["Sant Martí"],
  city: makeArea(cityFc.features),
};
function districtOf(ll) {
  for (const f of districtsFc.features) if (inDistrict[f.properties.NOM](ll)) return f.properties.NOM;
  return "Ciutat Vella";
}

// Douglas–Peucker on projected coordinates (closed rings are split in two).
function simplify(coords, tol) {
  if (coords.length < 3) return coords;
  const first = coords[0];
  const last = coords[coords.length - 1];
  if (coords.length > 4 && first[0] === last[0] && first[1] === last[1]) {
    let far = 1;
    let farD = 0;
    for (let i = 1; i < coords.length - 1; i++) {
      const d = distM(first, coords[i]);
      if (d > farD) {
        farD = d;
        far = i;
      }
    }
    const a = simplify(coords.slice(0, far + 1), tol);
    const b = simplify(coords.slice(far), tol);
    return [...a, ...b.slice(1)];
  }
  const pts = coords.map(proj);
  const keep = new Uint8Array(pts.length);
  keep[0] = keep[pts.length - 1] = 1;
  const stack = [[0, pts.length - 1]];
  while (stack.length) {
    const [a, b] = stack.pop();
    let maxD = 0;
    let idx = -1;
    const [ax, ay] = pts[a];
    const [bx, by] = pts[b];
    const dx = bx - ax;
    const dy = by - ay;
    const len = Math.hypot(dx, dy) || 1;
    for (let i = a + 1; i < b; i++) {
      const d = Math.abs(dy * pts[i][0] - dx * pts[i][1] + bx * ay - by * ax) / len;
      if (d > maxD) {
        maxD = d;
        idx = i;
      }
    }
    if (maxD > tol && idx > 0) {
      keep[idx] = 1;
      stack.push([a, idx], [idx, b]);
    }
  }
  return coords.filter((_, i) => keep[i]);
}

// ------------------------------------------------------------------ street model
// Offsets (metres) in the rotated grid frame, fitted from census boundaries.
const A = {
  // streets parallel to the sea (offset v grows towards the sea)
  granvia: { name: "Gran Via de les Corts Catalanes", v: -55.0 },
  diputacio: { name: "Carrer de la Diputació", v: -203.1 },
  consell: { name: "Carrer del Consell de Cent", v: -335.2 },
  arago: { name: "Carrer d'Aragó", v: -469.4 },
  valencia: { name: "Carrer de València", v: -602.8 },
  mallorca: { name: "Carrer de Mallorca", v: -736.2 },
  provenca: { name: "Carrer de Provença", v: -870.6 },
  rossello: { name: "Carrer del Rosselló", v: -1004.7 },
  corsega: { name: "Carrer de Còrsega", v: -1139.4 },
  paris: { name: "Carrer de París", v: -1272.5 },
  londres: { name: "Carrer de Londres", v: -1402.8 },
  casp: { name: "Carrer de Casp", v: 93.0 },
  sepulveda: { name: "Carrer de Sepúlveda", v: 93.0 },
  ausias: { name: "Carrer d'Ausiàs Marc", v: 226.0 },
  floridablanca: { name: "Carrer de Floridablanca", v: 226.0 },
  tanger: { name: "Carrer de Tànger", v: 93.0 },
  sancho: { name: "Carrer de Sancho d'Àvila", v: 226.0 },
  almogavers: { name: "Carrer d'Almogàvers", v: 359.9 },
  pallars: { name: "Carrer de Pallars", v: 495.6 },
  pujades: { name: "Carrer de Pujades", v: 623.9 },
  llull: { name: "Carrer de Llull", v: 763.1 },
  turro: { name: "Carrer de Ramon Turró", v: 894.3 },
};
const B = {
  // streets running towards the sea (offset u grows to the north-east)
  entenca: { name: "Carrer d'Entença", u: -1957.9 },
  rocafort: { name: "Carrer de Rocafort", u: -1823.9 },
  calabria: { name: "Carrer de Calàbria", u: -1690.7 },
  viladomat: { name: "Carrer de Viladomat", u: -1557.8 },
  borrell: { name: "Carrer del Comte Borrell", u: -1423.2 },
  urgell: { name: "Carrer del Comte d'Urgell", u: -1290.7 },
  villarroel: { name: "Carrer de Villarroel", u: -1157.6 },
  casanova: { name: "Carrer de Casanova", u: -1023.4 },
  muntaner: { name: "Carrer de Muntaner", u: -891.7 },
  aribau: { name: "Carrer d'Aribau", u: -757.6 },
  granados: { name: "Carrer d'Enric Granados", u: -623.6 },
  balmes: { name: "Carrer de Balmes", u: -489.9 },
  rambcat: { name: "Rambla de Catalunya", u: -305.0 },
  pgracia: { name: "Passeig de Gràcia", u: -129.2 },
  pauclaris: { name: "Carrer de Pau Claris", u: 46.2 },
  lluria: { name: "Carrer de Roger de Llúria", u: 176.1 },
  bruc: { name: "Carrer del Bruc", u: 309.3 },
  girona: { name: "Carrer de Girona", u: 442.4 },
  bailen: { name: "Carrer de Bailèn", u: 576.3 },
  santjoan: { name: "Passeig de Sant Joan", u: 709.0 },
  sicilia: { name: "Carrer de Sicília", u: 843.2 },
  napols: { name: "Carrer de Nàpols", u: 976.0 },
  rogerflor: { name: "Carrer de Roger de Flor", u: 1110.0 },
  sardenya: { name: "Carrer de Sardenya", u: 1243.0 },
  marina: { name: "Carrer de la Marina", u: 1374.9 },
  lepant: { name: "Carrer de Lepant", u: 1510.2 },
  padilla: { name: "Carrer de Padilla", u: 1643.0 },
  castillejos: { name: "Carrer dels Castillejos", u: 1777.0 },
  cartagena: { name: "Carrer de Cartagena", u: 1911.0 },
  badajoz: { name: "Carrer de Badajoz", u: 2179.3 },
  llacuna: { name: "Carrer de la Llacuna", u: 2312.3 },
  rocboronat: { name: "Carrer de Roc Boronat", u: 2443.7 },
  granada: { name: "Carrer de la Ciutat de Granada", u: 2578.9 },
  rambpoblenou: { name: "Rambla del Poblenou", u: 2709.7 },
};

// Street character: drives the synthetic measurements.
const CHARACTER = {
  "Gran Via de les Corts Catalanes": { kind: "arterial", lane: true },
  "Avinguda Diagonal": { kind: "arterial", lane: true },
  "Carrer d'Aragó": { kind: "arterial", lane: true, fastRough: true },
  "Carrer de Balmes": { kind: "arterial" },
  "Carrer de Muntaner": { kind: "arterial" },
  "Carrer d'Aribau": { kind: "arterial" },
  "Carrer de Casanova": { kind: "arterial" },
  "Carrer de Villarroel": { kind: "arterial", lane: true },
  "Carrer del Comte d'Urgell": { kind: "arterial", lane: true },
  "Carrer de València": { kind: "arterial", lane: true },
  "Carrer de Mallorca": { kind: "arterial" },
  "Carrer de Còrsega": { kind: "arterial" },
  "Carrer de Provença": { kind: "street", lane: true },
  "Carrer del Rosselló": { kind: "street", lane: true },
  "Carrer de la Diputació": { kind: "street", lane: true },
  "Carrer del Consell de Cent": { kind: "green", lane: true },
  "Carrer de Rocafort": { kind: "green" },
  "Carrer del Comte Borrell": { kind: "green", lane: true },
  "Carrer de Girona": { kind: "green", lane: true },
  "Carrer d'Enric Granados": { kind: "green", lane: true },
  "Rambla de Catalunya": { kind: "green" },
  "Passeig de Gràcia": { kind: "boulevard", lane: true },
  "Passeig de Sant Joan": { kind: "boulevard", lane: true, morningSmog: true },
  "Carrer de la Marina": { kind: "arterial", lane: true },
  "Carrer de Sardenya": { kind: "street", lane: true },
  "Carrer de Sicília": { kind: "street", lane: true },
  "Carrer de Pau Claris": { kind: "arterial" },
  "Carrer de Roger de Llúria": { kind: "arterial" },
  "Carrer de Bailèn": { kind: "street", lane: true },
  "Carrer de Lepant": { kind: "street" },
  "Carrer de Cartagena": { kind: "street", lane: true },
  "Carrer de Pallars": { kind: "street", lane: true, rough: true },
  "Carrer de Pujades": { kind: "green", lane: true },
  "Carrer d'Almogàvers": { kind: "green", lane: true },
  "Carrer de Sancho d'Àvila": { kind: "green" },
  "Carrer de la Llacuna": { kind: "street", lane: true },
  "Carrer de Roc Boronat": { kind: "green", lane: true },
  "Rambla del Poblenou": { kind: "green" },
  "Carrer de Llull": { kind: "street", lane: true, rough: true },
  "Carrer de Badajoz": { kind: "street" },
  "Carrer de Tànger": { kind: "street", lane: true },
  "La Rambla": { kind: "promenade", cobbles: true, nightlife: true },
  "Via Laietana": { kind: "arterial", lane: true },
  "Avinguda del Paral·lel": { kind: "arterial", lane: true, nightlife: true },
  "Ronda de Sant Antoni": { kind: "arterial", lane: true },
  "Ronda de Sant Pau": { kind: "arterial", lane: true },
  "Carrer Gran de Gràcia": { kind: "street", cobbles: true },
  "Travessera de Gràcia": { kind: "arterial", rough: true },
  "Passeig Marítim": { kind: "seafront", lane: true },
  "Passeig de Lluís Companys": { kind: "promenade", lane: true },
  "Carrer de Wellington": { kind: "street", lane: true },
};

// ------------------------------------------------------------------ segment builder
const rawSegments = [];

/** Walks a grid line, keeps the stretches inside `zone`, splits at cross streets. */
function gridLine({ name, fixed, family, from, to, zone, cross, blocks = [2, 4], note }) {
  const step = 6;
  const pts = [];
  for (let s = from; s <= to; s += step) {
    const [u, v] = family === "A" ? [s, fixed] : [fixed, s];
    const ll = fromUV(u, v);
    pts.push({ s, ok: zone(ll) });
  }
  const runs = [];
  let start = null;
  for (let i = 0; i < pts.length; i++) {
    if (pts[i].ok && start === null) start = pts[i].s;
    if ((!pts[i].ok || i === pts.length - 1) && start !== null) {
      const end = pts[i].ok ? pts[i].s : pts[i - 1].s;
      if (end - start > 120) runs.push([start, end]);
      start = null;
    }
  }
  for (const [rs, re] of runs) {
    const xs = cross.filter((c) => c.at > rs + 25 && c.at < re - 25).sort((a, b) => a.at - b.at);
    const stops = [{ at: rs, name: xs.length && xs[0].at - rs < 80 ? null : null }, ...xs, { at: re }];
    let i = 0;
    while (i < stops.length - 1) {
      const n = rint(blocks[0], blocks[1]);
      const j = Math.min(stops.length - 1, i + n);
      const a = stops[i];
      const b = stops[j];
      if (b.at - a.at > 90) {
        const coords = [];
        for (let s = a.at; s <= b.at + 0.01; s += Math.max(20, (b.at - a.at) / 12)) {
          coords.push(family === "A" ? fromUV(s, fixed) : fromUV(fixed, s));
        }
        const endPt = family === "A" ? fromUV(b.at, fixed) : fromUV(fixed, b.at);
        if (distM(coords[coords.length - 1], endPt) > 1) coords.push(endPt);
        rawSegments.push({
          name,
          from: a.name || null,
          to: b.name || null,
          coords: simplify(coords, 1),
          note,
        });
      }
      i = j;
    }
  }
}

const crossB = Object.values(B).map((b) => ({ at: b.u, name: shortName(b.name) }));
const POBLENOU_A = ["tanger", "sancho", "almogavers", "pallars", "pujades", "llull", "turro"];
/** Cross streets met by a street running to the sea at offset `u` (names depend on the area). */
function crossAFor(u) {
  return Object.entries(A)
    .filter(([k]) => {
      if (POBLENOU_A.includes(k)) return u > 2100;
      if (k === "sepulveda" || k === "floridablanca") return u < -480;
      if (k === "casp" || k === "ausias") return u > -140 && u < 1120;
      if (k === "paris" || k === "londres") return u < -120;
      return true;
    })
    .map(([, a]) => ({ at: a.v, name: shortName(a.name) }));
}
/** Unnamed grid positions so long stretches still split every few blocks. */
function gridStops(from, to, phase, pitch = 133.4) {
  const out = [];
  for (let x = phase + Math.ceil((from - phase) / pitch) * pitch; x < to; x += pitch) out.push({ at: x, name: null });
  return out;
}
function mergeStops(named, unnamed) {
  return [...named, ...unnamed.filter((u) => !named.some((n) => Math.abs(n.at - u.at) < 50))];
}
function shortName(n) {
  return n
    .replace(/^Carrer (de la |de les |del |dels |de l'|de |d')/, "")
    .replace(/^Passeig (de |del )/, "Pg. ")
    .replace(/^Avinguda (de la |del |de |d')/, "Av. ")
    .replace(/^Rambla (de |del )/, "Rambla ")
    .replace("Gran Via de les Corts Catalanes", "Gran Via");
}
// Diagonal crossings for grid streets.
function withDiagonal(list, family, fixed) {
  const at = family === "A" ? uDiagAtV(fixed) : vDiag(fixed);
  return [...list, { at, name: "Diagonal" }];
}

// Eixample: streets parallel to the sea.
const eixA = ["granvia", "diputacio", "consell", "arago", "valencia", "mallorca", "provenca", "rossello", "corsega", "paris", "londres"];
for (const k of eixA) {
  const a = A[k];
  gridLine({
    name: a.name,
    fixed: a.v,
    family: "A",
    from: -2400,
    to: k === "paris" || k === "londres" ? -140 : k === "granvia" ? 2020 : 2080,
    zone: ZONES.eixample,
    cross: withDiagonal(crossB.filter((c) => c.at < 2000), "A", a.v),
    blocks: [3, 4],
  });
}
gridLine({ name: A.casp.name, fixed: 93, family: "A", from: -129, to: 1100, zone: ZONES.eixample, cross: crossB, blocks: [2, 3] });
gridLine({ name: A.sepulveda.name, fixed: 93, family: "A", from: -2400, to: -620, zone: ZONES.eixample, cross: crossB, blocks: [2, 4] });
gridLine({ name: A.ausias.name, fixed: 226, family: "A", from: -129, to: 1100, zone: ZONES.eixample, cross: crossB, blocks: [2, 3] });
gridLine({ name: A.floridablanca.name, fixed: 226, family: "A", from: -2400, to: -760, zone: ZONES.eixample, cross: crossB, blocks: [2, 4] });
// Eixample: streets running to the sea.
for (const [k, b] of Object.entries(B)) {
  if (b.u > 2000) continue;
  gridLine({
    name: b.name,
    fixed: b.u,
    family: "B",
    from: -1500,
    to: 300,
    zone: ZONES.eixample,
    cross: withDiagonal(crossAFor(b.u).filter((c) => c.at > -1450 && c.at < 260), "B", b.u),
    blocks: ["santjoan", "pgracia", "balmes", "marina"].includes(k) ? [2, 3] : [3, 4],
  });
}
// Gran Via beyond Glòries + Poblenou / 22@ grid.
const poblenouCrossB = mergeStops(
  crossB.filter((c) => c.at > 2100),
  gridStops(1300, 4700, 2709.7),
);
gridLine({ name: A.granvia.name, fixed: -55, family: "A", from: 2040, to: 4700, zone: ZONES.santmarti, cross: poblenouCrossB, blocks: [3, 4] });
for (const k of ["tanger", "sancho", "almogavers", "pallars", "pujades", "llull", "turro"]) {
  const a = A[k];
  gridLine({
    name: a.name,
    fixed: a.v,
    family: "A",
    from: 1150,
    to: 3500,
    zone: ZONES.poblenou,
    cross: withDiagonal(poblenouCrossB, "A", a.v),
    blocks: [2, 3],
  });
}
for (const k of ["marina", "badajoz", "llacuna", "rocboronat", "granada", "rambpoblenou"]) {
  const b = B[k];
  gridLine({
    name: b.name,
    fixed: b.u,
    family: "B",
    from: -40,
    to: 2000,
    zone: k === "marina" ? (ll) => ZONES.poblenou(ll) || ZONES.santmarti(ll) : ZONES.poblenou,
    cross: withDiagonal(mergeStops(crossAFor(2200).filter((c) => c.at > 0), gridStops(-60, 2000, 894.3)), "B", b.u),
    blocks: [2, 3],
  });
}

// Avinguda Diagonal, Francesc Macià → Fòrum.
{
  const crossings = Object.values(B)
    .map((b) => ({ at: b.u, name: shortName(b.name) }))
    .concat([{ at: 2050, name: "Glòries" }]);
  const east = [
    { at: 3243, name: "Bac de Roda" },
    { at: 3777, name: "Diagonal Mar" },
  ];
  const stops = [{ at: -1400, name: "Francesc Macià" }, ...[...crossings, ...east].filter((c) => c.at > -1380 && c.at < 4300).sort((a, b) => a.at - b.at), { at: 4380, name: "Fòrum" }];
  // de-duplicate stops closer than 60 m
  const clean = stops.filter((s, i) => i === 0 || s.at - stops[i - 1].at > 60);
  const groups = [];
  let i = 0;
  while (i < clean.length - 1) {
    const j = Math.min(clean.length - 1, i + (clean[i].at < 2100 ? rint(3, 4) : 2));
    groups.push([clean[i], clean[j]]);
    i = j;
  }
  // a few extra stops east of Rambla del Poblenou where the grid isn't named
  for (const [a, b] of groups) {
    const coords = [];
    for (let u = a.at; u <= b.at + 0.01; u += Math.max(20, (b.at - a.at) / 10)) coords.push(fromUV(u, vDiag(u)));
    rawSegments.push({ name: "Avinguda Diagonal", from: a.name, to: b.name, coords: simplify(coords, 1) });
  }
}

// Shared barri boundaries trace real avenues (La Rambla, Via Laietana, Paral·lel…).
function sharedBoundary(nameA, nameB) {
  const key = (c) => `${c[0].toFixed(6)},${c[1].toFixed(6)}`;
  const ringB = new Set();
  for (const r of ringsOf(barriByName[nameB].geometry)) for (const c of r[0]) ringB.add(key(c));
  const out = [];
  for (const r of ringsOf(barriByName[nameA].geometry)) {
    let cur = [];
    for (const c of r[0]) {
      if (ringB.has(key(c))) cur.push(c);
      else if (cur.length) {
        out.push(cur);
        cur = [];
      }
    }
    if (cur.length) out.push(cur);
  }
  out.sort((a, b) => lineLength(b) - lineLength(a));
  return out[0] || [];
}
function addPolyline(name, coords, { pieces = 2, from, to, ends } = {}) {
  const line = simplify(coords, 3);
  const total = lineLength(line);
  const pieceLen = total / pieces;
  let acc = 0;
  let cur = [line[0]];
  let k = 0;
  for (let i = 1; i < line.length; i++) {
    const d = distM(line[i - 1], line[i]);
    if (acc + d > pieceLen * (k + 1) && k < pieces - 1) {
      const t = (pieceLen * (k + 1) - acc) / d;
      const mid = [line[i - 1][0] + (line[i][0] - line[i - 1][0]) * t, line[i - 1][1] + (line[i][1] - line[i - 1][1]) * t];
      cur.push(mid);
      rawSegments.push({ name, from: ends?.[k] ?? from ?? null, to: ends?.[k + 1] ?? null, coords: cur });
      cur = [mid];
      k++;
    }
    cur.push(line[i]);
    acc += d;
  }
  rawSegments.push({ name, from: ends?.[k] ?? null, to: ends?.[k + 1] ?? to ?? null, coords: cur });
}
const orient = (coords, northFirst = true) => {
  const c = [...coords];
  if (northFirst ? c[0][1] < c[c.length - 1][1] : c[0][1] > c[c.length - 1][1]) c.reverse();
  return c;
};
addPolyline("La Rambla", orient(sharedBoundary("el Raval", "el Barri Gòtic")), { pieces: 3, ends: ["Pl. Catalunya", "Liceu", "Drassanes", "Colom"] });
addPolyline("Via Laietana", orient(sharedBoundary("el Barri Gòtic", "Sant Pere, Santa Caterina i la Ribera")), { pieces: 2, ends: ["Urquinaona", "Jaume I", "Pg. Colom"] });
addPolyline("Avinguda del Paral·lel", [...sharedBoundary("Sant Antoni", "el Poble-sec"), ...sharedBoundary("el Raval", "el Poble-sec")].sort((a, b) => a[0] - b[0]), {
  pieces: 3,
  ends: ["Pl. Espanya", "Poble-sec", "Paral·lel", "Drassanes"],
});
addPolyline("Ronda de Sant Antoni", orient(sharedBoundary("Sant Antoni", "el Raval")), { pieces: 2, ends: ["Universitat", "Mercat de Sant Antoni", "Paral·lel"] });

// Gràcia (approximate centre-lines).
const travessera = (u) => -1885.3 + 0.226 * (u + 138);
addPolyline("Carrer Gran de Gràcia", [fromUV(-129.2, vDiag(-129.2)), fromUV(-136, -1560), fromUV(-138, travessera(-138)), fromUV(-40, -2230), fromUV(82, -2509)], {
  pieces: 3,
  ends: ["Jardinets", "Fontana", "Travessera", "Lesseps"],
});
addPolyline("Travessera de Gràcia", [fromUV(-560, travessera(-560)), fromUV(-138, travessera(-138)), fromUV(709, travessera(709)), fromUV(1243, travessera(1243))], {
  pieces: 4,
  ends: ["Via Augusta", "Gran de Gràcia", "Torrent de l'Olla", "Pg. Sant Joan", "Sardenya"],
});
addPolyline("Passeig de Sant Joan", [fromUV(709, travessera(709)), fromUV(709, vDiag(709))], { pieces: 2, ends: ["Travessera", "Gràcia", "Diagonal"] });

// Seafront: follow the municipal coastline 70 m inland.
const coastline = (() => {
  const coastal = ["la Barceloneta", "la Vila Olímpica del Poblenou", "el Poblenou", "Diagonal Mar i el Front Marítim del Poblenou", "el Besòs i el Maresme"];
  const pts = coastal.flatMap((n) => ringsOf(barriByName[n].geometry).flatMap((p) => p[0].map((c) => toUV(c))));
  const raw = [];
  for (let u = 980; u <= 4250; u += 80) {
    let best = null;
    for (const [pu, pv] of pts) if (Math.abs(pu - u) < 60 && (best === null || pv > best)) best = pv;
    if (best !== null) raw.push([u, best]);
  }
  // median filter removes the piers and the Olympic marina
  const smooth = raw.map((p, i) => {
    const w = raw.slice(Math.max(0, i - 3), i + 4).map((q) => q[1]).sort((a, b) => a - b);
    return [p[0], w[Math.floor(w.length / 2)]];
  });
  return simplify(smooth.map(([u, v]) => fromUV(u, v - 85)), 6);
})();
addPolyline("Passeig Marítim", coastline, { pieces: 5, ends: ["Barceloneta", "Port Olímpic", "Bogatell", "Mar Bella", "Llevant", "Fòrum"] });
addPolyline("Carrer de Wellington", [fromUV(1101, 560), fromUV(1101, 1660)], { pieces: 2, ends: ["Pujades", "Ciutadella", "Icària"] });
addPolyline("Passeig de Lluís Companys", [fromUV(760, 470), fromUV(850, 730)], { pieces: 1, ends: ["Arc de Triomf", "Ciutadella"] });

// ------------------------------------------------------------------ measurements
// Hourly traffic intensity (0..1) — Barcelona weekday profile.
const TRAFFIC = [0.16, 0.1, 0.07, 0.07, 0.11, 0.24, 0.52, 0.86, 1.0, 0.88, 0.74, 0.7, 0.73, 0.77, 0.72, 0.7, 0.76, 0.86, 0.95, 0.88, 0.68, 0.5, 0.36, 0.24];
export const airScore = (pm) => clamp(Math.round(100 - (pm - 5) * 3.2), 0, 100);
export const noiseScore = (db) => clamp(Math.round(100 - (db - 50) * 3.3), 0, 100);
export const comfortScore = (vib) => clamp(Math.round(100 - (vib - 0.4) * 38), 0, 100);

const BASE = {
  arterial: { vib: 0.95, pm: 15.5, db: 70.5, safety: 56 },
  boulevard: { vib: 0.8, pm: 13.5, db: 66, safety: 66 },
  street: { vib: 1.05, pm: 13.2, db: 64.5, safety: 68 },
  green: { vib: 0.9, pm: 10.6, db: 58.5, safety: 82 },
  promenade: { vib: 1.4, pm: 12.5, db: 63, safety: 72 },
  seafront: { vib: 0.7, pm: 8.2, db: 57, safety: 84 },
};

const segments = rawSegments
  .filter((s) => s.coords.length >= 2 && lineLength(s.coords) > 80)
  .map((s, i) => {
    const ch = CHARACTER[s.name] || { kind: "street" };
    const base = BASE[ch.kind];
    const mid = s.coords[Math.floor(s.coords.length / 2)];
    const district = districtOf(mid);
    const len = lineLength(s.coords);
    let vib = base.vib * rnd(0.82, 1.22) + (ch.rough ? 0.55 : 0) + (ch.cobbles ? 0.95 : 0) + (ch.fastRough ? 0.5 : 0);
    if (rand() < 0.08) vib += rnd(0.4, 0.8); // patched / worn asphalt
    let pm = base.pm * rnd(0.88, 1.14) + (district === "Eixample" ? 0.8 : 0);
    let db = base.db + gauss() * 1.6 - (ch.lane && (ch.kind === "arterial" || ch.kind === "boulevard") ? 4.5 : 0);
    let safety = base.safety + gauss() * 6 - (ch.kind === "arterial" && /Aragó|Diagonal|Gran Via|Balmes/.test(s.name) ? 6 : 0);
    const hourly = { comfort: [], safety: [], air: [], noise: [] };
    for (let h = 0; h < 24; h++) {
      const t = TRAFFIC[h];
      const inversion = h >= 7 && h <= 9 ? 1.12 : h >= 14 && h <= 17 ? 0.9 : 1; // sea breeze in the afternoon
      const smog = ch.morningSmog && h >= 7 && h <= 9 ? 1.45 : 1;
      const pmH = pm * (0.62 + 0.55 * t) * inversion * smog + gauss() * 0.4;
      const night = ch.nightlife && (h >= 22 || h <= 2) ? 5 : 0;
      const dbH = db - 9 * (1 - t) + night + gauss() * 0.5;
      hourly.air.push(airScore(pmH));
      hourly.noise.push(noiseScore(dbH));
      hourly.comfort.push(clamp(Math.round(comfortScore(vib) - 4 * (t - 0.5) + gauss()), 0, 100));
      hourly.safety.push(clamp(Math.round(safety - 13 * (t - 0.45) + gauss() * 1.2), 0, 100));
    }
    const avg = (arr) => Math.round(arr.reduce((a, b) => a + b, 0) / arr.length);
    const peakPasses = ch.lane ? rint(380, 1450) : ch.kind === "green" ? rint(180, 720) : rint(30, 320);
    const scores = { comfort: avg(hourly.comfort), safety: avg(hourly.safety), air: avg(hourly.air), noise: avg(hourly.noise) };
    return {
      id: `seg-${String(i + 1).padStart(3, "0")}`,
      name: s.name,
      from: s.from,
      to: s.to,
      district,
      kind: ch.kind,
      bikeLane: !!ch.lane,
      lengthM: Math.round(len),
      coordinates: s.coords.map(ll5),
      scores,
      hourly,
      passes30d: peakPasses,
      trend: round(gauss() * 2.4, 1),
      surface: { vibRms: round(vib, 2), potholes: 0 },
      pm25: round(pm, 1),
      db: round(db, 1),
    };
  });

// Narrative anchors used across the product copy.
function findSeg(name, pred = () => true) {
  return segments.find((s) => s.name === name && pred(s));
}
{
  const arago = segments.filter((s) => s.name === "Carrer d'Aragó");
  for (const s of arago.slice(0, 3)) {
    s.surface.vibRms = round(s.surface.vibRms + 0.35, 2);
    s.hourly.comfort = s.hourly.comfort.map((c) => clamp(c - 14, 0, 100));
    s.scores.comfort = Math.round(s.hourly.comfort.reduce((a, b) => a + b, 0) / 24);
  }
  const sj = segments.filter((s) => s.name === "Passeig de Sant Joan");
  for (const s of sj) {
    s.hourly.noise = s.hourly.noise.map((n) => clamp(n + 12, 0, 100));
    s.scores.noise = Math.round(s.hourly.noise.reduce((a, b) => a + b, 0) / 24);
  }
}

// Potholes on rough surfaces, confirmed by ≥ 3 riders.
function pointAlong(coords, t) {
  const total = lineLength(coords);
  let target = total * t;
  for (let i = 1; i < coords.length; i++) {
    const d = distM(coords[i - 1], coords[i]);
    if (target <= d) {
      const k = d ? target / d : 0;
      return [coords[i - 1][0] + (coords[i][0] - coords[i - 1][0]) * k, coords[i - 1][1] + (coords[i][1] - coords[i - 1][1]) * k];
    }
    target -= d;
  }
  return coords[coords.length - 1];
}
const potholes = [];
for (const s of segments) {
  if (s.scores.comfort < 58 || rand() < 0.05) {
    const n = s.scores.comfort < 45 ? rint(1, 3) : 1;
    for (let k = 0; k < n; k++) {
      const confirmations = rint(3, 16);
      potholes.push({
        id: `ph-${potholes.length + 1}`,
        segmentId: s.id,
        street: s.name,
        coordinates: ll5(pointAlong(s.coordinates, rnd(0.15, 0.85))),
        confirmations,
        firstSeen: new Date(Date.UTC(2026, rint(4, 9), rint(1, 28))).toISOString().slice(0, 10),
        severity: confirmations > 10 ? "high" : confirmations > 6 ? "medium" : "low",
      });
    }
    s.surface.potholes = n;
  }
}

// Hard-brake hotspots at junctions.
const junction = (bKey, aKeyOrV, label) => {
  const u = B[bKey].u;
  const v = typeof aKeyOrV === "number" ? aKeyOrV : A[aKeyOrV].v;
  return { coordinates: ll5(fromUV(u, v)), label };
};
const diag = (bKey, label) => {
  const u = B[bKey].u;
  return { coordinates: ll5(fromUV(u, vDiag(u))), label: label || `Av. Diagonal × ${shortName(B[bKey].name)}` };
};
const namedHotspots = [
  [diag("santjoan", "Av. Diagonal × Pg. de Sant Joan (Verdaguer)"), 41],
  [{ coordinates: ll5(fromUV(2050, vDiag(2050))), label: "Pl. de les Glòries" }, 36],
  [junction("pgracia", "arago", "Pg. de Gràcia × Aragó"), 31],
  [junction("santjoan", "granvia", "Pg. de Sant Joan × Gran Via (Tetuan)"), 29],
  [diag("marina"), 27],
  [junction("balmes", "arago", "Balmes × Aragó"), 25],
  [diag("llacuna"), 23],
  [junction("marina", "granvia", "Marina × Gran Via"), 22],
  [junction("urgell", "arago", "Comte d'Urgell × Aragó"), 21],
  [junction("aribau", "diputacio", "Aribau × Diputació"), 19],
  [diag("balmes"), 18],
  [junction("llacuna", "pallars", "Llacuna × Pallars"), 16],
  [junction("pauclaris", "valencia", "Pau Claris × València"), 15],
  [junction("muntaner", "arago", "Muntaner × Aragó"), 14],
  [junction("sicilia", "arago", "Sicília × Aragó"), 13],
];
const hotspots = namedHotspots.map(([h, w], i) => ({
  id: `hs-${i + 1}`,
  label: h.label,
  coordinates: h.coordinates,
  hardBrakesWeek: w,
  hardBrakes30d: Math.round(w * 4.3 + rint(-6, 6)),
  peakHour: pick([8, 8, 9, 18, 19]),
  trend: round(gauss() * 8, 0),
  avgDecel: round(rnd(3.4, 4.6), 1),
}));
// extra smaller hotspots at random arterial junctions
const arterialB = ["balmes", "muntaner", "aribau", "urgell", "borrell", "pauclaris", "lluria", "girona", "bailen", "santjoan", "napols", "sardenya", "marina", "casanova", "villarroel"];
const arterialA = ["granvia", "diputacio", "consell", "arago", "valencia", "mallorca", "provenca", "rossello"];
while (hotspots.length < 64) {
  const b = pick(arterialB);
  const a = pick(arterialA);
  const label = `${shortName(B[b].name)} × ${shortName(A[a].name)}`;
  if (hotspots.some((h) => h.label === label)) continue;
  const w = rint(4, 13);
  hotspots.push({
    id: `hs-${hotspots.length + 1}`,
    label,
    coordinates: junction(b, a, label).coordinates,
    hardBrakesWeek: w,
    hardBrakes30d: Math.round(w * 4.3 + rint(-3, 3)),
    peakHour: pick([8, 9, 13, 18, 19, 20]),
    trend: round(gauss() * 10, 0),
    avgDecel: round(rnd(3.1, 4.2), 1),
  });
}

// ------------------------------------------------------------------ routes
const P = (u, v) => fromUV(u, v);
const ROUTE_START = fromUV(204, travessera(204)); // Plaça de la Vila de Gràcia
const OFFICE = fromUV(B.llacuna.u, A.pallars.v); // Llacuna × Pallars, 22@
function densify(coords, step = 25) {
  const out = [coords[0]];
  for (let i = 1; i < coords.length; i++) {
    const d = distM(coords[i - 1], coords[i]);
    const n = Math.max(1, Math.ceil(d / step));
    for (let k = 1; k <= n; k++) {
      out.push([coords[i - 1][0] + ((coords[i][0] - coords[i - 1][0]) * k) / n, coords[i - 1][1] + ((coords[i][1] - coords[i - 1][1]) * k) / n]);
    }
  }
  return out;
}
const routeDefs = {
  fastest: [ROUTE_START, P(709, travessera(709)), P(709, vDiag(709)), P(B.llacuna.u, vDiag(B.llacuna.u)), OFFICE],
  calmest: [ROUTE_START, P(709, travessera(709)), P(709, A.consell.v), P(B.badajoz.u, A.consell.v), P(B.badajoz.u, A.pallars.v), OFFICE],
  cleanest: [ROUTE_START, P(709, travessera(709)), P(709, A.rossello.v), P(B.lepant.u, A.rossello.v), P(B.lepant.u, A.almogavers.v), P(B.llacuna.u, A.almogavers.v), OFFICE],
};
const routeLegs = {
  fastest: ["Travessera de Gràcia", "Passeig de Sant Joan", "Avinguda Diagonal", "Carrer de la Llacuna"],
  calmest: ["Travessera de Gràcia", "Passeig de Sant Joan", "Carrer del Consell de Cent", "Carrer de Badajoz", "Carrer de Pallars"],
  cleanest: ["Travessera de Gràcia", "Passeig de Sant Joan", "Carrer del Rosselló", "Carrer de Lepant", "Carrer d'Almogàvers", "Carrer de la Llacuna"],
};
const plannedRoutes = Object.entries(routeDefs).map(([goal, coords]) => {
  const line = coords;
  const distance = lineLength(line);
  const meta = {
    fastest: { minutes: 18, scores: { comfort: 66, safety: 61, air: 54, noise: 43 }, highlight: "Fewest stops, Diagonal bike lane" },
    calmest: { minutes: 21, scores: { comfort: 82, safety: 84, air: 78, noise: 72 }, highlight: "Consell de Cent green axis, 4 fewer busy junctions" },
    cleanest: { minutes: 20, scores: { comfort: 74, safety: 76, air: 86, noise: 64 }, highlight: "Avoids Diagonal and Aragó during the 8 am peak" },
  }[goal];
  return {
    id: `route-${goal}`,
    goal,
    label: goal[0].toUpperCase() + goal.slice(1),
    durationMin: meta.minutes,
    distanceM: Math.round(distance),
    scores: meta.scores,
    via: routeLegs[goal],
    highlight: meta.highlight,
    coordinates: line.map(ll5),
  };
});

// ------------------------------------------------------------------ activities
function nearestSegment(ll, maxD = 30) {
  let best = null;
  let bestD = maxD;
  for (const s of segments) {
    for (let i = 1; i < s.coordinates.length; i++) {
      const a = proj(s.coordinates[i - 1]);
      const b = proj(s.coordinates[i]);
      const p = proj(ll);
      const dx = b[0] - a[0];
      const dy = b[1] - a[1];
      const t = clamp(((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy || 1), 0, 1);
      const d = Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
      if (d < bestD) {
        bestD = d;
        best = s;
      }
    }
  }
  return best;
}

const people = {
  laia: { id: "laia", name: "Laia Serra", firstName: "Laia", initials: "LS", age: 31, city: "Gràcia, Barcelona", vehicle: "e-bike" },
  marc: { id: "marc", name: "Marc Ferrer", firstName: "Marc", initials: "MF", age: 34, city: "Poblenou, Barcelona", vehicle: "run" },
};
const friends = ["Núria Vila", "Jordi Soler", "Aina Puig", "Pau Roca", "Clara Bosch", "Oriol Mas", "Bernat Riera", "Marta Coll", "Arnau Font", "Júlia Camps"];

const NOW = new Date("2026-10-15T19:10:00+02:00");
function dayAt(daysAgo, hh, mm) {
  const d = new Date(NOW);
  d.setDate(d.getDate() - daysAgo);
  d.setHours(hh, mm, rint(0, 59), 0);
  return d;
}

/** Simulates a ride/run along `line`, sampling every `dt` seconds. */
function simulate({ line, kind, start, cruise, events = [], pmBias = 0, dbBias = 0 }) {
  const pts = densify(line, 8);
  const cum = [0];
  for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + distM(pts[i - 1], pts[i]));
  const total = cum[cum.length - 1];
  const dt = kind === "run" ? 15 : 10;
  const stops = [];
  if (kind === "ride") {
    for (let d = 260; d < total - 150; d += rnd(220, 520)) if (rand() < 0.42) stops.push({ at: d, wait: rint(8, 38) });
  }
  const samples = [];
  let t = 0;
  let d = 0;
  let v = 0;
  let stopIdx = 0;
  let waited = 0;
  const segCache = new Map();
  while (d < total && t < 6 * 3600) {
    const stop = stops[stopIdx];
    let target = cruise * (0.86 + 0.14 * Math.sin(t / 47) + gauss() * 0.05);
    if (stop && d > stop.at - 25 && d < stop.at + 5) {
      target = 0;
      if (v < 0.4) {
        waited += dt;
        if (waited >= stop.wait) {
          stopIdx++;
          waited = 0;
        }
      }
    } else if (stop && d >= stop.at + 5) stopIdx++;
    if (d < 40) target = Math.min(target, 2 + d / 10);
    const prevV = v;
    v = v + clamp(target - v, -2.2 * dt, 1.1 * dt) * 0.55;
    v = Math.max(0, v);
    d += ((v + prevV) / 2) * dt;
    t += dt;
    const idx = Math.min(pts.length - 1, cum.findIndex((c) => c >= d) === -1 ? pts.length - 1 : cum.findIndex((c) => c >= d));
    const pos = pts[idx];
    const key = Math.floor(idx / 6);
    if (!segCache.has(key)) segCache.set(key, nearestSegment(pos, 35));
    const seg = segCache.get(key);
    const hour = start.getHours() + start.getMinutes() / 60 + t / 3600;
    const traffic = TRAFFIC[Math.floor(hour) % 24];
    const baseVib = seg ? seg.surface.vibRms : 1.0;
    const basePm = seg ? seg.pm25 : 12;
    const baseDb = seg ? seg.db : 63;
    samples.push({
      t,
      d: Math.round(Math.min(d, total)),
      speed: round(v * 3.6, 1),
      vib: round(kind === "run" ? 0.3 + Math.abs(gauss()) * 0.12 : Math.max(0.15, baseVib * (0.55 + 0.6 * Math.min(1, v / cruise)) + gauss() * 0.12), 2),
      pm25: round(Math.max(3, basePm * (0.62 + 0.55 * traffic) + pmBias + gauss() * 0.9), 1),
      db: round(Math.max(45, baseDb - 9 * (1 - traffic) + dbBias + gauss() * 1.4), 1),
      i: idx,
      seg: seg ? seg.id : null,
    });
  }
  // inject events
  const out = [];
  for (const ev of events) {
    const target = ev.at * total;
    const k = samples.findIndex((s) => s.d >= target);
    if (k < 0) continue;
    const s = samples[k];
    if (ev.type === "hard_brake") {
      s.speed = round(Math.max(2, s.speed * 0.35), 1);
      if (samples[k + 1]) samples[k + 1].speed = round(Math.max(0, samples[k + 1].speed * 0.4), 1);
    }
    if (ev.type === "pothole") s.vib = round(ev.value ?? rnd(4.2, 5.6), 2);
    if (ev.type === "pm_spike") {
      for (let j = -1; j <= 2; j++) if (samples[k + j]) samples[k + j].pm25 = round((ev.value ?? 34) - Math.abs(j) * 4 + gauss(), 1);
    }
    if (ev.type === "noise_peak") s.db = round(ev.value ?? 84, 1);
    const when = new Date(start.getTime() + s.t * 1000);
    out.push({
      type: ev.type,
      sampleIndex: k,
      coordinates: ll5(pts[s.i]),
      value: ev.type === "hard_brake" ? round(ev.value ?? rnd(3.4, 4.6), 1) : ev.type === "pothole" ? s.vib : ev.type === "pm_spike" ? s.pm25 : s.db,
      time: `${String(when.getHours()).padStart(2, "0")}:${String(when.getMinutes()).padStart(2, "0")}`,
      street: ev.street || (s.seg ? segments.find((x) => x.id === s.seg)?.name : null),
    });
  }
  return { samples, total, events: out, pts };
}

function scoreRide(sim, kind) {
  const n = sim.samples.length;
  const mean = (f) => sim.samples.reduce((a, s) => a + f(s), 0) / n;
  const vib = mean((s) => s.vib);
  const pm = mean((s) => s.pm25);
  const db = mean((s) => s.db);
  const brakes = sim.events.filter((e) => e.type === "hard_brake").length;
  return {
    comfort: kind === "run" ? clamp(Math.round(88 - pm / 4 + gauss() * 3), 0, 100) : comfortScore(vib),
    safety: clamp(Math.round(86 - brakes * 9 - (kind === "ride" ? 8 : 0) + gauss() * 3), 0, 100),
    air: airScore(pm),
    noise: noiseScore(db),
  };
}

function routeSegments(sim) {
  const seq = [];
  for (const s of sim.samples) {
    if (!s.seg) continue;
    const last = seq[seq.length - 1];
    if (last && last.id === s.seg) last.samples.push(s);
    else seq.push({ id: s.seg, samples: [s] });
  }
  return seq
    .filter((x) => x.samples.length >= 2)
    .map((x) => {
      const seg = segments.find((s) => s.id === x.id);
      const vib = x.samples.reduce((a, s) => a + s.vib, 0) / x.samples.length;
      const pm = x.samples.reduce((a, s) => a + s.pm25, 0) / x.samples.length;
      const db = x.samples.reduce((a, s) => a + s.db, 0) / x.samples.length;
      const yours = Math.round((comfortScore(vib) * 0.35 + airScore(pm) * 0.35 + noiseScore(db) * 0.3) * 1);
      const avg = Math.round(seg.scores.comfort * 0.35 + seg.scores.air * 0.35 + seg.scores.noise * 0.3);
      return {
        segmentId: seg.id,
        name: seg.name,
        from: seg.from,
        to: seg.to,
        distanceM: x.samples[x.samples.length - 1].d - x.samples[0].d,
        score: yours,
        streetAverage: avg,
        bikeLane: seg.bikeLane,
      };
    })
    .filter((x) => x.distanceM > 60);
}

const offset = (line, meters) =>
  line.map((ll) => {
    const [u, v] = toUV(ll);
    return fromUV(u + gauss() * meters, v + gauss() * meters);
  });

const activities = [];
function addActivity({ athlete, kind, title, start, line, cruise, events, targetScores, kudos, comments, description, pmBias, dbBias, featured }) {
  const sim = simulate({ line, kind, start, cruise, events, pmBias, dbBias });
  const scores = targetScores || scoreRide(sim, kind);
  const duration = sim.samples[sim.samples.length - 1].t;
  const route = simplify(offset(sim.pts, 1.2), 2.5).map(ll5);
  const id = `${athlete}-${start.toISOString().slice(0, 10).replaceAll("-", "")}-${String(start.getHours()).padStart(2, "0")}${String(start.getMinutes()).padStart(2, "0")}`;
  // compact samples (index into route for map sync)
  const routeProj = route.map(proj);
  const samples = sim.samples.map((s) => {
    const p = proj(sim.pts[s.i]);
    let bi = 0;
    let bd = Infinity;
    for (let k = 0; k < routeProj.length; k++) {
      const dd = (routeProj[k][0] - p[0]) ** 2 + (routeProj[k][1] - p[1]) ** 2;
      if (dd < bd) {
        bd = dd;
        bi = k;
      }
    }
    return [s.t, s.d, s.speed, s.vib, s.pm25, s.db, bi];
  });
  const kudoers = [...friends].sort(() => rand() - 0.5).slice(0, kudos);
  const place = /Morning commute/.test(title)
    ? "Gràcia → 22@"
    : /Evening ride home/.test(title)
      ? "22@ → Gràcia"
      : /seafront|beach|Bogatell/i.test(title)
        ? "Gràcia → Bogatell"
        : /green-axis/.test(title)
          ? "Eixample"
          : /Ciutadella/.test(title)
            ? "Parc de la Ciutadella"
            : /Poblenou/.test(title)
              ? "Poblenou"
              : /Diagonal Mar/.test(title)
                ? "Diagonal Mar"
                : "Front Marítim";
  const a = {
    id,
    athleteId: athlete,
    type: kind,
    title,
    place,
    description: description || null,
    startedAt: start.toISOString(),
    durationS: Math.round(duration),
    movingTimeS: Math.round(sim.samples.filter((s) => s.speed > 1).length * (kind === "run" ? 15 : 10)),
    distanceM: Math.round(sim.total),
    avgSpeedKmh: round((sim.total / duration) * 3.6, 1),
    maxSpeedKmh: round(Math.max(...sim.samples.map((s) => s.speed)), 1),
    elevationGainM: Math.round(sim.total / 1000 * rnd(4, 11)),
    scores,
    events: sim.events,
    route,
    samples,
    segments: routeSegments(sim),
    kudos,
    kudoedBy: kudoers,
    comments,
    featured: !!featured,
    weather: { tempC: round(rnd(15, 23), 0), condition: pick(["clear", "clear", "cloudy", "breezy"]) },
  };
  activities.push(a);
  return a;
}

const commuteMorning = densify(routeDefs.fastest, 20);
const commuteEvening = densify([...routeDefs.calmest].reverse(), 20);
const commuteCleanest = densify(routeDefs.cleanest, 20);
const weekendLines = {
  seafront: densify([ROUTE_START, P(709, travessera(709)), P(709, 300), P(1101, 600), P(1101, 1660), ...coastline.slice(2, 40)], 20),
  eixample: densify([ROUTE_START, P(709, travessera(709)), P(709, A.consell.v), P(-1823.9, A.consell.v), P(-1823.9, A.mallorca.v), P(709, A.mallorca.v), P(709, travessera(709)), ROUTE_START], 20),
};

// Laia — 25 rides over the last five weeks.
let featuredDone = false;
for (let day = 0; day < 36 && activities.filter((a) => a.athleteId === "laia").length < 25; day++) {
  const date = new Date(NOW);
  date.setDate(date.getDate() - day);
  const dow = date.getDay();
  if (dow === 0 || dow === 6) {
    if (rand() < 0.5) {
      const seaside = rand() < 0.6;
      addActivity({
        athlete: "laia",
        kind: "ride",
        title: seaside ? pick(["Sunday seafront spin", "Saturday ride to the beach", "Slow ride to Bogatell"]) : "Eixample green-axis loop",
        start: dayAt(day, rint(9, 11), rint(0, 59)),
        line: seaside ? weekendLines.seafront : weekendLines.eixample,
        cruise: rnd(4.6, 5.4),
        kudos: rint(3, 9),
        comments: rint(0, 3),
        events: seaside ? [{ type: "noise_peak", at: 0.32, value: 82 }] : [{ type: "pothole", at: 0.41, street: "Carrer de Rocafort" }],
      });
    }
    continue;
  }
  if (day === 0) {
    // today: the hero ride used across the landing and the ride report
    addActivity({
      athlete: "laia",
      kind: "ride",
      title: "Morning commute",
      description: "Gràcia → 22@. Glòries was busy, the PM2.5 spike at 8:05 was a bus idling at the lights.",
      start: new Date("2026-10-15T07:52:40+02:00"),
      line: commuteMorning,
      cruise: 4.7,
      events: [
        { type: "hard_brake", at: 0.395, value: 4.1, street: "Av. Diagonal × Pg. de Sant Joan" },
        { type: "pothole", at: 0.55, value: 5.2, street: "Avinguda Diagonal" },
        { type: "pm_spike", at: 0.785, value: 34, street: "Pl. de les Glòries" },
      ],
      targetScores: { comfort: 72, safety: 64, air: 58, noise: 61 },
      kudos: 12,
      comments: 3,
      featured: true,
    });
    featuredDone = true;
    continue;
  }
  const morning = rand() < 0.8;
  const evening = rand() < 0.55;
  if (morning) {
    const clean = rand() < 0.25;
    addActivity({
      athlete: "laia",
      kind: "ride",
      title: clean ? "Morning commute · cleanest route" : "Morning commute",
      start: dayAt(day, 7, rint(35, 59)),
      line: clean ? commuteCleanest : commuteMorning,
      cruise: rnd(5.0, 5.6),
      kudos: rint(1, 8),
      comments: rint(0, 2),
      events: clean ? [] : [{ type: "hard_brake", at: rnd(0.26, 0.31), street: "Av. Diagonal × Pg. de Sant Joan" }, ...(rand() < 0.5 ? [{ type: "pm_spike", at: 0.7, value: rint(26, 33) }] : [])],
    });
  }
  if (evening && activities.filter((a) => a.athleteId === "laia").length < 25) {
    addActivity({
      athlete: "laia",
      kind: "ride",
      title: "Evening ride home",
      start: dayAt(day, 18, rint(5, 50)),
      line: commuteEvening,
      cruise: rnd(4.6, 5.2),
      kudos: rint(0, 6),
      comments: rint(0, 1),
      events: rand() < 0.4 ? [{ type: "pothole", at: rnd(0.55, 0.8) }] : [],
    });
  }
}

// Marc — marathon preparation runs.
const ciutadellaLoop = densify([P(760, 470), P(1101, 560), P(1101, 1180), P(820, 1240), P(700, 980), P(760, 470)], 20);
const loops = (line, n) => Array.from({ length: n }, (_, i) => (i ? line.slice(1) : line)).flat();
const coastOut = densify(coastline, 20);
const coastBack = [...coastOut].reverse();
const poblenouLoop = densify([P(2312, 360), P(2709, 360), P(2709, 894), P(1777, 894), P(1777, 360), P(2312, 360)], 20);
const marcRuns = [
  { days: 1, h: 7, title: "Tempo · Ciutadella loops", line: loops(ciutadellaLoop, 4), cruise: 3.65 },
  { days: 3, h: 19, title: "Easy 6 k · Poblenou superblocks", line: loops(poblenouLoop, 2), cruise: 3.05 },
  { days: 5, h: 8, title: "Long run · Front Marítim", line: [...coastOut, ...coastBack.slice(1), ...coastOut.slice(1), ...coastBack.slice(1)], cruise: 3.3 },
  { days: 8, h: 7, title: "Intervals · Diagonal Mar", line: loops(densify([P(2709, vDiag(2709)), P(4300, vDiag(4300)), P(2709, vDiag(2709))], 20), 2), cruise: 3.9 },
  { days: 10, h: 8, title: "Recovery jog · Ciutadella", line: loops(ciutadellaLoop, 2), cruise: 2.8 },
  { days: 12, h: 9, title: "Long run · Fòrum and back", line: [...coastOut, ...coastBack.slice(1), ...coastOut.slice(1), ...coastBack.slice(1), ...coastOut.slice(1, Math.floor(coastOut.length / 2))], cruise: 3.25 },
];
for (const r of marcRuns) {
  addActivity({
    athlete: "marc",
    kind: "run",
    title: r.title,
    start: dayAt(r.days, r.h, rint(0, 40)),
    line: r.line,
    cruise: r.cruise,
    kudos: rint(4, 14),
    comments: rint(0, 4),
    events: r.title.includes("Diagonal") ? [{ type: "noise_peak", at: 0.4, value: 81 }] : [],
    pmBias: -2,
    dbBias: -2,
  });
}
activities.sort((a, b) => b.startedAt.localeCompare(a.startedAt));

// ------------------------------------------------------------------ exposure (Laia)
const exposureDays = [];
for (let day = 364; day >= 0; day--) {
  const d = new Date(NOW);
  d.setDate(d.getDate() - day);
  const dow = d.getDay();
  const month = d.getMonth();
  const weekday = dow > 0 && dow < 6;
  const winter = [11, 0, 1].includes(month) ? 1.18 : [6, 7].includes(month) ? 0.86 : 1;
  const holiday = month === 7 && d.getDate() < 25; // August away
  const rideMin = holiday ? (rand() < 0.15 ? rint(15, 40) : 0) : weekday ? (rand() < 0.88 ? rint(30, 44) : 0) : rand() < 0.45 ? rint(25, 70) : 0;
  const trend = 1 - (364 - day) / 364 * 0.16; // switching to calmer routes over the year
  const pm = rideMin ? round((13.5 + gauss() * 2.4) * winter * (weekday ? trend : 0.82), 1) : null;
  const db = rideMin ? round(63.5 + gauss() * 1.8 - (weekday ? 0 : 3) - (1 - trend) * 6, 1) : null;
  exposureDays.push({ date: d.toISOString().slice(0, 10), rideMin, pm25: pm, db, doseUgH: pm ? round((pm * rideMin) / 60, 1) : 0 });
}

// ------------------------------------------------------------------ city aggregates
const districtNames = districtsFc.features.map((f) => f.properties.NOM);
const districtStats = districtNames.map((name) => {
  const segs = segments.filter((s) => s.district === name);
  const mean = (k) => (segs.length ? Math.round(segs.reduce((a, s) => a + s.scores[k], 0) / segs.length) : null);
  const synthetic = { comfort: rint(58, 78), safety: rint(55, 80), air: rint(52, 82), noise: rint(40, 70) };
  const scores = {
    comfort: mean("comfort") ?? synthetic.comfort,
    safety: mean("safety") ?? synthetic.safety,
    air: mean("air") ?? synthetic.air,
    noise: mean("noise") ?? synthetic.noise,
  };
  const surfaceIndex = round(scores.comfort * 0.8 + rnd(6, 16), 1);
  const rides = name === "Eixample" ? 3120 : name === "Sant Martí" ? 1980 : name === "Gràcia" ? 1210 : name === "Ciutat Vella" ? 940 : rint(180, 760);
  return {
    name,
    code: districtsFc.features.find((f) => f.properties.NOM === name).properties.DISTRICTE,
    scores,
    surfaceIndex: clamp(surfaceIndex, 40, 92),
    ridesWeek: rides,
    kmMeasured: round(segs.reduce((a, s) => a + s.lengthM, 0) / 1000 + (segs.length ? 0 : rnd(4, 18)), 1),
    hotspots: hotspots.filter((h) => districtOf(h.coordinates) === name).length || rint(1, 4),
    pm25: round(13 + (100 - scores.air) / 16 + gauss() * 0.4, 1),
    db: round(58 + (100 - scores.noise) / 6 + gauss() * 0.6, 1),
  };
});
const weeks = 12;
const spark = (end, vol, drift) => {
  const arr = [];
  let x = end - drift * weeks;
  for (let i = 0; i < weeks; i++) {
    x += drift + gauss() * vol;
    arr.push(round(x, 1));
  }
  arr[weeks - 1] = end;
  return arr;
};
const kmMeasured = round(segments.reduce((a, s) => a + s.lengthM, 0) / 1000, 1);
const city = {
  generatedAt: NOW.toISOString(),
  kpis: [
    { id: "km", label: "Streets measured", value: kmMeasured, unit: "km", delta: 4.8, deltaUnit: "%", better: "up", spark: spark(kmMeasured, 1.2, 2.4) },
    { id: "rides", label: "Rides aggregated", value: 8412, unit: "this week", delta: 12.4, deltaUnit: "%", better: "up", spark: spark(8412, 260, 180) },
    { id: "surface", label: "Surface index", value: 71.4, unit: "/100", delta: -0.6, deltaUnit: "pts", better: "up", spark: spark(71.4, 0.5, 0.05) },
    { id: "hotspots", label: "Active hard-brake hotspots", value: hotspots.filter((h) => h.hardBrakesWeek >= 8).length, unit: "", delta: 3, deltaUnit: "", better: "down", spark: spark(hotspots.filter((h) => h.hardBrakesWeek >= 8).length, 1.4, 0.3) },
    { id: "pm25", label: "Mean PM2.5 on measured streets", value: 14.2, unit: "µg/m³", delta: -3.1, deltaUnit: "%", better: "down", spark: spark(14.2, 0.6, -0.04), limit: 10, limitLabel: "EU 2030 limit" },
  ],
  districts: districtStats,
  monthlyHardBrakes: ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"].map((m, i) => ({
    month: m,
    hardBrakes: Math.round((i < 4 ? 640 : 900) + i * 42 + gauss() * 40 - (m === "2026-08" ? 330 : 0)),
    rides: Math.round((i < 4 ? 9000 : 15000) + i * 2600 - (m === "2026-08" ? 9000 : 0)),
  })),
  // hour × weekday city means (Mon..Sun)
  airNoise: Array.from({ length: 7 }, (_, dow) =>
    Array.from({ length: 24 }, (_, h) => {
      const weekend = dow >= 5;
      const t = weekend ? TRAFFIC[h] * 0.62 + (h >= 11 && h <= 21 ? 0.12 : 0) : TRAFFIC[h];
      const inv = h >= 7 && h <= 9 ? 1.12 : h >= 14 && h <= 17 ? 0.9 : 1;
      return {
        pm25: round(Math.max(5, (8.2 + 11.5 * t) * inv + gauss() * 0.4), 1),
        db: round(52 + 17 * t + (weekend && (h >= 22 || h <= 2) ? 3 : 0) + gauss() * 0.4, 1),
        rides: Math.round(1600 * t * (weekend ? 0.7 : 1) + rint(0, 40)),
      };
    }),
  ),
};

// Surface repair priorities.
const surfaceRanking = segments
  .map((s) => {
    const impacts = potholes.filter((p) => p.segmentId === s.id).reduce((a, p) => a + p.confirmations, 0) + (s.scores.comfort < 60 ? rint(2, 9) : rint(0, 2));
    const surfaceIndex = clamp(Math.round(s.scores.comfort - (s.surface.potholes ? 6 : 0) + gauss() * 2), 12, 96);
    return {
      segmentId: s.id,
      street: s.name,
      from: s.from,
      to: s.to,
      district: s.district,
      surfaceIndex,
      confirmedImpacts: impacts,
      riders30d: s.passes30d,
      trend: round(s.trend - (surfaceIndex < 50 ? 1.6 : 0), 1),
      lengthM: s.lengthM,
    };
  })
  .sort((a, b) => a.surfaceIndex - b.surfaceIndex);

// ------------------------------------------------------------------ write
const districtsOut = {
  type: "FeatureCollection",
  features: districtsFc.features.map((f) => ({
    type: "Feature",
    properties: { name: f.properties.NOM, code: f.properties.DISTRICTE },
    geometry: {
      type: f.geometry.type,
      coordinates:
        f.geometry.type === "Polygon"
          ? f.geometry.coordinates.map((r) => simplify(r, 9).map(ll5))
          : f.geometry.coordinates.map((p) => p.map((r) => simplify(r, 9).map(ll5))),
    },
  })),
};
const cityOutline = {
  type: "FeatureCollection",
  features: cityFc.features.map((f) => ({
    type: "Feature",
    properties: { name: "Barcelona" },
    geometry: {
      type: f.geometry.type,
      coordinates:
        f.geometry.type === "Polygon"
          ? f.geometry.coordinates.map((r) => simplify(r, 12).map(ll5))
          : f.geometry.coordinates.map((p) => p.map((r) => simplify(r, 12).map(ll5))),
    },
  })),
};

const write = (name, data) => {
  const file = path.join(OUT, name);
  fs.writeFileSync(file, JSON.stringify(data));
  console.log(`  ${name.padEnd(22)} ${(fs.statSync(file).size / 1024).toFixed(1)} KB`);
};
console.log(`Writing mock data → ${path.relative(ROOT, OUT)}`);
write("streets.json", segments);
write("districts.json", districtsOut);
write("city-outline.json", cityOutline);
write("potholes.json", potholes);
write("hotspots.json", hotspots);
write("routes.json", plannedRoutes);
write(
  "activities.json",
  activities.map(({ samples, segments: segs, route, ...rest }) => ({ ...rest, preview: simplify(route, 14).map(ll5) })),
);
write(
  "activity-details.json",
  Object.fromEntries(activities.map((a) => [a.id, { route: a.route, samples: a.samples, segments: a.segments }])),
);
write("people.json", { people, friends });
write("exposure.json", exposureDays);
write("city.json", city);
write("surface-ranking.json", surfaceRanking);

// ------------------------------------------------------------------ landing SVG data
// Pre-projected paths so the landing page ships no GeoJSON.
{
  const W = 1000;
  const H = 760;
  // Frame the featured ride: centred, with room for labels and callouts.
  const featuredRide = activities.find((a) => a.featured);
  const rxy = featuredRide.route.map(proj);
  const rMinX = Math.min(...rxy.map((p) => p[0]));
  const rMaxX = Math.max(...rxy.map((p) => p[0]));
  const rMinY = Math.min(...rxy.map((p) => p[1]));
  const rMaxY = Math.max(...rxy.map((p) => p[1]));
  const cx = (rMinX + rMaxX) / 2 + 60;
  const cy = (rMinY + rMaxY) / 2 - 120;
  const scale = Math.min((W * 0.72) / (rMaxX - rMinX), (H * 0.6) / (rMaxY - rMinY));
  const sx = ([x, y]) => [round(W / 2 + (x - cx) * scale, 1), round(H / 2 - (y - cy) * scale, 1)];
  const toPath = (coords) => coords.map((ll, i) => `${i ? "L" : "M"}${sx(proj(ll)).join(" ")}`).join("");
  const grid = [];
  for (const a of Object.values(A)) if (["Carrer de Casp", "Carrer de Sepúlveda", "Carrer d'Ausiàs Marc", "Carrer de Floridablanca"].indexOf(a.name) < 0) grid.push(toPath([fromUV(-2600, a.v), fromUV(4600, a.v)]));
  for (const b of Object.values(B)) grid.push(toPath([fromUV(b.u, -2400), fromUV(b.u, 2200)]));
  for (let v = -2700; v < 2400; v += 133.4) grid.push(toPath([fromUV(-2600, v), fromUV(4600, v)]));
  const districtsSvg = districtsFc.features.map((f) => ({
    name: f.properties.NOM,
    d: ringsOf(f.geometry)
      .map((p) => toPath(simplify(p[0], 14)) + "Z")
      .join(""),
  }));
  const cityPath = ringsOf(cityFc.features[0].geometry)
    .map((p) => toPath(simplify(p[0], 14)) + "Z")
    .join("");
  const featured = activities.find((a) => a.featured);
  const routePath = toPath(simplify(featured.route, 4));
  const routePts = featured.route.map((ll) => sx(proj(ll)));
  const cum = [0];
  for (let i = 1; i < routePts.length; i++) cum.push(cum[i - 1] + Math.hypot(routePts[i][0] - routePts[i - 1][0], routePts[i][1] - routePts[i - 1][1]));
  const evs = featured.events.map((e) => {
    const p = sx(proj(e.coordinates));
    let bi = 0;
    let bd = Infinity;
    routePts.forEach((q, i) => {
      const dd = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2;
      if (dd < bd) {
        bd = dd;
        bi = i;
      }
    });
    return { type: e.type, x: p[0], y: p[1], at: round(cum[bi] / cum[cum.length - 1], 3), time: e.time, value: e.value, street: e.street };
  });
  const diagonalPath = toPath([fromUV(-1400, vDiag(-1400)), fromUV(4380, vDiag(4380))]);
  const granViaPath = toPath([fromUV(-2600, A.granvia.v), fromUV(4600, A.granvia.v)]);
  const label = (name, ll) => ({ name, x: sx(proj(ll))[0], y: sx(proj(ll))[1] });
  const labels = [
    label("GRÀCIA", fromUV(-80, -1640)),
    label("EIXAMPLE", fromUV(500, -380)),
    label("SAGRADA FAMÍLIA", fromUV(1320, -820)),
    label("GLÒRIES", fromUV(2030, -220)),
    label("22@", fromUV(2560, 640)),
    label("CIUTADELLA", fromUV(1000, 900)),
  ].filter((l) => l.x > 40 && l.x < W - 40 && l.y > 40 && l.y < H - 30);
  const mapData = {
    width: W,
    height: H,
    city: cityPath,
    districts: districtsSvg,
    grid,
    diagonal: diagonalPath,
    granVia: granViaPath,
    route: routePath,
    start: sx(proj(featured.route[0])),
    end: sx(proj(featured.route[featured.route.length - 1])),
    events: evs,
    labels,
    ride: {
      distanceKm: round(featured.distanceM / 1000, 1),
      durationMin: Math.round(featured.durationS / 60),
      start: new Date(featured.startedAt).toTimeString().slice(0, 5),
      scores: featured.scores,
    },
  };
  // Mini street map for the phone mock-up.
  const phone = { w: 300, h: 420 };
  const pcx = proj(fromUV(900, -500));
  const pscale = 0.105;
  const psx = ([x, y]) => [round(phone.w / 2 + (x - pcx[0]) * pscale, 1), round(phone.h / 2 - (y - pcx[1]) * pscale, 1)];
  const ptoPath = (coords) => coords.map((ll, i) => `${i ? "L" : "M"}${psx(proj(ll)).join(" ")}`).join("");
  const phoneStreets = segments
    .filter((s) => {
      const [x, y] = psx(proj(s.coordinates[0]));
      return x > -40 && x < phone.w + 40 && y > -40 && y < phone.h + 40;
    })
    .map((s) => ({ d: ptoPath(s.coordinates), overall: s.hourly.air.map((a, h) => Math.round((a + s.hourly.comfort[h] + s.hourly.safety[h] + s.hourly.noise[h]) / 4)) }));
  const phoneRoutes = Object.fromEntries(plannedRoutes.map((r) => [r.goal, ptoPath(r.coordinates)]));
  // Whole-city district map for the City Insights preview.
  const cityFrame = { w: 560, h: 420 };
  const allPts = districtsFc.features.flatMap((f) => ringsOf(f.geometry).flatMap((p) => p[0].map(proj)));
  const cMinX = Math.min(...allPts.map((p) => p[0]));
  const cMaxX = Math.max(...allPts.map((p) => p[0]));
  const cMinY = Math.min(...allPts.map((p) => p[1]));
  const cMaxY = Math.max(...allPts.map((p) => p[1]));
  const cScale = Math.min((cityFrame.w - 20) / (cMaxX - cMinX), (cityFrame.h - 20) / (cMaxY - cMinY));
  const csx = ([x, y]) => [round(10 + (x - cMinX) * cScale, 1), round(cityFrame.h - 10 - (y - cMinY) * cScale, 1)];
  const cityDistricts = districtsFc.features.map((f) => {
    const name = f.properties.NOM;
    const stat = districtStats.find((d) => d.name === name);
    const ring = ringsOf(f.geometry)[0][0].map(proj);
    const cx = ring.reduce((a, p) => a + p[0], 0) / ring.length;
    const cy = ring.reduce((a, p) => a + p[1], 0) / ring.length;
    return {
      name,
      d: ringsOf(f.geometry)
        .map((p) => simplify(p[0], 22).map((c, i) => `${i ? "L" : "M"}${csx(proj(c)).join(" ")}`).join("") + "Z")
        .join(""),
      surfaceIndex: stat.surfaceIndex,
      label: csx([cx, cy]),
    };
  });
  const ts = `/* Generated by scripts/generate-mock-data.mjs — do not edit by hand. */
export const cityMap = ${JSON.stringify({ width: cityFrame.w, height: cityFrame.h, districts: cityDistricts })};

export const rideMap = ${JSON.stringify(mapData)} as const;

export const phoneMap = ${JSON.stringify({ ...phone, streets: phoneStreets, routes: phoneRoutes, ride: ptoPath(simplify(featured.route, 3)) })};
`;
  fs.writeFileSync(path.join(LANDING_OUT, "geo.ts"), ts);
  console.log(`  landing/data/geo.ts    ${(fs.statSync(path.join(LANDING_OUT, "geo.ts")).size / 1024).toFixed(1)} KB`);
}

console.log(
  `✓ ${segments.length} street segments (${kmMeasured} km), ${potholes.length} potholes, ${hotspots.length} hotspots, ${activities.length} activities (${activities.filter((a) => a.athleteId === "laia").length} Laia / ${activities.filter((a) => a.athleteId === "marc").length} Marc)`,
);
