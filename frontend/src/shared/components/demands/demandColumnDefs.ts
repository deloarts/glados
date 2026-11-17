/**
 * Prop bags for the demand-table columns that are identical, or identical
 * apart from their header text and width, across the bought/made/source-item
 * demand tables. Each table spreads the returned object onto a real
 * `<Column v-bind="...">`, so OpenVue's DataTable still sees a genuine
 * Column child, only the props come from here. Column keys, header text and
 * widths are all parameters, the header text is resolved by the caller
 * through its own `t()` call so this file carries no i18n key of its own.
 */
export interface DemandColumnDef {
  field?: string
  header?: string
  style?: string
  headerStyle?: string
  bodyStyle?: string
  bodyClass?: string
  showFilterMenu?: boolean
  frozen?: boolean
}

/**
 * The leading row-number column: same "#" header and index formatting on
 * every demand table.
 */
export function demandRowNumberColumnDef(): DemandColumnDef {
  return {
    frozen: true,
    header: '#',
    headerStyle: 'width: 3rem',
    bodyClass: 'row-number',
  }
}

/**
 * The `id` column: same field on every table, only the header text and
 * width vary. No filter menu, each table renders its own inline `#filter`
 * input.
 */
export function demandIdColumnDef(header: string, width: string): DemandColumnDef {
  return { header, field: 'id', style: `width: ${width}`, showFilterMenu: false }
}

/**
 * The high-priority column's shape (field, width, no filter menu), body and
 * filter content stay with the caller.
 */
export function demandPriorityColumnDef(header: string): DemandColumnDef {
  return { field: 'high_priority', header, style: 'width: 6rem', showFilterMenu: false }
}

/**
 * The desired-delivery column's shape, body and filter content stay with
 * the caller.
 */
export function demandDesiredDeliveryColumnDef(header: string): DemandColumnDef {
  return { field: 'desired_delivery_date', header, style: 'width: 10rem', showFilterMenu: false }
}

/**
 * The created column's shape, which shows the creator below the date and
 * filters by both; body and filter content stay with the caller.
 */
export function demandCreatedColumnDef(header: string): DemandColumnDef {
  return { field: 'created', header, style: 'width: 10rem', showFilterMenu: false }
}
