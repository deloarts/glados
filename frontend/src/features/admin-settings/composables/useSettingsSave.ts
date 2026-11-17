import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { extractApiError } from '@/core/utils/errors'

export function useSettingsSave(saveFn: () => Promise<unknown>) {
  const { t } = useI18n()
  const appToast = useAppToast()
  const saving = ref(false)

  async function onSave() {
    saving.value = true
    try {
      await saveFn()
      appToast.success(t('adminSettings.saved'))
    } catch (err: unknown) {
      // extractApiError surfaces a domain error's `detail` (e.g. the PDM
      // section's PdmSettingsInvalidError) when the backend sent one; a
      // plain/network error has none, so the summary alone still reads.
      appToast.error(t('adminSettings.errors.unknown'), extractApiError(err) ?? undefined)
    } finally {
      saving.value = false
    }
  }

  return { saving, onSave }
}
