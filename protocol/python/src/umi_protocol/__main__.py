"""``umi-protocol`` (or ``python -m umi_protocol``): look into, trim and verify session logs.

Exit status: 0 on success, 1 when the input is invalid or a flag fails verification,
2 on a usage error, 3 when ``trim`` finds nothing that may be uploaded.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from enum import IntEnum
from pathlib import Path
from typing import Any

from .canonical import header_to_dict, to_json
from .constants import Activity, FlagSource, HazardKind, HeaderFlag, Lang, RecordType
from .records import Flag, UnknownRecord
from .session import Session
from .signing import load_public_key_pem, verify_flag
from .trim import trim_session

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_NOTHING_TO_UPLOAD = 3


def _name(enum: type[IntEnum], value: int) -> str:
    return enum(value).name.lower() if value in enum else str(value)


def _clock(t_ms: int) -> str:
    seconds = t_ms // 1000
    return f"{seconds // 3600:d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


def summarize(session: Session) -> dict[str, Any]:
    """What ``inspect`` reports, as plain JSON-ready values."""
    undone = {flag.seq for flag in session.of_type(Flag)} - {flag.seq for flag in session.flags}
    counts = Counter(
        f"unknown_{r.type}" if isinstance(r, UnknownRecord) else r.TYPE.name.lower() for r in session.records
    )
    started = session.started_at
    trim = session.trim
    return {
        "header": header_to_dict(session.header),
        "complete": session.decoded.complete,
        "issue": session.decoded.issue,
        "started_at": None if started is None else started.isoformat(timespec="milliseconds"),
        "duration_ms": session.duration_ms,
        "distance_m": round(session.distance_m, 1),
        "records": dict(sorted(counts.items())),
        "trim": None if trim is None else {"start_m": trim.start_m, "end_m": trim.end_m},
        "flags": [
            {
                "seq": flag.seq,
                "t_ms": flag.t_ms,
                "source": _name(FlagSource, flag.source),
                "kind": _name(HazardKind, flag.kind),
                "confidence": flag.confidence,
                "lang": _name(Lang, flag.lang),
                "signed": flag.is_signed,
                "undone": flag.seq in undone,
            }
            for flag in session.of_type(Flag)
        ],
    }


def _print_summary(path: Path, size: int, summary: dict[str, Any]) -> None:
    header = summary["header"]
    tags = [str(flag.name).lower() for flag in HeaderFlag if header["header_flags"] & flag]
    fw = ".".join(map(str, header["fw_version"]))
    status = "complete" if summary["complete"] else f"incomplete: {summary['issue']}"
    lines = [
        f"file      {path} ({size} bytes)",
        f"device    {header['device_id']} · session {header['session_id']} · "
        f"{_name(Activity, header['activity'])} · hw {header['hw_rev']} · fw {fw}"
        + "".join(f" · {tag}" for tag in tags),
        f"started   {summary['started_at'] or 'unknown (no TIME_SYNC)'}",
        f"duration  {_clock(summary['duration_ms'])}",
        f"distance  {summary['distance_m'] / 1000:.2f} km",
        f"status    {status}",
        "records   " + ", ".join(f"{name} {count}" for name, count in summary["records"].items()),
    ]
    if summary["trim"]:
        lines.append(f"trimmed   {summary['trim']['start_m']} m at the start, {summary['trim']['end_m']} m at the end")
    for flag in summary["flags"]:
        keyword = "" if flag["kind"] == "none" else f" {flag['kind']} ({flag['confidence']} %, {flag['lang']})"
        notes = ("signed" if flag["signed"] else "unsigned") + (", undone" if flag["undone"] else "")
        lines.append(f"flag #{flag['seq']:<3} {_clock(flag['t_ms'])}  {flag['source']}{keyword}  [{notes}]")
    print("\n".join(lines))


def _inspect(args: argparse.Namespace) -> int:
    data = args.file.read_bytes()
    summary = summarize(Session.from_bytes(data))
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_summary(args.file, len(data), summary)
    return EXIT_OK


def _decode(args: argparse.Namespace) -> int:
    print(to_json(Session.from_bytes(args.file.read_bytes()).decoded), end="")
    return EXIT_OK


def _trim(args: argparse.Namespace) -> int:
    result = trim_session(args.input.read_bytes())
    if result.data is None:
        print(f"nothing to upload: {result.reason}", file=sys.stderr)
        return EXIT_NOTHING_TO_UPLOAD
    args.output.write_bytes(result.data)
    dropped = ", ".join(f"{_name(RecordType, t)} {n}" for t, n in sorted(result.dropped.items())) or "none"
    print(f"trimmed {result.start_m} m + {result.end_m} m of {result.total_m:.0f} m; dropped {dropped}")
    return EXIT_OK


def _verify(args: argparse.Namespace) -> int:
    public_key = load_public_key_pem(args.pubkey.read_bytes())
    session = Session.from_bytes(args.file.read_bytes())
    header = session.header
    flags = session.of_type(Flag)
    failures = 0
    for flag in flags:
        if not flag.is_signed:
            verdict = "unsigned"
        elif verify_flag(public_key, header.device_id, header.session_id, flag):
            verdict = "ok"
        else:
            verdict = "BAD SIGNATURE"
        failures += verdict != "ok"
        print(f"flag #{flag.seq:<3} {_clock(flag.t_ms)}  {verdict}")
    print(f"{len(flags) - failures}/{len(flags)} flags verified")
    return EXIT_OK if failures == 0 else EXIT_INVALID


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="umi-protocol", description=__doc__.splitlines()[0] if __doc__ else None)
    commands = parser.add_subparsers(dest="command", required=True)

    inspect = commands.add_parser("inspect", help="summarise a session log")
    inspect.add_argument("file", type=Path)
    inspect.add_argument("--json", action="store_true", help="print the summary as JSON")
    inspect.set_defaults(run=_inspect)

    decode = commands.add_parser("decode", help="print the canonical JSON decoding (as in protocol/vectors)")
    decode.add_argument("file", type=Path)
    decode.set_defaults(run=_decode)

    trim = commands.add_parser("trim", help="apply the privacy trim, as the phone does before upload")
    trim.add_argument("input", type=Path)
    trim.add_argument("output", type=Path)
    trim.set_defaults(run=_trim)

    verify = commands.add_parser("verify", help="check the signature of every flag")
    verify.add_argument("file", type=Path)
    verify.add_argument("--pubkey", type=Path, required=True, help="the Clip's public key (PEM)")
    verify.set_defaults(run=_verify)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    run: Callable[[argparse.Namespace], int] = args.run
    try:
        return run(args)
    except (ValueError, OSError) as exc:  # ProtocolError is a ValueError, as are bad PEM keys
        print(f"umi-protocol: {exc}", file=sys.stderr)
        return EXIT_INVALID


if __name__ == "__main__":
    sys.exit(main())
