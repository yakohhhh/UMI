"""``umi-sim``: virtual Clips and riders on the Barcelona street graph."""

from __future__ import annotations

import asyncio
import itertools
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, NoReturn

import httpx
import typer
from umi_protocol import Header, ProtocolError, Session, trim_session

from .clip import KeyStore, NoSessionError, Recording, UnknownClipError, VirtualClip, default_keys_dir
from .fleet import FleetReport, PlannedRide, Progress, RiderProfile, plan, run_fleet
from .network import RouteError, RouteGoal
from .phone import BackendError, Phone
from .places import PLACES, UnknownPlaceError, resolve
from .rider import Vehicle
from .scenario import write_scenario
from .simulation import LOCAL_TZ, City, RideSpec, SimulatedRide, simulate
from .world import DataError

# simulator/out in the repository (gitignored).
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "out"

app = typer.Typer(
    help="UMI Clip simulator: virtual riders record real .umis sessions; the simulated phone trims and uploads them.",
    no_args_is_help=True,
    add_completion=False,
)

DataOption = Annotated[
    Path | None,
    typer.Option("--data", help="Mock datasets (default: $UMI_SIM_DATA_DIR, else src/lib/mock/data)."),
]
KeysOption = Annotated[
    Path | None,
    typer.Option(
        "--keys", help="Where simulated Clips keep their keys (default: $UMI_SIM_KEYS_DIR, else ~/.umi-sim/keys)."
    ),
]
FromOption = Annotated[str, typer.Option("--from", help="Place name (see `places`) or lat,lon.")]
ToOption = Annotated[str, typer.Option("--to", help="Place name (see `places`) or lat,lon.")]
AtOption = Annotated[
    str | None,
    typer.Option("--at", help="Departure, ISO 8601; Barcelona time unless it has an offset. Default: now."),
]
RiderOption = Annotated[str, typer.Option("--rider", help="Rider id; their Clip is provisioned on first use.")]
VehicleOption = Annotated[Vehicle | None, typer.Option("--vehicle", help="Default: the rider's own.")]
RouteOption = Annotated[RouteGoal, typer.Option("--route", help="Route choice.")]
SeedOption = Annotated[int, typer.Option("--seed", help="Same seed, same ride.")]


def _fail(message: str) -> NoReturn:
    typer.echo(f"error: {message}", err=True)
    raise typer.Exit(2)


def _city(data: Path | None) -> City:
    try:
        return City.load(data)
    except DataError as exc:
        _fail(str(exc))


def _departure(text: str | None) -> datetime:
    if text is None:
        return datetime.now(LOCAL_TZ).replace(second=0, microsecond=0)
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        _fail(f"--at {text!r} is not an ISO 8601 date and time (e.g. 2026-11-18T07:50)")
    return value if value.tzinfo else value.replace(tzinfo=LOCAL_TZ)


def _simulate(
    city: City,
    origin: str,
    destination: str,
    *,
    at: str | None,
    rider: str,
    vehicle: Vehicle | None,
    goal: RouteGoal,
    seed: int,
) -> tuple[SimulatedRide, str]:
    """The ride and a label for it, with the rider's own habits."""
    try:
        start_label, start = resolve(origin)
        end_label, end = resolve(destination)
        profile = RiderProfile.for_id(rider, city.network)
        spec = RideSpec(
            waypoints=(start, end),
            depart=_departure(at),
            vehicle=vehicle or profile.vehicle,
            seed=seed,
            goal=goal,
            habits=profile.habits,
            pace=profile.pace,
        )
        return simulate(city, spec), f"{start_label} → {end_label}"
    except (UnknownPlaceError, RouteError, ValueError) as exc:
        _fail(str(exc))


@app.command()
def places() -> None:
    """List the named places rides can start from and go to."""
    width = max(len(p.name) for p in PLACES)
    for p in PLACES:
        typer.echo(
            f"{p.name:<{width}}  {p.lat:.5f},{p.lon:.5f}  {p.district:<11} {p.junction} [{', '.join(p.role_names)}]"
        )


@app.command()
def network(data: DataOption = None) -> None:
    """Report how much of the mock street network is routable."""
    typer.echo(f"Street network: {_city(data).network.connectivity}")


