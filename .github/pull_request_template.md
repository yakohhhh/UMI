## What and why

<!-- What changes and the problem it solves. Link the issue ("Closes #123") and the ADR if this implements one. -->

## How it was tested

<!-- The commands you ran and what they showed. For firmware, say where it ran: host tests, SIL, DevKitC or the Clip board. -->

## Checklist

- [ ] Tests added or updated; the suites of every area this touches pass locally (CONTRIBUTING.md, "Running the suites")
- [ ] Docs updated: the component README, `docs/architecture`, a new ADR for a decision that is expensive to reverse
- [ ] If `protocol/constants.toml` or the wire format changed: regenerated with `python3 protocol/codegen/generate.py`, every consumer updated, golden vectors re-checked
- [ ] Privacy impact stated below

## Privacy impact

<!-- Does this change what is collected, what leaves the Clip or the phone, the 200 m trim, the 3/5-rider thresholds, rounding or retention? "None" is a valid answer. -->
