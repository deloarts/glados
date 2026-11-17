# Report fonts

`Play-Regular.ttf` and `Play-Bold.ttf` set the headings of the PDF reports, the same face the app
uses for its headings. `Carlito-Regular.ttf`, `Carlito-Bold.ttf` and `Carlito-Italic.ttf` set the
body text. Carlito has the same metrics as Calibri, the app's body font, which cannot be embedded.

The reports are rendered in the browser by pdfmake, which embeds a subset of these files into each
PDF. They are TrueType rather than the WOFF2 files under `src/assets/fonts`, because pdfmake reads
TrueType, and they are bundled so a report looks the same on every machine and in every browser.
Vite serves them as hashed assets that are only downloaded when a report is first exported.

Both families are licensed under the SIL Open Font License, version 1.1; the full texts with the
copyright notices are `OFL-Play.txt` and `OFL-Carlito.txt`. Source: the Google Fonts repository
(<https://github.com/google/fonts>, `ofl/play` and `ofl/carlito`). The files are unmodified, as
the reserved font names require.
