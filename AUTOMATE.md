# Tidal Kick Automation Plan

## Goal

Run unattended kick attempts from the server every 15 minutes.

Policy:

- Strategy sources require a usable Curve quote.
- Fee-burner sources may run without a Curve quote.
- Minimum sell-side liquidity is `$250`.

## Server Config

Set this in the server checkout's `config/server.yaml`:

```yaml
txn_usd_threshold: 250
txn_require_curve_quote: true
```

Remove any `TXN_USD_THRESHOLD` environment override, or set it to `250` too.

## Core CLI Refactor

Add a first-class headless mode:

```bash
tidal kick run --headless
```

`--headless` should:

- run unattended without a confirmation prompt
- emit plain line-oriented logs, not Rich panels or spinners
- treat normal no-op outcomes as success: no ready candidates, prepare skips, stale prepared tx skips
- keep real failures nonzero: config errors, API errors, signing errors, broadcast errors
- keep `--json` as data output for scripts, separate from headless operator logs

Example log shape:

```text
kick.run.start source_type=strategy require_curve=true
kick.candidate.skip token=CRV auction=0x... reason="curve quote unavailable"
kick.prepared token=CRV auction=0x... usd_value=1234.56 gas_limit=252000
kick.broadcast tx_hash=0x... receipt_status=CONFIRMED
kick.run.complete status=ok sent=1 skipped=0
```

## systemd Service

After `--headless` exists, no wrapper script or special systemd success codes are needed.

Create `/etc/systemd/system/tidal-kick.service`:

```ini
[Unit]
Description=Tidal kick automation cycle
Wants=network-online.target
After=network-online.target tidal-api.service

[Service]
Type=oneshot
User=tidal
Group=tidal
WorkingDirectory=/srv/tidal
EnvironmentFile=/etc/tidal/kick.env
ExecStart=uv run tidal kick run --headless --source-type strategy --require-curve
ExecStart=uv run tidal kick run --headless --source-type fee-burner --no-require-curve
TimeoutStartSec=12min
```

If the API is not local, remove `tidal-api.service` from `After=`.

Create `/etc/systemd/system/tidal-kick.timer`:

```ini
[Unit]
Description=Run Tidal kick automation every 15 minutes

[Timer]
OnBootSec=2min
OnCalendar=*-*-* *:00/15:00
AccuracySec=30s
Persistent=true
Unit=tidal-kick.service

[Install]
WantedBy=timers.target
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tidal-kick.timer
```

## Environment

Use `/etc/tidal/kick.env`:

```dotenv
TIDAL_HOME=/var/lib/tidal
TIDAL_API_BASE_URL=http://127.0.0.1:8787
TIDAL_API_KEY=<operator-api-key>
RPC_URL=<mainnet-rpc-url>
TXN_KEYSTORE_PATH=/var/lib/tidal/operator-keystore.json
TXN_KEYSTORE_PASSPHRASE=<keystore-passphrase>
```

## Rollout Checks

```bash
sudo systemctl start tidal-kick.service
journalctl -u tidal-kick.service -n 100 --no-pager
uv run tidal logs kicks --limit 20
```

Keep scanner automation running separately. Kick selection depends on fresh cached balances and
prices.
