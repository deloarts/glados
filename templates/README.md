# Templates

Recommended content for a Glados install: print templates, mail templates, PLC environments, spreadsheet import column names and PDM variable maps. A fresh install starts without any of it.

Nothing in this folder is read by the application or the Docker image; only the frontend tests read it, to check that every file imports. An admin who wants a template imports the file in the matching editor, checks the values and saves. The editors export the same format, so a configuration can move from one install to another.

| Folder | Content | Import in Glados |
| ------ | ------- | ---------------- |
| `print-templates/` | One folder per print classifier. `source.zpl` (labels) or `source.json` (dockets, a block layout) is the source; `settings.json` holds the trigger, paper, design DPI, label size, copies and field map. The printer is never included, since it is install-specific. | The print template editor, **Import from file**. Pick the source, the settings or both. |
| `mail/` | One HTML file per mail kind and language (`<kind>.<language>.html`). `system/` holds the mails Glados sends on its own: full HTML documents with their own styles, whose `<title>` is the subject and whose whole file is the body. `compose/` holds the texts the send dialogs start from (request, order, order canceled, meeting notes): body fragments without styles, since a composed mail is sanitized before sending and loses any `<style>` block. Their leading `<title>` line is the subject and is removed from the body on import. The order mails take their subject from the app translations, so for them the title only labels the file. | Admin settings, Mail: **Import templates** takes many files at once; the template editor's **Import from file** takes one. |
| `plc-environments/` | `siemens_tia_portal.json`: signal prefixes, the longest tag, character conversions, tag tables and export columns for Siemens TIA Portal. | The PLC environment dialog, **Import from file**. |
| `data-import/` | `column_names.<language>.json`: the spreadsheet column names recognised per import type and field. | Admin settings, Data import, **Import from file**. Pick several files to combine languages; names a field has already are kept. |
| `pdm/` | `variable_maps.json`: the SolidWorks custom property behind each made item and bought item field. The add-in writes these properties, so change them only together with the vault's data cards (see `docs/FIELD_OWNERSHIP.md`). | Admin settings, SolidWorks PDM, **Import variable maps**. |

## File format

Every JSON file except a docket source starts with a header that names what it holds and the format version:

```json
{
  "glados_template": "plc_environment",
  "version": 1,
  "name": "Siemens TIA Portal"
}
```

The kinds are `print_template`, `plc_environment`, `data_import_column_names` and `pdm_variable_maps`. An editor refuses a file of another kind or version. Keys an editor does not know are reported after the import and otherwise ignored. The print template editor exports `<classifier>.source.<ext>` and `<classifier>.settings.json`; it reads files of any name.
