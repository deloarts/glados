# PDM Web API catalogue tooling

`src/modules/external_data/adapters/outbound/external/pdm/catalogue.py` lists every operation of the
SOLIDWORKS PDM Professional Web API (113 operations for the 2025 release). The
admin API-test console offers every entry of it. It is generated code; this
directory holds everything needed to rebuild it.

| File | Role |
| --- | --- |
| `operations.json` | The source of truth, finalised by hand. Commit every change. |
| `generate.py` | Renders `operations.json` into `catalogue.py`. `--check` only verifies. |
| `scrape.py` | Downloads the help pages as `.txt` files into a scratch directory. |
| `parse_pages.py` | Parses those pages into a draft operations JSON file. |

`operations.json` is never overwritten by a script. The scraped pages are not
committed either; they live in a scratch directory only while you work.

## Regenerating `catalogue.py` after editing `operations.json`

From `backend/`:

```bash
poetry run python scripts/pdm_catalogue/generate.py          # rewrite catalogue.py
poetry run python scripts/pdm_catalogue/generate.py --check  # exit 1 if catalogue.py is stale
```

The generator runs `ruff format` on its output and appends `# noqa: E501` to
lines that remain too long (verbatim documentation text and JSON samples). The
output therefore depends on the installed ruff version (`pyproject.toml` dev
dependencies). The module docstring of `catalogue.py` is part of `generate.py`
(`HEADER`); edit it there, not in the generated file. The pre-commit hook
`pdm-catalogue` runs the `--check` whenever `catalogue.py`, `operations.json`
or `generate.py` change.

## Updating to a new Web API version

1. Scrape the help pages into a scratch directory. Point `--base-url` at the
   new release's help site:

   ```bash
   python scripts/pdm_catalogue/scrape.py --out /tmp/pdmdocs \
       --base-url https://help.solidworks.com/2026/english/api/pdmprowebapihelp/
   ```

   Without `--pages`, the page list is taken from the links on the help index
   page. That discovery has not been run against the live site; if it finds no
   operation pages, write the page names (for example
   `PDM Pro API_ws~r-api-{vaultName}-authenticate_o-HttpPost.html`) into a
   file, one per line, and pass it with `--pages`. Re-running skips pages that
   are already downloaded.

2. Parse the pages into a draft:

   ```bash
   python scripts/pdm_catalogue/parse_pages.py /tmp/pdmdocs /tmp/operations.draft.json
   ```

   Lines starting with `SKIP` name pages without an operation signature.

3. Diff the draft against the committed `operations.json` by hand and carry
   over the real changes: new or removed operations, changed parameters,
   descriptions. Check the `mutating` flag of every new operation, since the
   admin console uses it to guard writes against the vault. The parser is a
   heuristic over irregular pages, so review rather than copy.

4. Run `generate.py`, review the diff of `catalogue.py`, update the operation
   counts in `HEADER` if they changed, and commit `operations.json` and
   `catalogue.py` together.
