# Tidal Docs

Tidal is Yearn's auction operations stack. It scans strategy and fee-burner inventories, caches balances and prices in SQLite, exposes that state through a FastAPI control plane, and lets CLI clients prepare and broadcast auction transactions with local wallet signing.

## Start Here

- Most users: [Install](install.md) then [CLI Client Guide](operator-guide.md)
- Running the shared server: [Install](install.md) then [Server Operator Guide](server-ops.md)
- Developing from source: [Install](install.md) then [Local Development](local-dev.md)

## Docs Map

- Setup and first-day workflows:
  [Install](install.md), [CLI Client Guide](operator-guide.md), [Server Operator Guide](server-ops.md)
- Exact command docs:
  [CLI Command Map](cli-reference.md)
- Runtime files and settings:
  [Configuration](config.md)
- System behavior:
  [Architecture](architecture.md), [Pricing](pricing.md), [Kick Selection](kick-selection.md)
- HTTP surface:
  [API Reference](api-reference.md)

## Source Of Truth

These docs are meant to explain the current system, not preserve historical plans. When behavior disagrees with prose, prefer the code:

- CLI surface: `tidal --help` and `tidal-server --help`
- API surface: FastAPI routes in `tidal/api/routes/`
- Config schema: `tidal/config.py`
