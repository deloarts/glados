import {
  dateCell,
  listCell,
  recordLinkCell,
  tableExportColumns,
  urlCell,
  type SpreadsheetColumn,
} from '@/shared/spreadsheet-export'
import { localizeLabel } from '@/shared/utils/localizeLabel'

import type { BoughtItemColumnDefinition } from '../stores/boughtItemsCatalogueColumnsStore'
import type { BoughtItemResponse } from '../types/boughtItemsResponse'

type Translate = (key: string) => string

/**
 * The export columns of the bought item catalogue: the table's visible
 * columns in their order, with status and data source as their labels, the
 * labels by their localized names, the weblink clickable and the PDF files as
 * their count. Each date column is followed by the person who set it, and the
 * lasting link to the item's page comes last, standing in for the picture a
 * spreadsheet cannot hold.
 */
export function boughtItemsExportColumns(
  visibleColumns: readonly BoughtItemColumnDefinition[],
  t: Translate,
): SpreadsheetColumn<BoughtItemResponse>[] {
  return tableExportColumns<BoughtItemResponse, BoughtItemColumnDefinition['field']>({
    visibleColumns,
    cells: {
      status: (item) =>
        listCell([
          t(`boughtItems.catalogue.status.${item.status}`),
          item.archived ? t('common.archivedTag') : null,
        ]),
      data_source: (item) => t(`boughtItems.catalogue.dataSources.${item.data_source}`),
      article_groups: (item) => listCell(item.article_groups.map((group) => localizeLabel(group.name))),
      product_family: (item) => localizeLabel(item.product_family?.name) || null,
      pdf_files: (item) => item.pdf_files.length,
      weblink: (item) => urlCell(item.weblink),
      created: (item) => dateCell(item.created),
      changed: (item) => dateCell(item.changed),
    },
    after: {
      created: {
        header: t('spreadsheetExport.columns.createdBy'),
        value: (item) => item.creator?.full_name ?? null,
      },
      changed: {
        header: t('spreadsheetExport.columns.changedBy'),
        value: (item) => item.changed_by?.full_name ?? null,
      },
    },
    trailing: [
      { header: t('spreadsheetExport.columns.link'), value: (item) => recordLinkCell(item.public_id) },
    ],
  })
}
