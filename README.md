# Akamai SIEM -> Coralogix (Docker Compose)

A small, self-contained deployment that pulls Akamai SIEM events and forwards
them to Coralogix for the **Akamai WAF** extension.

One long-running service:

```
Akamai SIEM API
      |
      v
akamai-siem pull --emit-datastream   (writes daily NDJSON, saves offset)
      |
      v
akamai-siem send                     (Coralogix /logs/v1/singles)
      |
      v
Coralogix app <application> / subsystem <subsystem>
```

Native `send` posts each event in the Coralogix `text` field, which is the shape
the Akamai WAF extension parses. No OpenTelemetry collector is required.

## Requirements

- Docker with Compose v2 (or Podman + the native `podman-compose` provider).
- An Akamai SIEM configuration ID.
- An Akamai `.edgerc` file with SIEM read access.
- A Coralogix key JSON file containing `apiKey.keyValue`, with send-data
  permission to the team that owns the target application/subsystem.
- Host OS with `linux/amd64` container support (the binary is `linux/amd64`).

## Files

| File | Purpose |
|---|---|
| `akamai-siem-linux-amd64` | Prebuilt CLI binary (linux/amd64) |
| `SHA256SUMS` | Binary checksum |
| `Dockerfile` | Runtime image (binary only, non-root, no secrets) |
| `compose.yaml` | Deployment (pull + send loop) |
| `.env.example` | Non-secret settings + credential file paths |

## 1. Verify the binary

```sh
sha256sum -c SHA256SUMS
# akamai-siem-linux-amd64: OK
```

## 2. Prepare credentials

Keep these two files on the host, mode `0600`, and never commit them:

```sh
chmod 600 /path/to/.edgerc
chmod 600 /path/to/coralogix-key.json
```

`.edgerc` example (use your real values):

```ini
[siem]
host = akab-your-hostname.luna.akamaiapis.net
client_token = akab-your-client-token
client_secret = your-client-secret
access_token = akab-your-access-token
```

## 3. Configure `.env`

```sh
cp .env.example .env
# edit: AKAMAI_CONFIG_ID, AKAMAI_EDGERC_FILE, CORALOGIX_DOMAIN,
#       CORALOGIX_APPLICATION, CORALOGIX_SUBSYSTEM, CORALOGIX_KEY_FILE
```

`.env` holds non-secret settings plus the **paths** to the two credential files.
Never put the contents of `.edgerc` or a Coralogix key into it.

## 4. Create runtime directories

The container runs as UID `100` / GID `101` (`akamai`). Give the host bind-mount
directories to that user:

```sh
mkdir -p runtime/state runtime/send-state runtime/out
chown -R 100:101 runtime
chmod 700 runtime/state runtime/send-state
chmod 750 runtime/out
```

| Host dir | Container path | Contents |
|---|---|---|
| `runtime/state` | `/var/lib/akamai/state` | Akamai pagination offset |
| `runtime/send-state` | `/var/lib/akamai/send-state` | Coralogix byte offsets + `last-ok` |
| `runtime/out` | `/var/lib/akamai/out` | daily `events-YYYYMMDD.ndjson` |

## 5. Start

```sh
docker compose --env-file .env up -d --build
```

The loop:

1. `pull` fetches new events (first run defaults to `now-1h`; later runs reuse
   the saved offset).
2. `send` posts any new NDJSON bytes to Coralogix `/logs/v1/singles` and saves
   byte offsets.
3. Writes `last-ok`, sleeps `POLL_INTERVAL`, repeats.
4. On a pull/send failure it retries after `RETRY_DELAY` instead of exiting.

## 6. Logs and health

```sh
docker compose --env-file .env ps          # expect: healthy
docker compose --env-file .env logs -f akamai-siem
```

Healthy cycle log output:

```text
done: pages=… … written=… out=/var/lib/akamai/out/events-YYYYMMDD.ndjson
sent: format=datastream events=… file=…
send complete: events=… files=…
cycle ok; sleeping 600s
```

## 7. Verify delivery with local `cx` (optional, host-side)

Compose itself does not use the `cx` CLI. To confirm records are visible, query
with a `cx` profile authenticated to the same tenant/region:

```sh
cx logs "source logs | filter \$l.applicationname == 'akamai' | filter \$l.subsystemname == '75581' | limit 10" \
  --start now-30m --end now --tier frequent -o json --read-only
```

Distinguish clearly:

- **Delivery** — the send requests succeed (see logs).
- **Visibility** — records appear in the query above.
- **Parsing** — `$d.cx_security.*` fields materialize (requires the deployed
  Akamai WAF extension and Frequent-tier events).
- **Alerts** — the extension's alerts fire on parsed events.

## 8. Restart, stop, upgrade

State is on the host, so restarts resume without re-sending acknowledged data.

```sh
docker compose --env-file .env restart      # or: down then up
docker compose --env-file .env down         # stop; state preserved
```

Upgrade:

```sh
docker compose --env-file .env down
# replace akamai-siem-linux-amd64 and re-run sha256sum -c SHA256SUMS
docker compose --env-file .env up -d --build
```

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| Service restarts every `RETRY_DELAY` | Pull or send failing | `docker compose logs akamai-siem`; check the printed stage |
| `401` / `403` on send | Coralogix key lacks access or wrong team | Rotate/scope the key; check domain |
| `permission denied` on out/state | Bind mounts not owned by `100:101` | Re-run the §4 `chown` |
| `416 offset expired` | Saved cursor too old | CLI resets to `from=now-12h` automatically |
| `no such image … image not known` | `docker-compose` shim on Podman | Use native `podman-compose` instead |

## Security notes

- The image contains only the binary; it runs as a non-root user.
- Credentials are mounted read-only as Docker secrets, never baked in.
- `.env`, `.edgerc`, and the Coralogix key must never be committed.
- No customer event data, tenant IDs, or API keys are included in this repo.

## Supported architecture

`linux/amd64`. The prebuilt binary and the image are built for that platform,
which the Compose file enforces via `platform: linux/amd64`.