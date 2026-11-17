// Public surface of the PDF report module. A feature describes its report
// as a ReportSpec built from the blocks below and opens it with
// useReportExport(); ReportExportDialog downloads the PDF or sends it to a
// printer. The frame, the branding and the archival format are applied by
// composeReport() for every report alike. See docs/CONTRIBUTING.md 2.6.
export { default as ReportDistribution } from './components/ReportDistribution.vue'
export { default as ReportExportDialog } from './components/ReportExportDialog.vue'
export { useReportExport } from './composables/useReportExport'
export {
  blockCell,
  bulletList,
  cell,
  dataTable,
  drawing,
  footnote,
  formula,
  group,
  keepTogether,
  keyValueGrid,
  labelWithSymbol,
  list,
  notice,
  noteCell,
  onNewPage,
  paragraph,
  picture,
  section,
  shareBar,
  span,
  statusChip,
  subheading,
  svgFigure,
  symbol,
  twoColumns,
  withUnit,
} from './utils/blocks'
export { renderComponentSvg } from './utils/componentSvg'
export { REPORT_EMPTY, orDash } from './utils/empty'
export { composeReport, createReportContext, resolveUrl } from './utils/composeReport'
export { loadReportImage, reportImageFromBlob } from './utils/reportImage'
export { downloadPdf, renderPdf } from './utils/renderPdf'
export { getDocumentPrinters } from './api'
export { CONTENT_WIDTH, DRAWING_COLORS } from './utils/styles'
export { reportFileName } from './utils/reportLocale'

export type { CellOptions, DataColumn, FormulaPart, Inline, KeyValue, ListBlock, ListEntry } from './utils/blocks'
export type { RenderedDrawing } from './utils/componentSvg'
export type { ReportTone } from './utils/palette'
export type { ReportTranslate } from './utils/reportLocale'
export type { ReportStyle, Spacing } from './utils/styles'
export type { DocumentPrinter, ReportJournalEntry, ReportPrintTarget, UploadedPrintDocument } from './api'
export type {
  ReportBranding,
  ReportContent,
  ReportContext,
  ReportIdentity,
  ReportOption,
  ReportOptionValues,
  ReportSpec,
} from './types'
export type { Content, TableCell, TDocumentDefinitions } from 'pdfmake/interfaces'
