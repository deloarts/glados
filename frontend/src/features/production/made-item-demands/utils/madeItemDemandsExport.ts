import { processRoutingLabel } from '@/features/made-items'
import { demandExportColumns } from '@/shared/components/demands/demandExportColumns'

import type { SpreadsheetColumn } from '@/shared/spreadsheet-export'
import type { MadeItemDemandResponse } from '@/features/made-items'

/**
 * The export columns of the made item demands: the columns every demand
 * list shares, with the article name, part number, revision and routing of
 * the demanded item in the middle.
 */
export function madeItemDemandsExportColumns(
  t: (key: string) => string,
  locale: string,
  bucketName: (bucketId: number) => string | null,
): SpreadsheetColumn<MadeItemDemandResponse>[] {
  return demandExportColumns<MadeItemDemandResponse>({
    t,
    prefix: 'madeItems.demands',
    bucketName,
    itemColumns: [
      { header: t('madeItems.demands.columns.item'), value: (demand) => demand.item_article_name || null },
      { header: t('madeItems.catalogue.columns.partNumber'), value: (demand) => demand.item_part_number ?? null },
      { header: t('madeItems.catalogue.columns.revision'), value: (demand) => demand.item_revision ?? null },
      {
        header: t('madeItems.demands.columns.steps'),
        value: (demand) => processRoutingLabel(demand.item?.processes ?? [], locale) || null,
      },
    ],
    itemPublicId: (demand) => demand.item?.public_id,
  })
}