@app.command()
def ride(
    *,
    origin: FromOption,
    destination: ToOption,
    at: AtOption = None,
    rider: RiderOption = "sim-0001",
    vehicle: VehicleOption = None,
    goal: RouteOption = RouteGoal.FASTEST,
    seed: SeedOption = 1,
    out: Annotated[
        Path | None, typer.Option("--out", help="Session file (default: simulator/out/<rider>/...).")
    ] = None,
    keys: KeysOption = None,
    data: DataOption = None,
) -> None:
    """Simulate one ride and write the session the Clip would record."""
    city = _city(data)
    simulated, label = _simulate(city, origin, destination, at=at, rider=rider, vehicle=vehicle, goal=goal, seed=seed)
    try:
        clip = KeyStore(keys or default_keys_dir()).clip_for(rider)
        recording = VirtualClip(clip).record(simulated)
    except (ValueError, NoSessionError, UnknownClipError) as exc:
        _fail(str(exc))
    local_start = recording.started_at.astimezone(LOCAL_TZ)
    path = out or DEFAULT_OUT / rider / f"{local_start:%Y%m%d-%H%M}-{recording.session_id}.umis"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(recording.data)

    session = Session.from_bytes(recording.data)
    route = simulated.route
    typer.echo(f"wrote {path} ({len(recording.data):,} bytes)")
    typer.echo(
        f"Clip {clip.device_hex} ({clip.serial}) · session {recording.session_id} · {simulated.spec.vehicle} · "
        f"{label}, {goal} route, {route.length / 1000:.1f} km via {', '.join(route.via)}"
    )
    typer.echo(_summary(recording, session))
    trim = trim_session(recording.data)
    if trim.data is None:
        typer.echo(f"the phone would not upload it: {trim.reason}")
    else:
        typer.echo(f"the phone trims {trim.start_m} m + {trim.end_m} m and uploads {len(trim.data):,} bytes")


def _summary(recording: Recording, session: Session) -> str:
    start = recording.started_at.astimezone(LOCAL_TZ)
    return (
        f"started {start:%Y-%m-%d %H:%M:%S %Z} · {recording.duration_ms / 60000:.0f} min · "
        f"{session.distance_m / 1000:.2f} km recorded · {len(session.records):,} records · "
        f"{recording.events} events · {recording.flags} flags ({recording.undos} undone)"
    )


@app.command()
def upload(
    files: Annotated[list[Path], typer.Argument(help="Session files written by a simulated Clip.", exists=True)],
    api: Annotated[str, typer.Option("--api", envvar="UMI_API_URL", help="Backend base URL.")],
    keys: KeysOption = None,
    data: DataOption = None,
) -> None:
    """Play the phone: pair the Clip, trim each session and upload it."""
    city = _city(data)
    store = KeyStore(keys or default_keys_dir())
    failures = asyncio.run(_upload(city, store, files, api))
    if failures:
        raise typer.Exit(1)


async def _upload(city: City, store: KeyStore, files: list[Path], api: str) -> int:
    failures = 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        phone = Phone(client, api)
        for path in files:
            raw = path.read_bytes()
            try:
                clip = store.find(Header.from_bytes(raw).device_id)
                profile = RiderProfile.for_id(clip.rider_id, city.network)
                result = await phone.sync(await phone.pair(clip, profile.athlete), raw)
            except (ProtocolError, UnknownClipError, BackendError) as exc:
                typer.echo(f"{path}: {exc}", err=True)
                failures += 1
                continue
            if result.receipt is None:
                typer.echo(f"{path}: not uploaded, {result.trim.reason}")
                continue
            r = result.receipt
            typer.echo(
                f"{path}: activity {r.activity_id} "
                f"({'already uploaded' if r.duplicate else 'created'}) · {r.segments_matched} segments · "
                f"flags {r.flags_accepted} accepted, {r.flags_rejected} rejected · {r.events} events · "
                f"trimmed {result.trim.start_m} m + {result.trim.end_m} m"
            )
    return failures


