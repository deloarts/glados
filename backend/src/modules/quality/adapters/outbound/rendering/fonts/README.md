# Vendored fonts

`LiberationSans-Regular.ttf` / `LiberationSans-Bold.ttf`, used by the ZPL rasterizer
(`src/modules/quality/adapters/outbound/rendering/zpl_rasterizer.py`) and the docket renderer for label/document
previews and PDF rendering.

These fonts are vendored rather than installed via an apt package because the
backend image (`docker/backend.Dockerfile`, `python:3.13-slim`) ships without
any fonts, and a docket/label layout tuned to specific millimetre positions must
not shift between development and production. Bundling identical files for every
environment guarantees consistent rendering, independent of the fonts fontconfig
would otherwise resolve on a given host.

Licensed under the SIL Open Font License, version 1.1, see
<https://openfontlicense.org/documents/OFL.txt> for the full text. Source:
the Liberation Fonts project (<https://github.com/liberationfonts/liberation-fonts>).
Redistribution under the OFL is explicitly permitted, including bundling with
software, provided the font name is not used to imply endorsement, which this
project does not do.
