# stock service

The stock service settings and their admin routes, and the HTTP contract between Glados and a stock service, which Glados defines and every service implements. The guide [STOCK_SERVICE.md](../STOCK_SERVICE.md) explains the integration.

- [stock service](#stock-service)
  - [1 settings](#1-settings)
  - [2 admin routes](#2-admin-routes)
  - [3 contract conventions](#3-contract-conventions)
  - [4 contract routes and errors](#4-contract-routes-and-errors)
  - [5 versions](#5-versions)

## 1 settings

- `admin_stock_settings` is a singleton row (`id = 1`), seeded switched off at startup like every settings group, and a database without the row reads as switched off.
- The service URL is an absolute `http://` or `https://` URL, optionally with a path, without user information, query or fragment (`assert_plain_http_url` in `shared_kernel/domain/services/service_url.py`, shared with the time tracking service). Plain http needs no opt-in, because the service runs in the stack.
- The API key is an `EncryptedString` column, write-only: requests take it, responses only say whether one is stored, an omitted key keeps the stored one and an empty one clears it. A value no configured key can decrypt loads as unset.
- Enabling requires the service URL and the API key (`StockServiceNotConfiguredError`).
- The service is ready (`is_ready`) when it is enabled and configured. Only then does the Host tab's service panel probe it.

## 2 admin routes

| Route | Permission | Purpose |
| ----- | ---------- | ------- |
| `GET /admin/settings/stock` | `read:settings` | The settings. |
| `PUT /admin/settings/stock` | `write:settings` | Update; omitted fields keep their value. |
| `POST /admin/settings/stock/test` | `write:settings` | Test the given or stored service: `info` and `status`, with whether the contract is supported. Stores nothing. |

- The routes exist on the web surface only, and never echo request input in a validation error.
- Every change is written to the settings audit log under the domain `stock`. A changed service URL names the old and the new URL, and a changed API key is mentioned without its value.

## 3 contract conventions

- Every route except `GET /health` takes the header `X-Api-Key`.
- Glados validates every answer against its own wire models in `adapters/outbound/external/stock_service/models.py`, which ignore fields they do not name; a missing or mistyped required field is a `StockServiceProviderError`.
- The client never follows a redirect; a redirect answer is a `StockServiceProviderError`.
- Requests time out after 20 seconds; the Host tab's probe gives up after 4.

## 4 contract routes and errors

| Route | Purpose |
| ----- | ------- |
| `GET /health` | `{status, version}`, for the Host tab's service panel. |
| `GET /api/v1/info` | `service`, `version`, `contract_version` and `provider_label` (the name Glados shows for the stock system). Contacts nothing behind the service. |
| `GET /api/v1/status` | `server_version` of the stock system. The admin connection test. |

An error answer is `{code, message}`. The client maps the codes as follows; the message is shown only for a mapped code.

| Code | HTTP | Glados error |
| ---- | ---- | ------------ |
| `api_key_invalid` | 401 | `StockServiceProviderError`, "refused Glados' API key" |
| `provider_unavailable` | 503 | `StockServiceUnavailableError` |
| `provider_error` and any other | 4xx, 5xx | `StockServiceProviderError` |

A transport failure (DNS, TCP, TLS, timeout) is a `StockServiceUnavailableError` (503); the others answer 502.

## 5 versions

- `contract_version` is the contract's own `major.minor`, independent of the service's version.
- Glados lists the minors it supports in `SUPPORTED_CONTRACT_MINORS` (`external_data/application/services/stock_service.py`), today `0.1`. The connection test warns about any other.
- A contract change that a service must follow bumps the minor here and in the service, together.
