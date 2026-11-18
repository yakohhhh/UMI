# Contributing to UMI

## Workflow

1. Pick an issue on the [project board](https://github.com/users/yakohhhh/projects/3) or open one with a template (feature, bug, hardware task). Assign yourself and move it to *In progress*.
2. Branch from `main`: `<area>/<short-topic>`, e.g. `firmware/ble-transfer`, `backend/hazard-expiry`, `web/catalan`.
3. Keep pull requests small and about one thing. Link the issue (`Closes #12`) and fill in the template, privacy impact included.
4. One approving review before merging; changes to `protocol/` need a review from someone working on another component, because they change every consumer.
5. Squash or rebase; no merge commits on branches.

Commit messages: imperative subject under 72 characters that says what changes (`Add chunked session transfer to the BLE service`), then a body explaining why when it is not obvious. No prefixes, no ticket numbers in the subject.

## Running the suites

| Area | Commands (from the repository root) |
| --- | --- |
| Web | `npm ci`, `npm run typecheck`, `npm run build` |
| Python (protocol, backend, simulator) | `uv sync --all-packages --all-groups`, `uv run ruff format --check`, `uv run ruff check`, `uv run mypy protocol/python/src backend/src simulator/src`, `uv run pytest` |
| Firmware | `cd firmware && pio test -e native && pio run -e sil && pio run -e devkit && pio run -e clip` |
| End to end | `(cd firmware && pio run -e sil) && uv run pytest -m e2e` |
| Generated files | `python3 protocol/codegen/generate.py --check`, `uv run python protocol/vectors/generate.py --check`, `npm run contract:generate` (no diff) |

CI runs the same commands, only for the areas a pull request touches (`.github/workflows/`).

## Changing the protocol

`protocol/constants.toml` and `protocol/README.md` are the contract between the Clip, the phone and the backend. Treat a change like an API change:

1. Edit the TOML or the spec, never a generated file.
2. `python3 protocol/codegen/generate.py` regenerates the C header, the Python module and the TypeScript module.
3. Update every codec and consumer in the same pull request, regenerate the golden vectors if the bytes change (`protocol/vectors/generate.py`), and say in the description why the threshold or format moved: a threshold change changes every score.
4. Follow the versioning rules in `protocol/README.md` §5.

## Architecture decisions

A decision that is expensive to reverse (a new datastore, a wire format change, an identity scheme) gets an ADR in `docs/architecture/adr/`: copy an existing record, number it, link it from the pull request. A decision that changes gets a new record that supersedes the old one.

## Definition of done

- Tests cover the change and every suite of the areas it touches passes.
- The component README, `docs/architecture` or an ADR says what a newcomer needs to know.
- Privacy impact stated: what is collected, what leaves the Clip or the phone, the 200 m trim, the 3/5-rider thresholds, rounding and retention.
- Code, comments and UI copy in English.
