import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'

export function useClipboard() {
  const { t } = useI18n()
  const toast = useAppToast()

  /**
   * Writes `value` to the clipboard and reports the outcome with a toast.
   * `successMessage` overrides the default confirmation text for callers
   * that need a more specific one (e.g. "secret copied"). Returns whether
   * the write succeeded so callers can fall back to a manual-copy affordance
   * (e.g. selecting the source text) when the browser denies clipboard
   * access.
   */
  async function copyToClipboard(value: string, successMessage?: string): Promise<boolean> {
    try {
      await navigator.clipboard.writeText(value)
      toast.info('', successMessage ?? t('common.copiedToClipboard'))
      return true
    } catch {
      toast.error('', t('common.copyFailed'))
      return false
    }
  }

  /** Copies a field value, doing nothing when the field is empty. */
  async function copyIfPresent(value: string | number | null | undefined): Promise<void> {
    if (value === null || value === undefined || value === '') return
    await copyToClipboard(String(value))
  }

  return { copyToClipboard, copyIfPresent }
}
