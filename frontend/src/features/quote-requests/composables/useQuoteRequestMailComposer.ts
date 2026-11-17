import { reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { appLocaleForLanguage } from '@/core/i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { formatDateOrDash } from '@/core/utils/dates'
import { flaggedSupplierRecipients } from '@/features/contacts'
import { getSupplier } from '@/features/suppliers'
import { getDefaultMailTemplate } from '@/features/orders'
import { TABLE_COLUMN_KEYS, resolveOrderTemplate } from '@/shared/order-mail'
import type { MailTableItem, TableColumnLabels } from '@/shared/order-mail'
import type {
  QuoteRequestLineResponse,
  QuoteRequestResponse,
  QuoteRequestSupplierResponse,
} from '../types/quoteRequestsResponse'

export interface QuoteRequestMailState {
  to: string
  cc: string
  replyTo: string
  subject: string
  body: string
  warning: string
}

/** A request line shaped as the mail table reads an order line; it has no price. */
function mailRow(line: QuoteRequestLineResponse): MailTableItem {
  return {
    item_article_name: line.item_name,
    item_part_number: line.line_type === 'MADE' ? line.item_code : null,
    item_order_code_1: line.line_type === 'MADE' ? '' : line.item_code,
    item_order_code_2: null,
    item_specification: '',
    item_material: null,
    item_dimension: null,
    item_type_name: null,
    item_revision: null,
    item_base_size: null,
    lot_number: line.lot_number,
    fabrication_method: '',
    item_manufacturer: null,
    item_mass: null,
    quantity: line.quantity,
    items_per_unit: 1,
    unit: line.unit,
    price: null,
    note: line.note,
    project_number: line.project_number,
  }
}

/**
 * Composes the request mail to one supplier of a quote request, from the
 * supplier's request template or the admin default of the request kind, in
 * the supplier's request language. The table lists the open lines; the
 * total variables stay blank, since nothing is priced yet. The page marks
 * the supplier as sent once the mail went out.
 */
export function useQuoteRequestMailComposer() {
  const { t } = useI18n()
  const toast = useAppToast()
  const currentUserStore = useCurrentUserStore()
  const composing = ref(false)
  const dialogVisible = ref(false)
  const pendingRow = ref<QuoteRequestSupplierResponse | null>(null)
  const dialogState = reactive<QuoteRequestMailState>({
    to: '',
    cc: '',
    replyTo: '',
    subject: '',
    body: '',
    warning: '',
  })

  async function compose(
    request: QuoteRequestResponse,
    row: QuoteRequestSupplierResponse,
  ): Promise<void> {
    composing.value = true
    pendingRow.value = row
    try {
      const supplier = await getSupplier(row.supplier_id)
      const language = supplier.request_language ?? supplier.order_language
      let template = supplier.request_template ?? supplier.order_template
      if (!template) {
        try {
          const fallback = await getDefaultMailTemplate('request', language)
          if (fallback.configured) template = fallback.body
        } catch {
          // template stays empty and the warning below fires.
        }
      }
      if (!template) {
        toast.warn(
          t('orders.mail.noTemplateTitle'),
          t('orders.mail.noTemplateDetail', { supplier: supplier.name }),
        )
        return
      }
      const mailLocale = appLocaleForLanguage(language)
      const tm = (key: string, named: Record<string, unknown> = {}): string =>
        t(key, named, { locale: mailLocale })
      const labels = Object.fromEntries(
        TABLE_COLUMN_KEYS.map((k) => [k, tm(`orders.mail.columns.${k}`)]),
      ) as TableColumnLabels
      const lines = request.lines.filter((line) => line.state === 'open')
      const vars: Record<string, string> = {
        order_number: request.request_number,
        supplier: supplier.name,
        note: request.note ?? '',
        ordered_date: '-',
        expected_delivery: request.deadline ? formatDateOrDash(request.deadline) : '-',
        total: String(lines.length),
        total_price: '-',
        user_full_name: currentUserStore.user?.full_name ?? '',
        user_email: currentUserStore.user?.email ?? '',
      }
      dialogState.body = resolveOrderTemplate(template, vars, lines.map(mailRow), labels, mailLocale)
      dialogState.subject = tm('quoteRequests.mail.subject', {
        number: request.request_number,
        supplier: supplier.name,
      })
      // The contacts flagged for request mails, else the supplier's own address.
      dialogState.to =
        (await flaggedSupplierRecipients(supplier.id, 'request')) ??
        supplier.request_email ??
        supplier.order_email ??
        supplier.email ??
        ''
      dialogState.cc = currentUserStore.user?.email ?? ''
      dialogState.replyTo = currentUserStore.user?.email ?? ''
      dialogState.warning = supplier.archived
        ? t('orders.mail.supplierArchived', { supplier: supplier.name })
        : ''
      dialogVisible.value = true
    } catch {
      toast.error(t('orders.mail.errorTitle'))
    } finally {
      composing.value = false
    }
  }

  return { composing, compose, dialogVisible, dialogState, pendingRow }
}
