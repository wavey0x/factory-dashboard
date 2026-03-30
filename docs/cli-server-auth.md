# Server Operator: `tidal-server auth`

`tidal-server auth` manages bearer tokens for authenticated API use.

## Subcommands

- `create`
- `list`
- `revoke`

## Common Invocations

Create a key:

```bash
tidal-server auth create --label alice
```

List known keys:

```bash
tidal-server auth list
```

Revoke a key:

```bash
tidal-server auth revoke alice
```

## Notes

- The plaintext key is shown once at creation time.
- The server stores only the hashed key value.
- The label is the current operator identity shown in audit history and auth listings.
