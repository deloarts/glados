import { useI18n } from 'vue-i18n'

import { useConfirmAsync } from './useConfirmAsync'

/** The confirmation group of ConfirmHandler's delete dialog, which App.vue mounts once. */
export const CONFIRM_DELETE_GROUP = 'confirm-delete'

/**
 * Asks before something is deleted for good, such as a stored file, a
 * picture or a logo. It resolves to true only when the user confirms. The
 * dialog is ConfirmHandler's, mounted once in App.vue, so a caller
 * needs no ConfirmDialog of its own.
 */
export function useConfirmDelete() {
  const { t } = useI18n()
  const { ask } = useConfirmAsync()

  function confirmDelete(name: string): Promise<boolean> {
    return ask({
      group: CONFIRM_DELETE_GROUP,
      header: t('common.confirmDelete.title'),
      message: t('common.confirmDelete.message', { name }),
      icon: 'mdi mdi-alert-outline',
      rejectProps: { label: t('common.cancel'), severity: 'secondary' },
      acceptProps: { label: t('common.delete'), severity: 'danger' },
    })
  }

  return { confirmDelete }
}
