# CLI Design

This document proposes a concrete CLI UX for `tidal`, with emphasis on the transaction flow and especially `tidal txn --confirm`.

## Problem

Today the CLI mixes two different audiences into one stdout stream:

- humans running one-off commands in a terminal
- automation that wants structured logs

For interactive commands, especially `tidal txn --confirm`, this creates poor UX:

- JSON logs are printed before and after the confirmation card
- the prompt is visually buried inside operational noise
- the final line is redundant with the structured log line
- user-cancelled runs still look like a successful automation run

The current behavior is acceptable for daemons and machine-operated commands, but it is too noisy for a human-controlled confirmation flow.

## Goals

- Make `tidal txn --confirm` feel like an interactive operator tool, not a daemon.
- Preserve structured machine-readable logs for automation and systemd use.
- Make stdout predictable: human-facing summaries for humans, structured events for machines.
- Keep the CLI low-drama and concise. No animated junk, no chatty spinners unless they add real value.
- Preserve enough detail for operators to make good decisions at confirmation time.

## Non-Goals

- Redesign the persistence model.
- Remove structured logging from daemon and service workflows.
- Build a full-screen TUI.

## Core Principle

The CLI should have explicit output modes.

- Text mode: concise, staged, readable, no JSON noise.
- JSON mode: structured events only.
- Auto selection: infer text vs machine-oriented behavior from flags and TTY.

The mistake today is not that the CLI logs too much. The mistake is that it emits the same logging stream for both interactive and automated workflows.

## Recommended Output Modes

For industry-standard CLI behavior, the public interface should prefer familiar names:

```text
--output text|json
```

Optional shorthand:

```text
--json
```

Recommended default behavior:

- `txn --confirm`: default to `text`
- `txn` without `--confirm`: default to `text` on TTY, `json` in explicitly non-interactive automation contexts
- `scan`: default to `text` when attached to a TTY, otherwise `json`
- `scan daemon`: default to `json`
- `txn daemon`: default to `json`
- `healthcheck`: default to `text`

Do not expose `auto` as a user-facing output value unless there is a strong reason. Auto-detection is useful internally, but `text` and `json` are more standard public choices than `human` and `auto`.

## Industry-Standard Conventions

This proposal intentionally follows common patterns used by established CLIs:

- explicit `--output` selection for format
- separate `--verbosity` control for detail level
- TTY-aware defaults, but explicit flags always win
- human-readable diagnostics in interactive flows
- structured output only when the user or environment clearly asks for it

That is closer to mainstream CLI practice than treating interactive commands and automation as the same logging surface.

## Recommended Verbosity

For industry-standard behavior, separate output format from verbosity.

Primary option:

```text
--verbosity quiet|minimal|normal|detailed|diagnostic
```

This matches Microsoft's published CLI guidance and is more standard than using only a boolean `--verbose`.

If you want a shorter path for operators, keep:

```text
--verbose
```

as an alias for:

```text
--verbosity detailed
```

## Optional Interaction Flag

The existing `--confirm` flag is good and domain-appropriate.

If you want to align even more closely with common CLI conventions, optionally add:

```text
-i, --interactive
```

for future flows that prompt without necessarily meaning "confirm a transaction now". Microsoft explicitly recommends `-i` for `--interactive`.

For the current transaction workflow, `--confirm` should remain the primary flag.

## Stream Rules

This is the most important part.

- Primary command output goes to `stdout`.
- Diagnostics go to `stderr`.
- In `text` mode, do not emit JSON event lines at all.
- In `json` mode, emit structured records on `stdout`.
- If startup fails before JSON mode can initialize, print the bootstrap error to `stderr` and exit nonzero.

This is closer to standard Unix CLI behavior than "JSON logs on stderr in text mode". Text mode should be human-readable on both streams.

That separation prevents prompt pollution and lets operators pipe stdout safely.

## Command Behavior Matrix

### `tidal scan`

TTY default:

- staged progress lines
- single completion summary
- warnings and errors on stderr

Non-TTY default:

- JSON events

### `tidal scan daemon`

- JSON events only
- no human progress formatting

### `tidal txn`

Dry run without confirm:

- compact shortlist summary
- optional candidate table
- final summary
- no raw JSON unless `--output json`

### `tidal txn --confirm`

This is the key mode.

Expected behavior:

1. Print one short preamble:
   - what scope is being evaluated
   - how many candidates were found
2. If zero candidates:
   - print `No eligible candidates`
   - exit `0`
3. If one or more candidates:
   - show compact ranked candidates summary
   - show the detailed confirmation card for the item or batch to be sent
4. Prompt
5. If declined:
   - print `Aborted. No transaction sent.`
   - print run id and candidate count
   - exit `1`
6. If accepted:
   - print `Submitting...`
   - print tx hash
   - print receipt outcome
   - print final summary

No JSON event lines should appear in between those steps by default.

## Proposed Human Output

### Dry run

```text
$ tidal txn --type fee-burner

Evaluating fee-burner candidates...
1 candidate eligible above threshold

1. yCRV Fee Burner
   Auction: 0xa00e...6693
   Token:   WFRAX
   Value:   ~$33,272.83

Dry run complete
Run ID:      f63ae151-4d99-408f-9c39-32e9ae72c8c2
Candidates:  1
Attempted:   0
Would kick:  1
```

### Interactive confirm, user declines

