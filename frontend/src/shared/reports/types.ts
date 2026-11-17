import type { Content } from 'pdfmake/interfaces'

import type { AppLocale } from '@/core/i18n'
import type { ReportPrintTarget } from './api'
import type { KeyValue } from './utils/blocks'
import type { ReportTone } from './utils/palette'
import type { ReportTranslate } from './utils/reportLocale'

/**
 * The contract between a feature and the report module. A feature describes
 * its report as a ReportSpec; the module turns it into a PDF with the shared
 * frame, the company's branding and the archival format (see
 * utils/composeReport.ts), and the export dialog downloads or prints it.
 */

/** A choice the export dialog offers as a checkbox, such as adding an appendix. */
export interface ReportOption {
  key: string
  /** i18n key of the checkbox label, shown in the language of the app. */
  labelKey: string
}

/** The chosen options by key; an option not offered is false. */
export type ReportOptionValues = Readonly<Record<string, boolean>>

/** What a report is built with: the chosen language and its formats, and the chosen options. */
export interface ReportContext {
  locale: AppLocale
  t: ReportTranslate
  /** A date and time in the report's fixed format for its language. */
  dateTime: (value: Date | string) => string
  /** A calendar date such as "2026-10-09" in the same format, without a time. */
  date: (value: string) => string
  /** The time of day of an instant, such as "14:05", in the same timezone. */
  time: (value: Date | string) => string
  /** Whether two instants fall on the same calendar day in that timezone. */
  sameDay: (a: Date | string, b: Date | string) => boolean
  options: ReportOptionValues
}

/** The content of one report, everything inside the shared frame. */
export interface ReportContent {
  /** What kind of document this is, shown in the header, e.g. "Drive sizing". */
  kind: string
  title: string
  subtitle?: string
  /** The record's details under the title: owner, status, revision, reference. */
  details: readonly KeyValue[]
  /** A remark right under the details, such as results that changed since saving. */
  notice?: { text: string; tone: ReportTone } | null
  /**
   * The saved record and revision this report shows. Its pages then carry a
   * QR code that opens exactly that revision in the app; a draft that was
   * never saved has none.
   */
  identity?: ReportIdentity | null
  body: Content[]
}

/** The record a report shows, by its public id and a readable reference. */
export interface ReportIdentity {
  publicId: string
  /** Printed next to the QR code, such as "CAL-0042 rev. B". */
  reference: string
}

/** A report a feature offers for export. */
export interface ReportSpec {
  /** Shown in the export dialog and used for the file name, in the app's language. */
  title: string
  options?: readonly ReportOption[]
  /**
   * The saved record a printed copy is logged against, and whose export
   * journal records downloads and prints; null allows downloading only,
   * without a journal entry.
   */
  printTarget: ReportPrintTarget | null
  /** The version of the calculation engine the report recalculates with, for the journal. */
  engineVersion?: number
  build: (context: ReportContext) => ReportContent | Promise<ReportContent>
}

/** The company and the person a report is exported for and by. */
export interface ReportBranding {
  appName: string
  companyName: string | null
  companyLogoUrl: string | null
  /** The address the app is served at, which QR codes point to; null uses the current origin. */
  domain: string | null
  exportedBy: string
}
