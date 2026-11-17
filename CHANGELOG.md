# changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.0] - 2026-11-17

The first release of Glados, a web app that plans the work of a manufacturing shop: the catalogue of made, bought and source items, the demands of every project, purchasing, production lots, the machine schedule and quality assurance, integrated with a SolidWorks PDM vault. Backend and frontend ship together under this one version.

### Added

- Catalogue, demands and procurement: made items with revisions, bought and source items, suppliers, customers and contacts, project demands covered by allocations, supplier orders and quote requests, with every lifecycle status derived from what was recorded ([ADR 0008](https://github.com/deloarts/glados/blob/v0.1.0/docs/adr/0008-derived-lifecycle-statuses.md)).
- Production and quality: production lots, production orders on machines and machine pools, a schedule with Auto-Plan, QA tasks, nonconformities and inspection reports.
- Products, projects and engineering: products and product devices with PLC tag lists, flow sequences, calculations, checklists and meetings, kept as controlled documents with revisions and an export journal.
- Shop floor: labels and dockets on ZPL and IPP printers, terminals and infoscreens ([docs/TERMINAL_INTEGRATION.md](https://github.com/deloarts/glados/blob/v0.1.0/docs/TERMINAL_INTEGRATION.md)).
- Integrations: SolidWorks PDM ([docs/PDM_INTEGRATION.md](https://github.com/deloarts/glados/blob/v0.1.0/docs/PDM_INTEGRATION.md)), the EPLAN Data Portal, a time tracking service and a stock service over contracts Glados defines, AI agents through MCP, signed webhooks, SMTP mail and LDAP sign-in.
- Users and security: local and LDAP accounts with TOTP, passkeys and RFID sign-in, permissions through groups, personal access tokens, API keys and terminal keys, a security log and secrets encrypted at rest.
- Operations: a Docker Compose stack of prebuilt images, runtime-configured file storage, encrypted scheduled backups, a dump before pending migrations, health, readiness and metrics endpoints, and admin recovery commands ([docs/INSTALLATION.md](https://github.com/deloarts/glados/blob/v0.1.0/docs/INSTALLATION.md), [docs/OPERATIONS.md](https://github.com/deloarts/glados/blob/v0.1.0/docs/OPERATIONS.md)).
- Recommended print templates, mail templates, a PLC environment, spreadsheet column names and PDM variable maps in the `templates/` folder, imported by an admin.

### Requirements

- A Linux host with Docker Engine 24 or newer and the Compose plugin v2.20 or newer, used from the CLI or Portainer, and a TLS certificate or a Cloudflare Tunnel in front of the stack.
- An env file from `.env.example` with `GLADOS_VERSION` pinned to `v0.1`; `scripts/create_stack_env.py` generates every password and key.

Images: `ghcr.io/deloarts/glados/backend` and `ghcr.io/deloarts/glados/frontend`, tagged `v0.1.0`, `v0.1` and `latest`.

### The `pat` contract 0.1

The `pat`, `key` and `public` routes that clients outside the browser use are frozen in `backend/openapi/pat-v0.1.json`. Every 0.1.x release serves exactly this contract, and any change to it comes with a new minor ([docs/RELEASING.md, section 1](https://github.com/deloarts/glados/blob/v0.1.0/docs/RELEASING.md#1-versioning-policy)).

| Client | Version | Talks to Glados through |
| --- | --- | --- |
| [glados-sw-addin](https://github.com/deloarts/glados-sw-addin), the SolidWorks add-in | 0.1.x | the `pat` contract 0.1 |
| [glados-pdm-addin](https://github.com/deloarts/glados-pdm-addin), the PDM vault add-in | 0.1.x | the `pat` contract 0.1 |
| [glados-terminal](https://github.com/deloarts/glados-terminal), the wall display bridge and kiosk | 0.1.x | the `/infoscreen` page |
