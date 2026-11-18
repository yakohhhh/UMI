#!/usr/bin/env sh
# Builds the SIL, runs every scenario in test/scenarios through the real
# firmware logic and checks each .umis with the reference codec:
# complete log, every flag signature valid.
#
#   firmware/scripts/run-sil.sh [OUT_DIR]      (default: firmware/.pio/sil-out)
set -eu

FIRMWARE="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$FIRMWARE/.." && pwd)"
OUT="${1:-$FIRMWARE/.pio/sil-out}"
# RFC 6979 A.2.5's published P-256 key: TEST ONLY, never on a real Clip.
KEY=c9afa9d845ba75166b5c215767b1d6934e50c3db36e89b127b8a622b120f6721
PUBKEY="$FIRMWARE/test/scenarios/sil-test-key.pub.pem"
DEVICE=00a1b2c3d4e5f601

(cd "$FIRMWARE" && pio run -e sil -s)
mkdir -p "$OUT"
session=1
for scenario in "$FIRMWARE"/test/scenarios/*.scn; do
    name="$(basename "$scenario" .scn)"
    echo "== $name"
    "$FIRMWARE/.pio/build/sil/program" --scenario "$scenario" --out "$OUT/$name.umis" \
        --device-id "$DEVICE" --session-id "$session" --key-hex "$KEY" --activity ride
    session=$((session + 1))
done

if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found: skipping the decode with umi_protocol" >&2
    exit 0
fi
for log in "$OUT"/*.umis; do
    summary="$(cd "$REPO" && uv run --quiet python -m umi_protocol inspect "$log")"
    echo "$summary"
    if ! echo "$summary" | grep -q "^status *complete"; then
        echo "$log: not a complete session log" >&2
        exit 1
    fi
    (cd "$REPO" && uv run --quiet python -m umi_protocol verify --pubkey "$PUBKEY" "$log")
done