@app.command()
def fleet(
    *,
    riders: Annotated[int, typer.Option("--riders", min=1, help="Number of riders (sim-0001...).")] = 40,
    days: Annotated[int, typer.Option("--days", min=1, help="Days to simulate.")] = 14,
    seed: SeedOption = 7,
    start: Annotated[
        str | None, typer.Option("--start", help="First day, YYYY-MM-DD (default: the last DAYS days to yesterday).")
    ] = None,
    api: Annotated[str | None, typer.Option("--api", envvar="UMI_API_URL", help="Upload to this backend.")] = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write the Clips' files here (default without --api: simulator/out/fleet)."),
    ] = None,
    concurrency: Annotated[int, typer.Option("--concurrency", min=1, help="Uploads in flight.")] = 8,
    keys: KeysOption = None,
    data: DataOption = None,
) -> None:
    """Simulate riders x days of commutes, runs and weekend rides; write the files and/or upload them."""
    city = _city(data)
    try:
        first = date.fromisoformat(start) if start else date.today() - timedelta(days=days)
    except ValueError:
        _fail(f"--start {start!r} is not a date (YYYY-MM-DD)")
    rides = plan(city.network, riders=riders, days=days, start=first, seed=seed)
    out_dir = out or (None if api else DEFAULT_OUT / "fleet")
    typer.echo(f"{len(rides)} rides for {riders} riders from {first} to {first + timedelta(days=days - 1)}")

    recorded = itertools.count(1)

    def progress(planned: PlannedRide, recording: Recording) -> None:
        if (n := next(recorded)) % 100 == 0:
            typer.echo(f"  {n}/{len(rides)} recorded", err=True)

    keystore = KeyStore(keys or default_keys_dir())
    report = asyncio.run(
        _fleet(city, rides, api=api, out_dir=out_dir, concurrency=concurrency, keys=keystore, progress=progress)
    )
    typer.echo(_fleet_summary(report, out_dir, api))
    for error in report.errors[:5]:
        typer.echo(f"  {error}", err=True)
    if report.failed:
        raise typer.Exit(1)


async def _fleet(
    city: City,
    rides: list[PlannedRide],
    *,
    api: str | None,
    out_dir: Path | None,
    concurrency: int,
    keys: KeyStore,
    progress: Progress,
) -> FleetReport:
    if api is None:
        return await run_fleet(city, rides, keys=keys, out_dir=out_dir, progress=progress)
    async with httpx.AsyncClient(timeout=30.0, limits=httpx.Limits(max_connections=concurrency)) as client:
        phone = Phone(client, api)
        return await run_fleet(
            city, rides, keys=keys, out_dir=out_dir, phone=phone, concurrency=concurrency, progress=progress
        )


def _fleet_summary(report: FleetReport, out_dir: Path | None, api: str | None) -> str:
    lines = [f"recorded {report.recorded} of {report.planned} rides ({report.not_started} never started)"]
    if out_dir is not None:
        lines.append(f"wrote {report.written} files under {out_dir}")
    if api is not None:
        lines.append(
            f"uploaded {report.uploaded} to {api} ({report.duplicates} already there, {report.too_short} too short "
            f"to upload, {report.failed} failed) · flags {report.flags_accepted} accepted, "
            f"{report.flags_rejected} rejected · {report.events} events"
        )
    return "\n".join(lines)


@app.command()
def scenario(
    *,
    origin: FromOption,
    destination: ToOption,
    out: Annotated[Path, typer.Option("--out", help="Scenario file.")] = DEFAULT_OUT / "scenario.txt",
    at: AtOption = None,
    rider: RiderOption = "sim-0001",
    vehicle: VehicleOption = None,
    goal: RouteOption = RouteGoal.FASTEST,
    seed: SeedOption = 1,
    data: DataOption = None,
) -> None:
    """Export a ride as a firmware SIL scenario (raw sensor streams, protocol/sil-scenario.md)."""
    city = _city(data)
    simulated, label = _simulate(city, origin, destination, at=at, rider=rider, vehicle=vehicle, goal=goal, seed=seed)
    out.parent.mkdir(parents=True, exist_ok=True)
    title = (
        f"rider={rider} route={label} vehicle={simulated.spec.vehicle} "
        f"depart={simulated.spec.depart.isoformat()} seed={seed}"
    )
    with out.open("w", encoding="utf-8", newline="\n") as file:
        info = write_scenario(simulated, file, title=title)
    typer.echo(f"wrote {out}: {info.lines:,} lines, {info.duration_ms / 60000:.1f} min from power-on")
