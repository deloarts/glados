import type { TDocumentDefinitions } from 'pdfmake/interfaces'

import type { AppLocale } from '@/core/i18n'
import type { ReportBranding, ReportContext, ReportIdentity, ReportOptionValues, ReportSpec } from '../types'
import { loadCompanyLogo } from './reportImage'
import { reportDocument } from './reportDocument'
import type { FrameIdentity } from './reportDocument'
import { formatReportDate, formatReportDateTime, formatReportTime, reportDayKey, reportTranslator } from './reportLocale'

/** The language, formats and options a report is built with. */
export function createReportContext(locale: AppLocale, options: ReportOptionValues = {}): ReportContext {
  return {
    locale,
    t: reportTranslator(locale),
    dateTime: (value) => formatReportDateTime(value, locale),
    date: (value) => formatReportDate(value, locale),
    time: (value) => formatReportTime(value, locale),
    sameDay: (a, b) => reportDayKey(a) === reportDayKey(b),
    options,
  }
}

/**
 * The link a QR code holds, the same scheme labels use: the app's resolve
 * page for the public id, which opens whatever record carries it.
 */
export function resolveUrl(publicId: string, domain: string | null): string {
  const base = (domain || window.location.origin).replace(/\/+$/, '')
  return `${base}/resolve/${encodeURIComponent(publicId)}`
}

function frameIdentity(identity: ReportIdentity | null | undefined, domain: string | null): FrameIdentity | null {
  if (!identity) return null
  return { url: resolveUrl(identity.publicId, domain), reference: identity.reference }
}

/**
 * Turns a feature's ReportSpec into the document pdfmake renders: builds the
 * content in the chosen language with the chosen options, loads the company
 * logo, and puts both into the shared frame. Every report goes through here,
 * so the frame, the branding and the archival format are the same for all.
 */
export async function composeReport(
  spec: ReportSpec,
  branding: ReportBranding,
  locale: AppLocale,
  options: ReportOptionValues,
): Promise<TDocumentDefinitions> {
  const context = createReportContext(locale, options)
  const { t } = context
  const [content, logo] = await Promise.all([spec.build(context), loadCompanyLogo(branding.companyLogoUrl)])
  return reportDocument(
    {
      locale,
      appName: branding.appName,
      companyName: branding.companyName,
      logo,
      kind: content.kind,
      exportedAt: t('reports.document.exportedAt', { date: context.dateTime(new Date()) }),
      title: content.title,
      subtitle: content.subtitle !== content.title ? content.subtitle : undefined,
      details: content.details,
      notice: content.notice ?? null,
      exportedBy: t('reports.document.exportedBy', { name: branding.exportedBy }),
      identity: frameIdentity(content.identity, branding.domain),
      copyNotice: t('reports.document.copyNotice'),
      pageLabel: (page, pages) => t('reports.document.page', { page, pages }),
    },
    content.body,
  )
}
