# installation: deployment internals

This file holds the reasoning and internals behind the deployment steps: how the container's nginx routes, why the reverse proxy settings are required, what depends on HTTPS, how forwarded client addresses are trusted, the Cloudflare Tunnel limits, the version mismatch banner and the facts about running without Docker. The steps themselves are in [INSTALLATION.md](../INSTALLATION.md).

- [installation: deployment internals](#installation-deployment-internals)
  - [1 the container's nginx](#1-the-containers-nginx)
  - [2 host reverse proxy](#2-host-reverse-proxy)
  - [3 https-dependent behaviour](#3-https-dependent-behaviour)
  - [4 forwarded client addresses](#4-forwarded-client-addresses)
  - [5 cloudflare tunnel](#5-cloudflare-tunnel)
  - [6 version mismatch banner](#6-version-mismatch-banner)
  - [7 running without docker](#7-running-without-docker)

## 1 the container's nginx

- Its configuration ships with the image in `frontend/docker/nginx.conf`.
- It serves the built Vue app and sets the app's security headers, including HSTS for the app document.
- The app document gets an enforced `Content-Security-Policy`. Scripts, styles, fonts, images, frames and workers load from the deployment's own origin, and each further source has one reason, written next to the header: inline styles for the runtime theming, `data:` and `blob:` images, `blob:` workers for the QR scanner, `blob:` frames and plugin data for PDF previews, and `http://localhost:8600` for the terminal bridge. The policy allows no `eval`, so a frontend dependency that needs it fails in the browser.
- `/objects/` serves user uploads, so every response there carries `X-Content-Type-Options: nosniff` and `Content-Security-Policy: sandbox; default-src 'none'; frame-ancestors 'none'`. A browser opening an uploaded file therefore runs it in a sandbox with no script on the Glados origin, whatever type the object was stored with ([backend-conventions.md section 8](backend-conventions.md#8-stored-files-and-browser-headers)). A PDF gets only `frame-ancestors 'none'`, because browsers refuse to show a PDF in a sandboxed document.
- It proxies `/api/`, `/health` and `/ready` to the backend and `/objects/` to the bundled SeaweedFS over the internal Docker network.
- It caps request bodies at 110M and allows 120 seconds for the Excel demand import routes.
- It resolves the client address with the `real_ip` module and rate limits the API per resolved address ([section 4](#4-forwarded-client-addresses)).

## 2 host reverse proxy

- `certonly --webroot` writes the certificate and leaves the nginx configuration untouched, which keeps the documented server block the single source of truth. `certbot --nginx` also works, but it rewrites the file in place and its generated block lacks the SSE and upload settings.
- nginx `location` blocks do not inherit `proxy_set_header`, `client_max_body_size` or timeouts from a sibling block, which is why the header lines are repeated in each block. `client_max_body_size` is set at `server` level and so applies to all three.
- The application's own upload guard (`src/modules/platform/adapters/inbound/api/upload_limits.py`) rejects only a request whose declared `Content-Length` exceeds the limit, and is documented there as not a substitute for a reverse-proxy body cap. A request that omits or misstates that header could otherwise stream an unbounded body into the application, so the proxy is the one place the limit is enforced against such a client.
- The 110M cap is `MAX_UPLOAD_BYTES` in `src/modules/platform/const.py`: room for the largest 100 MB file plus the multipart envelope. A host proxy with a lower cap rejects uploads the app would have accepted.
- The live SSE stream is a long-lived, unbuffered response, so the host proxy gives it the same treatment the container's nginx already does: no buffering, no cache, no gzip and a one-hour read timeout.
- The Excel demand import parses the whole workbook in the request, which is why its routes get 120 seconds at both proxies.

## 3 https-dependent behaviour

- The TOTP trusted-device cookie is issued with `Secure` whenever `DEBUG` is false (`src/modules/platform/adapters/inbound/api/v1/auth/login_responses.py`), so browsers discard it over plain HTTP.
- Passkeys are bound to the host name in `DOMAIN` and accepted only from its origin, so they need `https` or `http://localhost`.

## 4 forwarded client addresses

- The backend reads the client address as `request.client.host` for sessions (`src/modules/platform/application/services/login_session.py`), the login throttle, the maintenance allowlist and the terminal allowlist and rate limit.
- Two hops stand between the client and the backend, and each believes forwarded headers only from peers it is told to trust:
  - The frontend's nginx lists its trusted proxies in `/etc/nginx/glados/trusted-proxies.conf`, which `frontend/docker/trusted-proxies.sh` writes from `GLADOS_TRUSTED_PROXIES` on every start (as `/docker-entrypoint.d/40-glados-trusted-proxies.sh`). Unset, empty or `none` lists nothing, so the TCP peer is the client. A malformed entry stops the container.
  - With `real_ip_header X-Forwarded-For` and `real_ip_recursive on`, nginx walks the header from the right and takes the first address that is not a trusted proxy; from an untrusted peer it ignores the header. The result replaces `$remote_addr`.
  - nginx sends the backend `X-Forwarded-For $remote_addr` and `X-Real-IP $remote_addr`, replacing whatever the client sent rather than appending to it.
  - Gunicorn passes `forwarded_allow_ips` from `NETWORK__TRUSTED_PROXIES` (`src/modules/platform/infrastructure/gunicorn_conf.py`, default loopback only) to uvicorn, which resolves `request.client` and the scheme from `X-Forwarded-For` and `X-Forwarded-Proto` only for those peers. A malformed entry stops gunicorn.
- `docker-compose.yml` pins the subnets of its `internal` and `external` networks (`GLADOS_INTERNAL_SUBNET`, `GLADOS_EXTERNAL_SUBNET`), so both hops can name them:
  - The backend's `NETWORK__TRUSTED_PROXIES` is the external subnet, the only network the frontend shares with it. The compose file sets it under `environment`, which wins over the env file, so a value there cannot widen the trust.
  - nginx's `GLADOS_TRUSTED_PROXIES` defaults to the same subnet. A host reverse proxy reaches the loopback-published port through Docker's port forwarding, which connects to the container from the network's gateway address, and `cloudflared` runs on that network, so both are covered.
  - With `FRONTEND_BIND=0.0.0.0`, Docker's port forwarding keeps a remote client's own address, so it is not trusted. Hosts whose forwarding replaces it with the gateway (rootless Docker, some desktop setups) must set `GLADOS_TRUSTED_PROXIES=none`.
- The rate limit keys on `$binary_remote_addr`, the resolved address, so a client cannot choose its bucket.
- The backend also receives both subnets as `NETWORK__INTERNAL_SUBNETS` (`NetworkSettings.internal_subnets` in `src/modules/platform/infrastructure/config/settings.py`), so outbound calls a user can aim can refuse the stack's own networks.
- `X-Forwarded-Proto` is still taken from any client, but only the value `https` (the `$client_proto` map); claiming https over plain http only yields redirects the client cannot follow.

## 5 cloudflare tunnel

- The compose file passes only `TUNNEL_TOKEN` to the `cloudflared` container, which never sees database or storage credentials, and never passes the token to the app containers.
- The container's nginx still enforces the 110M body cap, which satisfies the body cap requirement without a host proxy.
- The SSE stream sends a keepalive every 15 seconds, well inside Cloudflare's idle timeout of about 100 seconds.
- Cloudflare appends the address that connected to its edge to `X-Forwarded-For`, and `cloudflared` sits on the external network the default `GLADOS_TRUSTED_PROXIES` covers, so nginx resolves the visitor without further settings.

## 6 version mismatch banner

- The banner appears when the frontend's own build version and the backend's `/health` version disagree, compared as the full `X.Y.Z` and not only `major.minor`.
- The development placeholder `0.0.0` is excluded from the comparison.
- In practice it has two causes: a stale cached frontend bundle in the browser, or `BACKEND_VERSION` and `FRONTEND_VERSION` overrides that no longer agree with each other or with `GLADOS_VERSION`.

## 7 running without docker

Running outside Docker is unsupported. These are facts about what it would take, not a guide.

- The backend needs Python 3.13 and [Poetry](https://python-poetry.org/), and `poetry run alembic upgrade head` before the app starts.
- It is served with gunicorn, e.g. `gunicorn src.bootstrap.main:app -k src.modules.platform.infrastructure.gunicorn_worker.TimeoutUvicornWorker -c python:src.modules.platform.infrastructure.gunicorn_conf --error-logfile - --bind 0.0.0.0:3000`; the exact command is in the `backend` service of `docker-compose.yml`. Without the frontend container in front, `NETWORK__TRUSTED_PROXIES` names the proxy that sets `X-Forwarded-For`.
- It needs its own PostgreSQL, Redis and `postgresql-client` (for backups).
- The backend runs in-process background workers (Redis Streams consumers, the SSE subscriber, the outbox relay, the backup scheduler), so it must run as a single, continuously supervised service, not spawned per request or recycled by a process manager.
- The frontend needs a Node 22 build (`npm run build`) served by any static web server that proxies `/api/`, `/health`, `/ready` and `/objects/` and sends the same security headers the way `frontend/docker/nginx.conf` does.
