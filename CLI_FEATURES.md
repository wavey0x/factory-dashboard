# CLI Features

## `tidal auction enable-tokens` optional auction prompt

### Goal

Allow this interactive form:

```bash
tidal auction enable-tokens
```

and, when running in a TTY, prompt once for the auction address.

Keep the current canonical form unchanged:

```bash
tidal auction enable-tokens 0xAuction
```

### Why

- Better operator UX when working through several auctions manually.
- Faster reruns without editing the previous shell command.
- No downside for scripting if the positional form stays primary.

### Design

- Make `auction_address` optional in `tidal/auction_cli.py`.
- If `auction_address` is omitted and stdin is interactive, prompt:
  `Auction address`
- Immediately normalize and validate with the existing address helper.
- If `auction_address` is omitted and stdin is not interactive, fail with the current required-argument style error.

### Constraints

- No persistent “last auction” state.
- No hidden defaults.
- No extra prompts for other arguments in this change.
- JSON / scripted usage must remain deterministic.
- Positional `AUCTION` remains the documented primary interface.

### Implementation

1. Change the `enable_tokens` command signature so `auction_address` is optional.
2. Add a small helper near the command to resolve the auction address:
   - use the provided positional value if present
   - otherwise prompt only when running in a TTY
   - otherwise raise a clean CLI error
3. Reuse `normalize_cli_address(..., param_hint="AUCTION")` after prompt entry.
4. Keep the rest of the command flow unchanged.

### Testing

- Existing positional path still works.
- Interactive prompt path works when no auction is provided.
- Non-interactive invocation without auction exits cleanly.
- Invalid prompted address fails with the same normalization error path.

### Notes

- This is a good narrow UX affordance.
- It only becomes over-engineered if we start adding prompt-driven fallbacks for many command arguments or introduce remembered state.
