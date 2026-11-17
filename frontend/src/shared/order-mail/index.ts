// The supplier mail templates of orders and quote requests: the line table
// a template's {{ table }} token expands to, template resolution for sending,
// and the sample preview the template editors show. Orders, quote requests,
// the supplier form and the admin mail template editor all build on it.
export {
  DEFAULT_TABLE_COLUMNS,
  TABLE_COLUMN_KEYS,
  buildTableHtml,
  resolveOrderTemplate,
} from './orderMailTemplate'
export { buildOrderMailPreviewHtml, SAMPLE_ORDER_MAIL_VARS } from './orderMailPreview'

export type { MailTableExtra, MailTableItem, TableColumnKey, TableColumnLabels } from './orderMailTemplate'
