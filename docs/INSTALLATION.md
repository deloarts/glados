# installation

This guide deploys Glados to a server, puts TLS in front of it and upgrades it. Day-2 operations (volumes, storage, backup, restore, recovery) are in [OPERATIONS.md](OPERATIONS.md), and the internals behind these steps are in [reference/installation-deployment.md](reference/installation-deployment.md).

- [installation](#installation)
  - [1 support policy](#1-support-policy)
  - [2 requirements](#2-requirements)
  - [3 install (cli)](#3-install-cli)
  - [4 install (portainer)](#4-install-portainer)
  - [5 configuration](#5-configuration)
  - [6 ssl termination](#6-ssl-termination)
    - [6.1 how the two nginx layers fit together](#61-how-the-two-nginx-layers-fit-together)
    - [6.2 bind the container port to localhost](#62-bind-the-container-port-to-localhost)
    - [6.3 obtain a certificate](#63-obtain-a-certificate)
    - [6.4 reverse proxy config](#64-reverse-proxy-config)
    - [6.5 renewal](#65-renewal)
    - [6.6 what breaks without https](#66-what-breaks-without-https)
    - [6.7 client addresses behind proxies](#67-client-addresses-behind-proxies)
    - [6.8 alternative: cloudflare tunnel](#68-alternative-cloudflare-tunnel)
  - [7 externalising postgres, redis and storage](#7-externalising-postgres-redis-and-storage)
  - [8 upgrade](#8-upgrade)
    - [8.1 patch updates](#81-patch-updates)
    - [8.2 minor and major upgrades](#82-minor-and-major-upgrades)
  - [9 uninstall](#9-uninstall)
  - [10 bare metal (unsupported)](#10-bare-metal-unsupported)

## 1 support policy

GLADOS is supported as a Docker Compose deployment only: a Linux host running Docker Engine and the Compose plugin, either from the CLI or under [Portainer](https://www.portainer.io/) ([section 4](#4-install-portainer)). Running it on bare metal without containers is **not** supported ([section 10](#10-bare-metal-unsupported)). The local development loop is in [DEVELOPMENT.md](DEVELOPMENT.md), and how releases are cut and versioned is in [RELEASING.md](RELEASING.md).

## 2 requirements

- The host runs Linux, any distribution Docker Engine supports.
- The host has **Docker Engine ≥ 24** and the **Compose plugin ≥ v2.20** (check with `docker compose version`).
- A **domain name** points at the server and has a **TLS certificate** ([section 6](#6-ssl-termination)); behind a [Cloudflare Tunnel](#68-alternative-cloudflare-tunnel) neither is needed.
- **No GitHub credentials** are needed, because the repository and the GHCR images are public and nothing at runtime talks to GitHub.

## 3 install (cli)

Clone the repository into the deployment directory; only `docker-compose.yml` and `.env.example` from it are actually needed:

```bash
mkdir -p /opt/glados
git clone https://github.com/deloarts/glados.git /opt/glados
cd /opt/glados
```

> [!NOTE]
> To fetch just those two files instead of cloning:
> `curl -O https://raw.githubusercontent.com/deloarts/glados/main/docker-compose.yml`
> (and the same for `.env.example`).

Copy and fill in the environment file ([section 5](#5-configuration) explains every variable):

```bash
cp .env.example .env
nano .env
```

Start the stack:

```bash
docker compose up -d
# Storing files in the bundled SeaweedFS? Enable its profile instead:
docker compose --profile seaweedfs up -d
```

Compose waits for the Postgres and Redis healthchecks, and the backend's entrypoint runs `alembic upgrade head` before gunicorn starts, so there is no separate migration step. When migrations are pending on an existing database, it dumps the database first ([OPERATIONS.md, section 3.1](OPERATIONS.md#31-pre-migration-dump)). Verify:

```bash
docker compose ps
curl localhost:8080/health
```

## 4 install (portainer)

**Stack.** *Stacks* → *Add stack*, then either:

- With **Repository**, set the Repository URL `https://github.com/deloarts/glados.git`, the reference `refs/tags/vX.Y.Z` and the compose path `docker-compose.yml`. Pin a release tag and do not track a branch in production. No git authentication is needed.
- With **Web editor**, paste the contents of `docker-compose.yml`.

**Environment variables.** `python3 scripts/create_stack_env.py` asks how the stack is reached and which optional services it runs, generates every password and key in the format it needs, and writes `stack.env` with `ENV_FILE` and `COMPOSE_PROFILES` already set. Upload that file with *Load variables from .env file*. It needs only Python 3.10 or newer, no checkout dependencies, so it runs on any machine that has the script. Without the script, upload a filled-in copy of `.env.example` and add two stack variables by hand:

- `ENV_FILE=stack.env` makes `docker-compose.yml` (which reads `env_file: ${ENV_FILE:-.env}`) find the `stack.env` file Portainer writes from the stack's variables.
- `COMPOSE_PROFILES=seaweedfs` is needed only when storing files in the bundled SeaweedFS.

Then **Deploy the stack**. Registry setup and the stack editor's wording vary across Portainer versions, so verify them against the version in use.

## 5 configuration

| Group | Variable | Purpose |
| --- | --- | --- |
| App | `DEBUG` | `false` in production; `true` enables verbose errors and debug behaviour |
| App | `DOMAIN` | Public URL, e.g. `https://glados.example.com`, used for absolute links such as in mails. Passkeys are bound to its host name and need `https` (or `http://localhost`); changing the host name later invalidates every registered passkey |
| App | `LOG_LEVEL` | Minimum level written to stdout: `DEBUG`, `INFO`, `WARNING` or `ERROR` (default `DEBUG`) |
| App | `LOG_DB_LEVEL` | Minimum level stored in the database and shown in the in-app Logs tab (default `INFO`). Request audit rows are kept regardless of either level |
| App | `LOG_FORMAT` | Stdout line format: `text` (default) or `json` for a log aggregator such as Loki or Elastic |
| App | `GUNICORN_WORKERS` | Number of backend worker processes (default `4`); see [OPERATIONS.md, section 7.5](OPERATIONS.md#75-worker-processes-and-restarts) |
| Database | `DATABASE__URL` | SQLAlchemy connection string of the backend; with the bundled Postgres its user, password and database match `POSTGRES_*`. The backend refuses to start when the password is the sample value `change_me` |
| Database | `DATABASE__POOL_SIZE`, `DATABASE__MAX_OVERFLOW`, `DATABASE__POOL_TIMEOUT_SECONDS`, `DATABASE__*_TIMEOUT_SECONDS`, `DATABASE__SLOW_QUERY_THRESHOLD_MS` | Optional pool size and server-side limits; defaults and the connection budget are in [OPERATIONS.md, section 7.6](OPERATIONS.md#76-database-connections-and-timeouts) |
| Database | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Superuser name, its password and the database the bundled Postgres container creates on first init |
| Redis | `REDIS__URL` | Redis connection string, e.g. `redis://redis:6379/0` |
| Redis | `REDIS__SOCKET_TIMEOUT_SECONDS`, `REDIS__SOCKET_CONNECT_TIMEOUT_SECONDS`, `REDIS__MAX_CONNECTIONS`, `REDIS__RETRIES` | Optional client limits; the defaults are in `.env.example` |
| Security | `SECURITY__SECRET_KEY_PERSISTENT` | Signing key for long-lived tokens and sessions; never commit a real value. Like every key below, at least 32 characters, or the backend refuses to start; `openssl rand -hex 32` makes one |
| Security | `SECURITY__SECRET_KEY_NON_PERSISTENT` | Signing key for short-lived tokens; never commit a real value |
| Security | `SECURITY__ENCRYPTION_KEY` | Encrypts secrets stored in the database (SMTP, storage and PDM credentials, webhook secrets, TOTP secrets); must differ from both signing keys; back it up with the database |
| Security | `SECURITY__ENCRYPTION_KEY_PREVIOUS` | Set only for one restart while rotating the encryption key; see [OPERATIONS.md, section 3](OPERATIONS.md#3-backup) |
| Security | `SECURITY__BACKUP_ENCRYPTION_KEY` | Encrypts the backup archives and pre-migration dumps; must differ from every other key. Without it a production backend refuses to write a backup. Keep a copy apart from the backups; see [OPERATIONS.md, section 3](OPERATIONS.md#3-backup) |
| Upgrades | `BACKUP__PRE_MIGRATION_DUMP_DIR`, `BACKUP__PRE_MIGRATION_DUMP_KEEP` | Where the dump taken before pending migrations goes (default `./pre-migration-dumps`, a volume) and how many are kept (default `3`); see [OPERATIONS.md, section 3.1](OPERATIONS.md#31-pre-migration-dump) |
| Upgrades | `GLADOS_SKIP_PRE_MIGRATION_DUMP` | `true` migrates without that dump; only for one start after a failed dump, once a dump was taken by other means |
| PDM | `PDM__ALLOW_MUTATING_OPERATIONS` | `true` lets the admin API console run mutating SOLIDWORKS PDM Web API operations (check-in, delete, state changes and the like) after its "Allow critical endpoints" switch; the default `false` refuses every one of them |
| Storage | `LOCAL_STORAGE__BASE_DIR` | Directory files are written to when the `local` storage provider is active |
| System user seed | `INIT__FULL_NAME`, `INIT__MAIL` | Display name and mail address of the system account, created on first start |
| System user seed | `INIT__PASSWORD` | Password of the system account. Every start sets the account back to this value, so change it here, not in the app. At least 12 characters and not the sample value, or the backend refuses to start |
| SeaweedFS | `SEAWEEDFS_ACCESS_KEY` | S3 access key of the bundled SeaweedFS (`--profile seaweedfs`); enter it in Admin Settings → Storage as well |
| SeaweedFS | `SEAWEEDFS_SECRET_KEY` | S3 secret key of the bundled SeaweedFS. At least 24 characters and not the sample value: with the profile on, the `seaweedfs-check` service and the backend refuse to start otherwise, because nginx serves the storage's S3 API under `/objects/` |
| Deploy control | `GLADOS_VERSION` | Required image tag of backend and frontend, e.g. `v0.1`; compose refuses to start without it, so nothing pulls `latest`. Pin a **minor** (e.g. `v0.1`) so patch releases arrive on the next `docker compose pull`, or an exact tag (e.g. `v0.1.2`) for fully reproducible deploys |
| Deploy control | `BACKEND_VERSION`, `FRONTEND_VERSION` | Override `GLADOS_VERSION` for one image; normally unset |
| Deploy control | `GLADOS_INTERNAL_SUBNET`, `GLADOS_EXTERNAL_SUBNET` | Subnets of the stack's two Docker networks; default `192.168.240.0/24` and `192.168.241.0/24`. Change them only when they overlap a network the host must reach; see [6.7](#67-client-addresses-behind-proxies) |
| Deploy control | `GLADOS_TRUSTED_PROXIES` | Comma-separated addresses or CIDR networks whose `X-Forwarded-For` the frontend's nginx believes, or `none`; defaults to `GLADOS_EXTERNAL_SUBNET`, which covers a reverse proxy on the host and the Cloudflare Tunnel. See [6.7](#67-client-addresses-behind-proxies) |
| Deploy control | `FRONTEND_BIND` | Interface the frontend's port binds to; defaults to `127.0.0.1` so only the host's reverse proxy reaches it. Read [6.2](#62-bind-the-container-port-to-localhost) before changing it |
| Deploy control | `FRONTEND_PORT` | Host port of the frontend; defaults to `8080`, and the reverse proxy's `proxy_pass` uses the same port |
| Deploy control | `ENV_FILE` | Env file `docker-compose.yml` loads; Portainer sets it to `stack.env` |
| Deploy control | `COMPOSE_PROFILES` | Comma-separated profiles, e.g. `seaweedfs`, `cloudflare`, `maintenance`, `pgadmin`, or `seaweedfs,cloudflare`. For `maintenance` see [OPERATIONS.md, section 4.2.1](OPERATIONS.md#421-portainer-alternative-maintenance-container) |
| pgAdmin | `PGADMIN_DEFAULT_EMAIL`, `PGADMIN_DEFAULT_PASSWORD` | Login of the pgAdmin console, only with the `pgadmin` profile and passed only to that container |
| pgAdmin | `PGADMIN_PORT` | Host port of pgAdmin; defaults to `5050` |
| pgAdmin | `PGADMIN_BIND` | Interface pgAdmin binds to; defaults to `127.0.0.1` (reach it through an SSH tunnel). Read [OPERATIONS.md, section 5.7](OPERATIONS.md#57-database-console-pgadmin) before setting `0.0.0.0` |
| Cloudflare tunnel | `TUNNEL_TOKEN` | Tunnel token from the Cloudflare Zero Trust dashboard, only with the `cloudflare` profile and passed only to the `cloudflared` container |

## 6 ssl termination

The stack listens on `127.0.0.1:8080` over plain HTTP, and nothing in it serves TLS. TLS is terminated outside Docker: by a host nginx with Certbot as below, by a [Cloudflare Tunnel](#68-alternative-cloudflare-tunnel), or by something equivalent such as a cloud load balancer.

### 6.1 how the two nginx layers fit together

The nginx **inside** the `frontend` container ships with the image and is never edited on the server. It serves the Vue app, sets the app's security headers and routes to the backend and the object store. The nginx **on the host** is the only part configured here: it owns the certificate and forwards everything to the container.

```
client ──https:443──▶ host nginx ─http:8080─▶ frontend container nginx ──┬──▶ backend:3000  (/api/, /health, /ready)
                      (installed on the host,  (baked into the image,   └──▶ seaweedfs:8333 (/objects/)
                       terminates TLS)          plain HTTP only)
```

The host block only terminates TLS and passes requests through. It must not duplicate the app's security headers or routing, which pass through the proxy unchanged.

### 6.2 bind the container port to localhost

`docker-compose.yml` publishes the frontend on `127.0.0.1:8080`, so the plain-HTTP stack is reachable only from the host and every outside request goes through the reverse proxy.

> [!WARNING]
> Docker writes its own iptables rules for published ports, so a host
> firewall such as `ufw` does **not** block them. Keep `FRONTEND_BIND` on
> `127.0.0.1` unless another device in front of the host does the filtering.

`FRONTEND_PORT` moves the port off 8080, for example when something else uses it; the `proxy_pass` lines in [6.4](#64-reverse-proxy-config) then use the same port. Both are set in the env file (in Portainer, in the stack's environment). Then allow only 80 and 443 through the firewall; 80 stays open for the ACME challenge and the HTTPS redirect:

```bash
sudo ufw allow 80,443/tcp
```

### 6.3 obtain a certificate

Install nginx and Certbot on the host, then start with an HTTP-only server block so the ACME challenge can be answered:

```bash
sudo apt-get install -y nginx certbot
```

```nginx
# /etc/nginx/sites-available/glados
server {
    listen 80;
    listen [::]:80;
    server_name glados.example.com;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/glados /etc/nginx/sites-enabled/glados
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

sudo certbot certonly --webroot -w /var/www/html \
  -d glados.example.com \
  --email ops@example.com --agree-tos --no-eff-email
```

The certificate lands in `/etc/letsencrypt/live/glados.example.com/`. Use `certonly --webroot` rather than `certbot --nginx`, which rewrites the file in place and leaves out the SSE and upload settings below.

### 6.4 reverse proxy config

Append the TLS server block to the same file, keeping the port-80 block for redirects and renewals:

```nginx
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;                       # nginx < 1.25.1: use `listen 443 ssl http2;` instead
    server_name glados.example.com;

    ssl_certificate     /etc/letsencrypt/live/glados.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/glados.example.com/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # File uploads. At least 110M, the cap of the container's nginx and the
    # backend; nginx's default of 1M fails almost every attachment.
    client_max_body_size 110M;

    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }

    # Live row-sync SSE stream. Without these settings the default 60s
    # proxy_read_timeout drops the stream every minute and buffering delays
    # events, producing constant client reconnects.
    location /api/v1/web/live {
        proxy_pass         http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header   Connection        "";
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_buffering    off;
        proxy_cache        off;
        proxy_read_timeout 1h;
        gzip               off;
    }

    # Excel demand import can outlast the 60s default.
    location ~ ^/api/v1/web/(bought-items|made-items)-demands/batch/ {
        proxy_pass         http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

> [!IMPORTANT]
> `client_max_body_size` is a **requirement**, not a sizing convenience. A
> reverse proxy in front of Glados **must** cap request bodies itself, because
> the application only rejects a request whose declared `Content-Length` is
> too large and cannot stop a client that omits or misstates it.

HSTS is already sent by the container, so the host block does not repeat it. Confirm it arrives once the site is live, and keep it only if the deployment stays on HTTPS, because a long `max-age` is hard to reverse:

```bash
curl -sI https://glados.example.com | grep -i strict-transport-security
```

Background: [reference/installation-deployment.md](reference/installation-deployment.md).

### 6.5 renewal

The Debian and Ubuntu Certbot package renews through a systemd timer, but nginx must be reloaded to pick up the new certificate. Add a deploy hook once:

```bash
echo -e '#!/bin/sh\nsystemctl reload nginx' \
  | sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

Then confirm the renewal and the timer:

```bash
sudo certbot renew --dry-run
systemctl list-timers | grep certbot
```

Keep the port-80 block: renewal answers the ACME challenge over plain HTTP, and the `/.well-known/acme-challenge/` location is matched before the redirect.

### 6.6 what breaks without https

Over plain HTTP in production, browsers discard the TOTP trusted-device cookie, so every login asks for a 2FA code again, even on a device the user marked as trusted. Passkeys need `https` as well ([section 5](#5-configuration)).

Background: [reference/installation-deployment.md](reference/installation-deployment.md).

### 6.7 client addresses behind proxies

Sessions, the maintenance and terminal allowlists, the login throttle and the request rate limit all work on the client's address, so it has to survive the proxies in front of the backend. The frontend container's nginx takes it from `X-Forwarded-For` only when the connection comes from a proxy listed in `GLADOS_TRUSTED_PROXIES`, and then uses the rightmost address in that header that is not a listed proxy, so entries a client adds itself are never used. Any other connection is the client itself, whatever it sends. nginx passes on only the address it settled on, and the backend in turn believes forwarded headers only from the stack's external network, where nginx runs.

The default, the stack's external network (`GLADOS_EXTERNAL_SUBNET`), fits both documented setups without changes:

- A **reverse proxy on the host** ([6.4](#64-reverse-proxy-config)) reaches the published port through Docker, which hands the connection to nginx from the external network's gateway address. Keep its `X-Forwarded-For $proxy_add_x_forwarded_for` line.
- The **Cloudflare Tunnel** ([6.8](#68-alternative-cloudflare-tunnel)) runs `cloudflared` on the external network, and Cloudflare puts the visitor's address last in `X-Forwarded-For`.

Other setups set `GLADOS_TRUSTED_PROXIES` in the env file:

| Setup | Value |
| --- | --- |
| Clients reach the published port directly, with no proxy in front (`FRONTEND_BIND=0.0.0.0`) | `none` |
| A proxy on another machine forwards to the host's published port (`FRONTEND_BIND=0.0.0.0`) | That proxy's address, e.g. `10.20.0.5` |
| Another proxy in front of the host proxy, such as Cloudflare's proxied DNS | The default plus that proxy's ranges, e.g. `192.168.241.0/24,173.245.48.0/20,...` from Cloudflare's published list, or resolve the client in the host proxy instead (`real_ip` in nginx) |

> [!WARNING]
> Never list a network that clients themselves connect from. Every address
> listed can name any client address it likes.

The two subnets are fixed so both sides can name them. When `192.168.240.0/24` or `192.168.241.0/24` overlaps a network the host must reach, set `GLADOS_INTERNAL_SUBNET` and `GLADOS_EXTERNAL_SUBNET` to free ranges; the trust follows `GLADOS_EXTERNAL_SUBNET` unless `GLADOS_TRUSTED_PROXIES` is set. Docker creates a network's subnet once, so after changing them, or when a stack created before the subnets were fixed is updated, recreate the networks with `docker compose down` followed by `docker compose up -d` (this keeps the volumes). The frontend's start log names the trusted proxies, and the sessions list shows the addresses the backend sees:

```bash
docker compose logs frontend | grep trusting
```

Background: [reference/installation-deployment.md](reference/installation-deployment.md).

### 6.8 alternative: cloudflare tunnel

Instead of the host nginx, the `cloudflare` compose profile runs [cloudflared](https://github.com/cloudflare/cloudflared), which holds an outbound-only connection to Cloudflare's edge. TLS terminates at Cloudflare, no inbound port has to be open and no certificate is handled on the server. In exchange the domain's DNS must be managed by Cloudflare, all traffic transits Cloudflare, and the application is public unless gated, for example with Cloudflare Access. The tunnel suits a server behind NAT or one that must be reachable from outside without firewall changes; for an internal deployment with a company-issued certificate, the host nginx is the better fit.

1. Create a tunnel (connector type `cloudflared`) in the [Cloudflare Zero Trust dashboard](https://one.dash.cloudflare.com/) and copy its token.
2. Set `TUNNEL_TOKEN` in the stack's env file (`.env`, or `stack.env` in Portainer) next to the other deploy-control variables, so it survives updates. Only the `cloudflared` container receives it.
3. In the tunnel's *Public hostname* settings, route the hostname to the service `http://frontend:80`, which resolves over the compose network.
4. Start the stack with the profile: `docker compose --profile cloudflare up -d` on the [CLI](#3-install-cli), or `COMPOSE_PROFILES=cloudflare` in [Portainer](#4-install-portainer). Profiles combine, e.g. `COMPOSE_PROFILES=seaweedfs,cloudflare` or repeated `--profile` flags.

Keep the loopback binding from [6.2](#62-bind-the-container-port-to-localhost) so the published port stays unreachable from the network. No further proxy tuning is needed, and the visitor's address reaches the backend with the default `GLADOS_TRUSTED_PROXIES` ([6.7](#67-client-addresses-behind-proxies)). Cloudflare caps request bodies at 100 MB on the Free and Pro plans, so a STEP or STL file close to the 100 MB limit cannot be uploaded through the tunnel.

Background: [reference/installation-deployment.md](reference/installation-deployment.md).

## 7 externalising postgres, redis and storage

Postgres and Redis are bundled by default. To use external instances:

1. Remove the `postgres` and `redis` service blocks from your copy of `docker-compose.yml` (in Portainer, in the stack's Web editor).
2. Remove the matching `depends_on` entries of the `backend` service.
3. Point `DATABASE__URL` and `REDIS__URL` ([section 5](#5-configuration)) at the external hosts.

An override file can only add or merge configuration, not remove a service or a `depends_on` entry, so this needs the base file itself, not `docker-compose.override.yml`.

File storage is configured at runtime in the admin settings, not in compose or env files; see [OPERATIONS.md, section 2](OPERATIONS.md#2-storage-providers).

## 8 upgrade

There are two paths: a same-minor **patch** ([8.1](#81-patch-updates)) and a **minor or major** change ([8.2](#82-minor-and-major-upgrades)). Both are started by hand; nothing in the stack updates itself. How releases are versioned and cut is in [RELEASING.md](RELEASING.md).

The operator sets `GLADOS_VERSION` (and its per-image overrides) by hand on each server; no workflow writes it, and compose refuses to start without it. A test server may point it at a mutable channel tag (`staging` or `release-candidate`) instead, see [RELEASING.md, section 4](RELEASING.md#4-test-servers-staging-and-release-candidate).

> [!NOTE]
> A lasting "server/app version mismatch" banner means the frontend build and
> the backend's `/health` report different versions. Hard-refresh the browser
> to drop a stale cached bundle, and redeploy both images to the same version
> if `BACKEND_VERSION`, `FRONTEND_VERSION` and `GLADOS_VERSION` disagree.

### 8.1 patch updates

A patch release never changes the `pat` contract that the add-ins rely on ([RELEASING.md, section 1](RELEASING.md#1-versioning-policy)), but it can carry migrations, so it changes the database like any other upgrade. Before it applies them, the entrypoint dumps the database and refuses to migrate when the dump fails ([OPERATIONS.md, section 3.1](OPERATIONS.md#31-pre-migration-dump)); that dump is the way back. Check that the last scheduled backup succeeded as well, since the dump sits on the same host. With `GLADOS_VERSION` pinned to a minor (e.g. `v0.1`) the floating tag moves to the newest patch by itself:

```bash
docker compose pull
docker compose up -d
```

In Portainer, **Update the stack** with **Re-pull image and redeploy** ticked; no variable changes under the same pin. With an exact patch tag pinned instead, update it to the new patch first, as in [8.2](#82-minor-and-major-upgrades).

### 8.2 minor and major upgrades

1. Take a backup ([OPERATIONS.md, section 3](OPERATIONS.md#3-backup)).
2. Set `GLADOS_VERSION` to the target release in `.env` (or the Portainer stack's environment variables), e.g. `GLADOS_VERSION=v0.2`.
3. Pull and redeploy:

   ```bash
   docker compose pull
   docker compose up -d
   ```

   In Portainer, change the version variable (or the git reference, if deployed from a tag), then **Update the stack** with **Re-pull image and redeploy** ticked.

The entrypoint dumps the database ([OPERATIONS.md, section 3.1](OPERATIONS.md#31-pre-migration-dump)) and then applies the migrations on start.

> [!WARNING]
> **Rollback:** pulling an older image does not reverse a schema migration.
> Set `GLADOS_VERSION` back to the previous release **and** restore the
> database from the pre-upgrade backup or the pre-migration dump
> ([OPERATIONS.md, section 4.2](OPERATIONS.md#42-restoring-the-database-out-of-process)).

[CHANGELOG.md](../CHANGELOG.md) lists what changed in each version and anything an upgrade to it needs.

## 9 uninstall

Stop and remove the containers, keeping all data:

```bash
docker compose down
```

To also destroy every volume (database, Redis and any locally stored uploads):

```bash
docker compose down -v
```

> [!CAUTION]
> `down -v` deletes every named volume, including `glados_postgres` and any
> local `glados_media`, without a confirmation prompt. It is irreversible, so
> take a backup first if the data may ever be needed again.

Then remove what is left on the host, if present:

```bash
sudo rm -rf /opt/glados
# Host nginx site (section 6):
sudo rm /etc/nginx/sites-enabled/glados /etc/nginx/sites-available/glados && sudo systemctl reload nginx
# Certbot certificate:
sudo certbot delete --cert-name glados.example.com
```

## 10 bare metal (unsupported)

Running outside Docker is unsupported, and there is no guide for it. What it would take is listed in [reference/installation-deployment.md](reference/installation-deployment.md).
