import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { extractApiError } from '@/core/utils/errors'
import { usePrint } from '@/shared/print'
import { PRINT_ROOT_TYPE, printClassifier } from '../utils/printClassifiers'

import type { CatalogueItemKind } from '../types/itemDetail'

/**
 * Label and docket printing from a catalogue item detail page. Success only
 * when the job comes back sent; otherwise the job's error message, so it
 * reads like a print from the catalogue table.
 */
export function useCatalogueItemPrint(kind: CatalogueItemKind) {
  const { t } = useI18n()
  const toast = useAppToast()
  const printService = usePrint()

  /** The job in flight; only one classifier prints at a time. */
  const printing = ref<'label' | 'docket' | null>(null)

  const SENT_KEY: Record<'label' | 'docket', string> = {
    label: 'catalogue.itemDetail.print.labelSent',
    docket: 'catalogue.itemDetail.print.docketSent',
  }
  const FAILED_KEY: Record<'label' | 'docket', string> = {
    label: 'catalogue.itemDetail.print.labelFailed',
    docket: 'catalogue.itemDetail.print.docketFailed',
  }

  async function print(target: { id: number; summary: string }, which: 'label' | 'docket'): Promise<void> {
    printing.value = which
    try {
      const [job] = await printService.print({
        root_type: PRINT_ROOT_TYPE[kind],
        root_id: target.id,
        items: [{ classifier: printClassifier(kind, which) }],
      })
      if (job?.status === 'sent') {
        toast.success(target.summary, t(SENT_KEY[which]))
      } else {
        toast.error(target.summary, job?.error_message ?? t(FAILED_KEY[which]))
      }
    } catch (e) {
      toast.error(target.summary, extractApiError(e) ?? t(FAILED_KEY[which]))
    } finally {
      printing.value = null
    }
  }

  return { printing, print }
}
