import { demandExportColumns } from '@/shared/components/demands/demandExportColumns'

import type { SpreadsheetColumn } from '@/shared/spreadsheet-export'
import type { BoughtItemDemandResponse } from '@/features/bought-items'

/**
 * The export columns of the bought item demands: the columns every demand
 * list shares, with the article name, order code, part number and
 * manufacturer of the demanded item in the middle.
 */
export function boughtItemDemandsExportColumns(
  t: (key: string) => string,
  bucketName: (bucketId: number) => string | null,
): SpreadsheetColumn<BoughtItemDemandResponse>[] {
  return demandExportColumns<BoughtItemDemandResponse>({
    t,
    prefix: 'boughtItems.demands',
    bucketName,
    itemColumns: [
      { header: t('boughtItems.demands.columns.item'), value: (demand) => demand.item_article_name || null },
      { header: t('boughtItems.catalogue.columns.orderCode1'), value: (demand) => demand.item_order_code_1 || null },
      { header: t('boughtItems.catalogue.columns.partNumber'), value: (demand) => demand.item?.part_number ?? null },
      {
        header: t('boughtItems.demands.columns.manufacturer'),
        value: (demand) => demand.item?.manufacturer_name ?? null,
      },
    ],
    itemPublicId: (demand) => demand.item?.public_id,
  })
}
