import {
  dateCell,
  listCell,
  recordLinkCell,
  tableExportColumns,
  urlCell,
  type SpreadsheetColumn,
} from '@/shared/spreadsheet-export'
import { localizeLabel } from '@/shared/utils/localizeLabel'

import type { MadeItemColumnDefinition } from '../stores/madeItemsCatalogueColumnsStore'
import type { MadeItemResponse } from '../types/madeItemsResponse'
import { processRoutingLabel } from './madeItemProcessGroups'

type Translate = (key: string) => string
type Field = MadeItemColumnDefinition['field']

/**
 * The picture and the files have nothing a spreadsheet cell can hold, and
 * the files are not part of the list response either. The link column at
 * the end leads to both.
 */
const SKIPPED_FIELDS = new Set<Field>(['image', 'files'])

/**
 * The export columns of the made item catalogue: the table's visible columns
 * in their order, with status and data source as their labels, the routing
 * as the text its tooltip shows, the source as its label and sublabel and the
 * labels by their localized names. Each date column is followed by the
 * person who set it, and the lasting link to the item's page comes last.
 */
export function madeItemsExportColumns(
  visibleColumns: readonly MadeItemColumnDefinition[],
  t: Translate,
  locale: string,
): SpreadsheetColumn<MadeItemResponse>[] {
  return tableExportColumns<MadeItemResponse, Field>({
    visibleColumns,
    skip: SKIPPED_FIELDS,
    cells: {
      status: (item) =>
        listCell([
          t(`madeItems.catalogue.status.${item.status}`),
          item.archived ? t('common.archivedTag') : null,
        ]),
      data_source: (item) => t(`madeItems.catalogue.dataSources.${item.data_source}`),
      article_groups: (item) => listCell(item.article_groups.map((group) => localizeLabel(group.name))),
      processes: (item) => processRoutingLabel(item.processes, locale) || null,
      source_label: (item) => listCell([item.source_label, item.source_sublabel]),
      weblink: (item) => urlCell(item.weblink),
      revision_date: (item) => dateCell(item.revision_date),
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
