---
name: Gamma SSL fix
description: How and why the Gamma API TLS verification was broken in Replit, and the permanent fix pattern.
---

# Gamma API SSL Fix

## Rule
All external HTTPS clients must use `create_verified_httpx_client()` from
`app.services.http_client` — never bare `httpx.AsyncClient()` without `verify=`.

## Why
- Replit Nix environment: `certifi` reports a path that does not exist on disk
  (`/home/runner/workspace/.pythonlibs/.../certifi/cacert.pem` → FileNotFoundError).
- httpx default `verify=True` picks up the absent certifi bundle on this platform,
  causing `[SSL: CERTIFICATE_VERIFY_FAILED]` against Polymarket's Gamma API.
- System CA bundle `/etc/ssl/certs/ca-certificates.crt` is present and works correctly.

## How to Apply
- `create_verified_httpx_client()` in `app/services/http_client.py` resolves CA in priority order:
  1. `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` env override
  2. `/etc/ssl/certs/ca-certificates.crt` (system CA — present on Nix/Linux)
  3. `certifi.where()` (if file exists on disk)
  Never uses `verify=False`.
- User-Agent `LIMWANPO-AI/1.0` and `Accept: application/json` included by default.
- `classify_httpx_error(exc)` in the same module classifies any httpx exception to
  `SSL_ERROR | CONNECT_ERROR | TIMEOUT | HTTP_4XX | HTTP_5XX | UNKNOWN`.
- Gamma sync result now includes `gamma_status` field:
  `GAMMA_OK | GAMMA_PARTIAL_SUCCESS | GAMMA_EMPTY_RESPONSE | GAMMA_UNREACHABLE | GAMMA_SSL_ERROR`.
- `/health/detailed` returns `gamma_ingestion.status = GAMMA_UNREACHABLE` if
  `market_universe` count == 0 and uptime >= 120 s, and sets overall to `degraded`.
