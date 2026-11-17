import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { usePrint } from '@/shared/print'

import type { PrintJob } from '@/shared/print'

export type LotPrintClassifier = 'lot_label' | 'lot_docket' | 'scrap_tag'

export type PrintableLot = { id: number; lot_number: string }

const I18N_STEMS: Record<LotPrintClassifier, string> = {
  lot_label: 'printLotLabel',
  lot_docket: 'printLotDocket',
  scrap_tag: 'printScrapTag',
}

// Lot label, docket and scrap tag printing. One job at a time per lot and
// classifier, so the menu can disable the item while it runs.
export function useLotPrinting() {
  const { t } = useI18n()
  const toast = useAppToast()
  const printService = usePrint()
  const { withErrorToast } = useErrorToast()

  const printingLot = ref<{ lotId: number; classifier: LotPrintClassifier } | null>(null)

  function isPrintingLot(lot: PrintableLot, classifier: LotPrintClassifier): boolean {
    return printingLot.value?.lotId === lot.id && printingLot.value?.classifier === classifier
  }

  async function onPrintLot(lot: PrintableLot, classifier: LotPrintClassifier): Promise<void> {
    const i18nStem = I18N_STEMS[classifier]
    printingLot.value = { lotId: lot.id, classifier }
    await withErrorToast(
      async () => {
        // The scrap tag's record is resolved on the server, so it has its own
        // lot-scoped endpoint.
        const job: PrintJob | undefined =
          classifier === 'scrap_tag'
            ? await printService.printLotScrapTag(lot.id)
            : (await printService.print({ root_type: 'production_lot', root_id: lot.id, items: [{ classifier }] }))[0]
        if (job?.status === 'sent') {
          toast.success(lot.lot_number, t(`production.lots.contextMenu.${i18nStem}Sent`))
        } else {
          toast.error(
            lot.lot_number,
            job?.error_message ?? t(`production.lots.contextMenu.${i18nStem}Failed`),
          )
        }
      },
      { summary: lot.lot_number, fallbackMessage: t(`production.lots.contextMenu.${i18nStem}Failed`) },
    )
    printingLot.value = null
  }

  return { isPrintingLot, onPrintLot }
}
