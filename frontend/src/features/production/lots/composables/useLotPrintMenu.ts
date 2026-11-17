import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { MenuItem } from 'openvue/menuitem'
import type { LotPrintClassifier } from '../components/lots-table/useLotPrinting'

/**
 * The dropdown half of the lot detail's Print split button, shared by the
 * dialog header and the page's controls bar so both offer the same
 * documents with the same gating: the three printer labels and dockets,
 * and the inspection report, a PDF that also downloads without the print
 * permission. Every input is a getter so the menu stays reactive to props
 * and exposed component state alike.
 */
export function useLotPrintMenu(options: {
  canPrint: () => boolean
  hasScrap: () => boolean
  isPrinting: (classifier: LotPrintClassifier) => boolean
  print: (classifier: LotPrintClassifier) => void
  openReport: () => void
}) {
  const { t } = useI18n()

  const printMenuItems = computed<MenuItem[]>(() => [
    {
      label: t('production.lots.detail.print.label'),
      icon: 'mdi mdi-tag-outline',
      disabled: !options.canPrint() || options.isPrinting('lot_label'),
      command: () => options.print('lot_label'),
    },
    {
      label: t('production.lots.detail.print.docket'),
      icon: 'mdi mdi-file-document-outline',
      disabled: !options.canPrint() || options.isPrinting('lot_docket'),
      command: () => options.print('lot_docket'),
    },
    {
      label: t('production.lots.detail.print.scrapTag'),
      icon: 'mdi mdi-alert-octagon-outline',
      disabled: !options.canPrint() || options.isPrinting('scrap_tag') || !options.hasScrap(),
      command: () => options.print('scrap_tag'),
    },
    { separator: true },
    {
      label: t('production.lots.report.print'),
      icon: 'mdi mdi-file-certificate-outline',
      command: () => options.openReport(),
    },
  ])

  return { printMenuItems }
}
