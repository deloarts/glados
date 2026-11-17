/**
 * The address of a PDF for an embedded viewer, opened to fit the page.
 * Without an explicit initial view the browser's PDF viewer restores
 * whatever zoom it last used, such as the tiny one a thumbnail-sized preview
 * left behind, and the document opens shrunk. The two spellings cover both
 * engines: Chrome reads view, Firefox's pdf.js reads zoom.
 */
export function pdfFitUrl(url: string): string {
  return `${url}#view=Fit&zoom=page-fit`
}
