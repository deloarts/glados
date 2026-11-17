import { i18n } from '@/core/i18n'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

import type { PdmFileKind } from '../types/adminSettingsTypes'

/**
 * Renders a PDM file's made/bought/document kind for display, shared by
 * PdmFilesDialog and PdmSyncLogDialog. Null happens for a file under a
 * `by_kind` watched folder whose datacard has not yet supplied a kind value,
 * rendered with the same empty placeholder every other unset field on
 * these dialogs uses, not a bespoke dash.
 */
export function kindLabel(kind: PdmFileKind | null): string {
  const { t } = i18n.global
  if (kind === 'made') return t('adminSettings.itemFields.madeSection')
  if (kind === 'bought') return t('adminSettings.itemFields.boughtSection')
  if (kind === 'document') return t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.exportedDocuments')
  return getEmptyPlaceholder()
}
