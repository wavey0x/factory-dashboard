# Tidal Kick Automation Plan

## Goal

Run unattended kick attempts from a server every 15 minutes.

Policy for the automated run:

- Strategy sources must have a usable Curve quote before Tidal prepares/sends.
- Fee-burner sources may proceed when Curve has no route.
- Candidates below `$250` sell-side USD value are skipped so the bot does not kick dust.

The canonical operator command is `tidal kick run`. Even on the server host, use `tidal`
against the local control-plane API instead of adding a new `tidal-server` kick path.

## Server Config

Set the shared threshold and default Curve strictness in the server checkout's
`config/server.yaml`:

```yaml
txn_usd_threshold: 250
txn_require_curve_quote: true
```

`txn_usd_threshold` is the existing minimum sell-value gate. It is applied during shortlist
selection from cached prices and checked again during just-in-time preparation with the live
source balance. Do not use `kick.usd_kick_limit` for this; that setting is a per-token sell cap,
not a minimum.

Environment variables override YAML. Remove any `TXN_USD_THRESHOLD` override from the API and
scanner service environments, or set it to `250` there too.

Keep scanner automation running separately, at the same or faster cadence than the kick timer.
Kick selection depends on fresh cached balances and prices, and stale data is rejected by
`txn_data_freshness_limit_seconds`.

## Command Strategy

Use one timer cycle with two serialized `tidal kick run` invocations:

```bash
tidal kick run --source-type strategy --require-curve --no-confirmation
tidal kick run --source-type fee-burner --no-require-curve --no-confirmation
```

This is intentional. `--require-curve` and `--no-require-curve` are per-run overrides, so source
specific quote policy requires separate runs.

With `--no-confirmation`, `tidal kick run` submits at most one prepared candidate before ending
that invocation. One full automation cycle can therefore send up to one strategy kick and one
fee-burner kick.

## Environment

Keep secrets out of unit files. Put them in an environment file readable only by the service
user, for example `/etc/tidal/kick.env`:

```dotenv
TIDAL_REPO=/srv/tidal
TIDAL_HOME=/var/lib/tidal
TIDAL_API_BASE_URL=http://127.0.0.1:8787
TIDAL_API_KEY=<operator-api-key>
RPC_URL=<mainnet-rpc-url>
TXN_KEYSTORE_PATH=/var/lib/tidal/operator-keystore.json
TXN_KEYSTORE_PASSPHRASE=<keystore-passphrase>
```

Suggested permissions:

```bash
sudo install -o tidal -g tidal -m 0750 -d /var/lib/tidal
sudo install -o root -g tidal -m 0750 -d /etc/tidal
sudo chmod 0640 /etc/tidal/kick.env
```

If the server checkout uses a different path than `/srv/tidal`, set `TIDAL_REPO` accordingly.
If `tidal` is installed as a standalone tool instead of run from the checkout, set
`TIDAL_BIN=/home/tidal/.local/bin/tidal` in the environment file.

## Wrapper Script

Install this as `/usr/local/bin/tidal-kick-cycle`:

```bash
#!/usr/bin/env bash
set -euo pipefail

TIDAL_REPO="${TIDAL_REPO:-/srv/tidal}"
TIDAL_BIN="${TIDAL_BIN:-uv run tidal}"
TIDAL_KICK_LOCK="${TIDAL_KICK_LOCK:-/var/lib/tidal/kick.lock}"

cd "$TIDAL_REPO"
read -r -a tidal_cmd <<< "$TIDAL_BIN"

run_kick() {
  set +e
  "${tidal_cmd[@]}" kick run --no-confirmation "$@"
  local status=$?
  set -e

  case "$status" in
    0) return 0 ;;
    2) return 0 ;; # no ready candidate is normal for a timer
    *) return "$status" ;;
  esac
}

(
  flock -w 30 9
  run_kick --source-type strategy --require-curve
  run_kick --source-type fee-burner --no-require-curve
) 9>"$TIDAL_KICK_LOCK"
```

Then:

```bash
sudo install -o root -g root -m 0755 tidal-kick-cycle /usr/local/bin/tidal-kick-cycle
```

The lock prevents overlapping timer runs and also prevents the strategy and fee-burner passes
from racing each other for the same wallet nonce.

## systemd Units

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
ExecStart=/usr/local/bin/tidal-kick-cycle
TimeoutStartSec=12min
```

If the API service has a different unit name, replace `tidal-api.service`. If the API is hosted
elsewhere, remove that dependency and keep only `network-online.target`.

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

Enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tidal-kick.timer
systemctl list-timers tidal-kick.timer
```

## Rollout Checks

Before enabling the timer, start the oneshot service directly so systemd loads the same user,
working directory, and environment file that the timer will use:

```bash
sudo systemctl start tidal-kick.service
journalctl -u tidal-kick.service -n 100 --no-pager
```

For a non-sending preview, run the two commands manually without `--no-confirmation` and decline
the prompt:

```bash
cd /srv/tidal
uv run tidal kick run --source-type strategy --require-curve
uv run tidal kick run --source-type fee-burner --no-require-curve
```

After enabling the timer:

```bash
journalctl -u tidal-kick.service -n 100 --no-pager
uv run tidal logs kicks --limit 20
```

No ready candidates are normal and should not alert by themselves. Real failures to alert on are
missing API credentials, missing RPC, keystore failures, API downtime, and transaction submission
errors.

## Follow-Up

This plan uses the existing `$250` sell-side USD threshold. If the desired rule is instead
"Curve route output must be worth at least `$250`", that is a separate code change because current
selection uses cached sell-token USD value for thresholding and live Curve quotes only for
transaction pricing.
