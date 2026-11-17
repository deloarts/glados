import type { ControlledDocument } from '../types'
import type { Translate } from '@/core/i18n'

/** "CAL-26-0042 rev. B", how a revision of a document is quoted. */
export function documentReference(
  document: Pick<ControlledDocument, 'document_number' | 'revision'>,
  t: Translate,
): string {
  return t('documents.reference', { number: document.document_number, revision: document.revision })
}

/** "B", or "B (draft)" while the revision is not released yet. */
export function revisionLabel(document: Pick<ControlledDocument, 'revision' | 'released_at'>, t: Translate): string {
  return document.released_at
    ? document.revision
    : t('documents.revision.draft', { revision: document.revision })
}