```text
$ tidal txn --confirm --type fee-burner

Evaluating fee-burner candidates...
1 candidate ready for submission

┌────────────────────────────────────────────────────────────────┐
│ Kick (1 of 1)                                                  │
│   Source:      yCRV Fee Burner (0xb911…1ee8)                   │
│   Auction:     0xa00e6b35c23442fa9d5149cba5dd94623ffe6693      │
│   Sell amount: 11,557.02 WFRAX (~$33,272.83)                   │
│   Start quote: 5,766 crvUSD (incl. 10% buffer)                 │
│   Min price:   4,979 crvUSD (minus 5% buffer)                  │
│   Profile:     volatile | decay 0.50%                          │
│   Gas est:     369,452 (~0.000018 ETH)                         │
│   Fees:        priority 0.00 gwei | max 2.5 gwei               │
└────────────────────────────────────────────────────────────────┘
Send this transaction? [y/N]: n

Aborted. No transaction sent.
Run ID:      f63ae151-4d99-408f-9c39-32e9ae72c8c2
Candidates:  1
Type:        fee-burner
```

### Interactive confirm, user accepts

```text
$ tidal txn --confirm --type fee-burner

Evaluating fee-burner candidates...
1 candidate ready for submission

[confirmation card]
Send this transaction? [y/N]: y

Submitting transaction...
Tx hash:      0xabc...1234
Waiting for receipt...
Confirmed.

Run ID:       f63ae151-4d99-408f-9c39-32e9ae72c8c2
Type:         fee-burner
Attempted:    1
Succeeded:    1
Failed:       0
```

## Status Language

Text mode should use user-facing language, not internal run-status language.

Recommended final labels:

- `No eligible candidates`
- `Aborted. No transaction sent.`
- `Submitted`
- `Confirmed`
- `Failed`

Avoid showing:

- `txn_run_started`
- `txn_candidates_ranked`
- `txn_run_completed`
- `status=SUCCESS`

in text mode unless higher verbosity is explicitly requested.

## Candidate Presentation

For interactive text mode:

- show at most the top 3 shortlisted candidates before the confirmation card
- if only one candidate exists, skip the ranked list and go straight to `1 candidate ready for submission`
- for batches, show a short numbered list with source, token, USD value, and pricing profile

Do not dump raw structured candidate payloads.

## Confirmation Card Rules

The existing card is directionally good. Keep the card, but tighten it:

- keep `Source`, `Auction`, `Sell amount`, `Start quote`, `Min price`, `Profile`, `Gas est`, `Fees`
- remove duplicate information when it does not help the decision
- keep formatting stable so operators learn the shape
- do not interleave logs between card render and prompt

## Error Presentation

In text mode:

- one clear top-line error message
- one optional cause line
- detailed tracebacks only with `--verbosity diagnostic`

Example:

```text
Preparation failed.
Reason: live balance changed during estimation
```

For multiple failures:

- print grouped counts first
- print individual failures only with `--verbose`

## Logging Policy

Recommended logging behavior by mode:

### `--output text`

- operational summaries rendered by the CLI layer
- warnings and errors rendered as readable diagnostics on stderr
- no JSON logs interleaved with prompts or summaries

### `--output json`

- structured records only on stdout
- no human summaries except fatal startup errors written to stderr
- stable event schemas per command

### Default selection

- if `--confirm` and both stdin/stdout are TTYs: behave as `text`
- if running a daemon command: behave as `json`
- otherwise prefer `text` on TTY and require explicit `--output json` for machine-readable mode

## Implementation Notes

The cleanest implementation is to separate command rendering from service logging.

Suggested approach:

1. Add an `OutputMode` enum in the CLI layer with `text` and `json`.
2. Extend `configure_logging()` to accept:
   - `output_mode`
   - `verbosity`
   - optional `stream`
3. Add a small CLI renderer for:
   - human progress lines
   - candidate shortlist summary
   - final run summary
   - error summary
4. In text mode:
   - do not emit JSON records
   - keep warnings/errors visible on stderr as readable text
5. In JSON mode:
   - preserve current behavior

## Suggested Flags

Keep:

- `--confirm`
- `--type`

Add:

- `--output text|json`
- `--verbosity quiet|minimal|normal|detailed|diagnostic`

Keep optionally:

- `--verbose` as alias for `--verbosity detailed`
- `--json` as alias for `--output json`

Optional later additions:

- `--show-candidates`
- `--quiet`
- `--no-color`

## Exit Codes

Recommended semantics:

- `0`: command completed successfully, including dry-run success and no eligible candidates
- `1`: command aborted or failed after execution began
- `2`: bad CLI usage
- `130`: interrupted by signal such as `Ctrl-C`

For industry-standard CLI behavior, a destructive command that the user explicitly declines should generally be treated as `aborted`, not `success`. That means nonzero exit status is more conventional than `0`, even though the message should clearly say no transaction was sent.

## Acceptance Criteria

This design is successful when:

- `tidal txn --confirm --type fee-burner` prints no JSON event lines by default
- prompts are never split by structured logs
- the operator can understand what will happen in under 10 seconds
- daemons still emit structured logs for machines
- explicit `--output json` reproduces machine-readable behavior
- `stdout` remains safe to pipe in JSON mode
- diagnostics remain readable in text mode

## First Implementation Slice

If this is done incrementally, the first slice should be:

1. Add `--output`
2. Add `--verbosity`
3. Make `txn --confirm` default to `text`
4. Remove structured JSON logs from text mode
5. Keep machine-readable output behind `--output json`
6. Replace the noisy pre/post JSON lines with:
   - `Evaluating ...`
   - candidate count
   - confirmation card
   - final concise summary

That alone would solve most of the current UX problem.
