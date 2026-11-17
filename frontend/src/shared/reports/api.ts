import type { Schemas } from '@/core/api/generated'
import { webApi } from '@/core/api/webRequest'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import type { AppLocale } from '@/core/i18n'

/**
 * The calls of the report export dialog: the document printers to offer,
 * sending a rendered report to one of them, and the export journal, which
 * records every download and print of a saved record's report and lists
 * them as its distribution.
 */

export type UploadedPrintDocument = Schemas['UploadedPrintDocument']
export type UploadedPrintJobResponse = Schemas['UploadedPrintJobResponse']
export type ReportJournalEntry = Schemas['ReportJournalEntryResponse']

/** How a report was built, as the export journal records it. */
export interface ReportExportFacts {
  language: AppLocale
  options: Readonly<Record<string, boolean>>
  /** The app version that built the report. */
  reportVersion: string
  engineVersion: number | null
}

export type DocumentPrinter = Pick<
  Schemas['PrinterResponse'],
  'id' | 'name' | 'location' | 'transport' | 'is_default'
>

/** The record a report belongs to; only a saved record can be printed. */
export interface ReportPrintTarget {
  document: UploadedPrintDocument
  rootPublicId: string
}

export interface ReportPrintOptions {
  printerId: number
  copies: number
  twoSided: boolean
}

/** Enabled document printers, the default one first, then by name. */
export async function getDocumentPrinters(): Promise<DocumentPrinter[]> {
  const page = await webApi.get('/printers', {
    query: { kind: 'ipp_document', enabled: true, limit: API_MAX_PAGE_SIZE, order_by: 'name' },
  })
  return [...page.items].sort((a, b) => Number(b.is_default) - Number(a.is_default))
}

/** The SHA-256 of the PDF as hex, the fingerprint the journal keeps. */
export async function sha256Hex(pdf: Blob): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await pdf.arrayBuffer())
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('')
}

export async function recordReportDownload(
  target: ReportPrintTarget,
  facts: ReportExportFacts,
  pdf: Blob,
): Promise<ReportJournalEntry> {
  return webApi.post('/report-journal/downloads', {
    body: {
      document: target.document,
      root_public_id: target.rootPublicId,
      facts: {
        language: facts.language,
        options: { ...facts.options },
        report_version: facts.reportVersion,
        engine_version: facts.engineVersion,
      },
      byte_size: pdf.size,
      sha256: await sha256Hex(pdf),
    },
  })
}

/** Every download and print of a report of any revision of the record, newest first. */
export async function getReportJournal(target: ReportPrintTarget): Promise<ReportJournalEntry[]> {
  return webApi.get('/report-journal', {
    query: { document: target.document, root_public_id: target.rootPublicId },
  })
}

export async function printReport(
  target: ReportPrintTarget,
  pdf: Blob,
  options: ReportPrintOptions,
  facts?: ReportExportFacts,
): Promise<UploadedPrintJobResponse> {
  const form = new FormData()
  form.append('file', pdf, 'report.pdf')
  form.append('document', target.document)
  form.append('root_public_id', target.rootPublicId)
  form.append('printer_id', String(options.printerId))
  form.append('copies', String(options.copies))
  form.append('two_sided', String(options.twoSided))
  if (facts) {
    form.append('language', facts.language)
    form.append('options', JSON.stringify(facts.options))
    form.append('report_version', facts.reportVersion)
    if (facts.engineVersion !== null) form.append('engine_version', String(facts.engineVersion))
  }
  return webApi.post('/print/document', {
    body: form,
    config: { headers: { 'Content-Type': 'multipart/form-data' } },
  })
}
