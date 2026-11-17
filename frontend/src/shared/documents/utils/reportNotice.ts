import type { ControlledDocument } from '../types'
import type { Translate } from '@/core/i18n'

export interface DocumentReportNotice {
  text: string
  tone: 'fail' | 'warn'
}

/**
 * The warning a report of this revision carries, if any: that it was marked
 * invalid, or that a newer revision exists. The report frame shows it right
 * under the details.
 */
export function documentReportNotice(
  document: Pick<ControlledDocument, 'invalid_at' | 'invalid_by_full_name' | 'invalid_reason' | 'is_latest' | 'superseded_at'>,
  t: Translate,
  dateTime: (value: string) => string,
): DocumentReportNotice | null {
  if (document.invalid_at) {
    return {
      tone: 'fail',
      text: t('documents.report.invalid', {
        name: document.invalid_by_full_name ?? '',
        date: dateTime(document.invalid_at),
        reason: document.invalid_reason ?? '',
      }),
    }
  }
  if (!document.is_latest) {
    return {
      tone: 'warn',
      text: document.superseded_at
        ? t('documents.report.superseded', { date: dateTime(document.superseded_at) })
        : t('documents.report.notLatest'),
    }
  }
  return null
}
