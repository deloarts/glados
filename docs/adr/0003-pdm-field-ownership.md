# 0003 PDM owns CAD data, enforced per field

- Status: accepted
- Date: 2026-10-05

## context

Engineers maintain part data in the SolidWorks PDM vault, while office users maintain purchasing, planning and stock data in Glados. If both sides can edit the same field, changes get overwritten in one direction or the other without anyone noticing, and nobody can tell which value is right.

## decision

The PDM vault is the single source of truth for CAD-authored data. Each field of made and bought items has a fixed owner: PDM-mapped fields on PDM-owned rows are written only by ingest, which overwrites them unconditionally, and are read-only in the web while the integration is enabled; Glados-authored fields stay editable. Which rows PDM owns follows from the part-number scheme, because numbers matching the external pattern are reserved for ingest. Part numbers are unique across the application and never reused, even by archived rows, and `data_source` only ever moves from web to CAD.

## consequences

Users see one authoritative value per field, and ingest never has to merge. The cost is a set of enforcement points that must stay in sync with the mapping: the domain services `item_field_ownership.py` and `pdm_ownership.py`, the ingest use case, and the read-only state in the frontend. Every new item field must be classified before it ships. The full rule set is [FIELD_OWNERSHIP.md](../FIELD_OWNERSHIP.md); the mechanism is [PDM_INTEGRATION.md](../PDM_INTEGRATION.md).
