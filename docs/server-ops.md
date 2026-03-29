# Server Operations

## What The Server Owns

`tidal-server` is the server/admin CLI. It owns:

- Alembic migrations
- scanner execution
- optional kick daemon execution
- FastAPI serving
- API key management
- the canonical SQLite database

The server should run close to both the database and the Ethereum RPC it depends on.

## Recommended Deployment Shape

Minimal production deployment:

```text
1 host / VM
  - SQLite database file
  - tidal-server scan daemon
  - tidal-server api serve
  - optional tidal-server kick daemon
```

Separate the operator wallet from this machine whenever possible.

## First-Time Bootstrap

Install the project and create a config/environment:

```bash
pip install -e ".[dev]"
tidal-server db migrate
tidal-server auth create --label operator-name
tidal-server scan run
tidal-server api serve
```

If you plan to reconcile receipts in the API process, set `RPC_URL` so the background reconciler can start.

## Example Linux Deployment

One simple production shape is:

- host: `electro`
- user: `wavey`
- working directory: `/home/wavey/tidal`
- API bind: `127.0.0.1:8020`
- reverse proxy: nginx terminating TLS at `api.tidal.wavey.info`

Example `.env`:

```bash
DB_PATH=data/tidal.db
RPC_URL=http://127.0.0.1:8545
TIDAL_API_PORT=8020
TIDAL_API_HOST=127.0.0.1
```

## Long-Running Commands

Scanner daemon:

```bash
tidal-server scan daemon --interval-seconds 300
```

Kick daemon:

```bash
tidal-server kick daemon --broadcast --sender 0xYourAddress --account wavey3
```

API:

```bash
tidal-server api serve
```

The API host and port come from:

- `TIDAL_API_HOST`
- `TIDAL_API_PORT`

## systemd Example

API service:

```ini
[Unit]
Description=Tidal API Server (FastAPI/uvicorn)
After=network.target

[Service]
Type=simple
User=wavey
Group=wavey
WorkingDirectory=/home/wavey/tidal
EnvironmentFile=/home/wavey/tidal/.env
ExecStart=/home/wavey/tidal/venv/bin/tidal-server api serve
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Scanner oneshot service:

```ini
[Unit]
Description=Tidal Scan (oneshot)
After=network.target

[Service]
Type=oneshot
User=wavey
Group=wavey
WorkingDirectory=/home/wavey/tidal
EnvironmentFile=/home/wavey/tidal/.env
ExecStart=/home/wavey/tidal/venv/bin/tidal-server scan run
```

Pair the scan oneshot with a systemd timer or external scheduler.

## Reverse Proxy Example

Minimal nginx shape:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name api.tidal.wavey.info;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name api.tidal.wavey.info;

    location / {
        proxy_pass http://127.0.0.1:8020;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## DNS And TLS

For the API hostname, point an `A` record at your server before requesting certificates:

```text
api.tidal.wavey.info A <server-ip>
```

Then issue the certificate with your normal ACME flow, for example `certbot --nginx`.

## API Key Management

Create:

```bash
tidal-server auth create --label alice
```

List:

```bash
tidal-server auth list
```

Revoke:

```bash
tidal-server auth revoke alice
```

The API stores only SHA-256 hashes of keys. The plaintext key is shown once at creation time.

## Database Notes

SQLite is the canonical datastore for this repo.

Runtime behavior:

- journal mode: WAL
- busy timeout: 30 seconds
- synchronous mode: NORMAL

That configuration is set in `tidal/persistence/db.py`.

Operational implications:

- keep the database on local disk
- avoid multiple independent writers outside the app
- expect occasional lock retries under write pressure
- back up the `.db`, `.db-wal`, and `.db-shm` files consistently

Also ignore runtime data directories in git. A server-local `data/` directory should never be committed.

## Auth Model

Public endpoints:

- dashboard
- logs
- kick inspect
- deploy defaults
- AuctionScan lookups
- health

Authenticated endpoints:

- kick prepare
- auction prepare routes
- action audit routes

Authentication is bearer-token based. Operator identity is currently the API key label.

## Monitoring And Troubleshooting

Useful commands:

```bash
tidal-server logs scans
tidal-server logs kicks
tidal-server logs show <run_id>
```

Useful symptoms:

- no candidates: check scanner freshness, token prices, and auction mappings
- repeated `database is locked`: investigate overlapping long-lived writes
- API 503 `No API keys configured`: create at least one key with `tidal-server auth create`
- missing receipt reconciliation: verify `RPC_URL` is present in the API process environment

Useful logs:

```bash
journalctl -u tidal-api -f
journalctl -u tidal-scan -f
```

## Deployment Boundaries

Do not point multiple operator CLIs directly at the SQLite database. The intended model is:

- server owns DB and preparation logic
- operator CLI talks over HTTP
- operator CLI signs locally

That keeps schema changes and audit behavior centralized.
