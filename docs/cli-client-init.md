# CLI Client: `tidal init`

`tidal init` creates the default runtime home for both the CLI client and the server operator.

## Common Invocation

```bash
tidal init
```

Overwrite the scaffolded files intentionally:

```bash
tidal init --force
```

## What It Writes

The command creates:

- `~/.tidal/config.yaml`
- `~/.tidal/.env`
- `~/.tidal/kick.yaml`
- `~/.tidal/state/`
- `~/.tidal/state/operator/`
- `~/.tidal/run/`

## When To Use It

Run `tidal init` when:

- setting up a new workstation
- setting up a new server host
- you want to regenerate the latest scaffold files with `--force`

## What To Edit Next

After initialization, the usual next steps for a CLI client are:

1. Put `TIDAL_API_KEY` in `~/.tidal/.env`.
2. If you are using `https://api.tidal.wavey.info`, get that API key from wavey.
3. Confirm `tidal_api_base_url` in `~/.tidal/config.yaml`.
4. Leave `~/.tidal/kick.yaml` alone on a normal workstation. API-backed kick pricing, ignore rules, and cooldowns come from the server-side file.
5. Add keystore-related values if you will broadcast locally.

See [Configuration](config.md) for the setting-level breakdown.
