import { demandExportColumns } from '@/shared/components/demands/demandExportColumns'
import { localizeLabel } from '@/shared/utils/localizeLabel'

import type { SpreadsheetColumn } from '@/shared/spreadsheet-export'
import type { SourceItemDemandResponse } from '@/features/source-items'

/**
 * The export columns of the source item demands: the columns every demand
 * list shares, with the demanded item in the middle. A demand names either a
 * source item, described by its dimension, material and type, or a bought
 * item, described by its article name and order code. The lot the material
 * is for follows. The table shows no priority, so neither does the file.
 */
export function sourceItemDemandsExportColumns(
  t: (key: string) => string,
  bucketName: (bucketId: number) => string | null,
): SpreadsheetColumn<SourceItemDemandResponse>[] {
  return demandExportColumns<SourceItemDemandResponse>({
    t,
    prefix: 'sourceItems.demands',
    bucketName,
    priority: false,
    itemColumns: [
      {
        header: t('sourceItems.demands.columns.item'),
        value: (demand) => demand.bought_item?.article_name || demand.source_item?.dimension || null,
      },
      { header: t('sourceItems.catalogue.columns.material'), value: (demand) => demand.source_item?.material || null },
      {
        header: t('sourceItems.catalogue.columns.type'),
        value: (demand) => localizeLabel(demand.source_item?.type_name) || null,
      },
      {
        header: t('sourceItems.catalogue.columns.orderCode1'),
        value: (demand) => demand.bought_item?.order_code_1 || demand.source_item?.order_code_1 || null,
      },
      {
        header: t('sourceItems.demands.columns.manufacturer'),
        value: (demand) => demand.bought_item?.manufacturer_name || demand.source_item?.manufacturer_name || null,
      },
      { header: t('sourceItems.demands.columns.lot'), value: (demand) => demand.lot_number || null },
    ],
    itemPublicId: (demand) => demand.bought_item?.public_id ?? demand.source_item?.public_id,
  })
}
