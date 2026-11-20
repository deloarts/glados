import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { flaggedSupplierRecipients } from '@/features/contacts'
import type { SupplierMailKind } from '@/features/contacts'
import { getSupplier } from '@/features/suppliers'
import type { SupplierResponse } from '@/features/suppliers'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { appLocaleForLanguage } from '@/core/i18n'
import { formatPrice } from '@/core/utils/currency'
import { TABLE_COLUMN_KEYS, resolveOrderTemplate } from '@/shared/order-mail'
import type { TableColumnLabels } from '@/shared/order-mail'
import { extraCostName, signedExtraCost } from '@/shared/utils/extraCosts'
import { getDefaultMailTemplate } from '../api/getDefaultMailTemplate'
import type { OrderResponse } from '../types/ordersResponse'

// order_canceled has no per-supplier template, so it always uses the admin
// default.
export type OrderMailType = 'request' | 'order' | 'order_canceled'

export interface MailComposeState {
  to: string
  cc: string
  replyTo: string
  subject: string
  body: string
  warning: string
}

// ── Per-type resolution ─────────────────────────────────────────────────
// Explicit maps per mail type instead of ternaries that would fold a third
// type into the wrong branch. order and order_canceled share the order
// language and recipient.

function supplierTemplateFor(type: OrderMailType, supplier: SupplierResponse): string | null {
  switch (type) {
    case 'request':
      return supplier.request_template ?? supplier.order_template
    case 'order':
      return supplier.order_template
    case 'order_canceled':
      return null
  }
}

function languageFor(type: OrderMailType, supplier: SupplierResponse): string | null {
  switch (type) {
    case 'request':
      return supplier.request_language ?? supplier.order_language
    case 'order':
    case 'order_canceled':
      return supplier.order_language
  }
}

// The contacts flag for the mail kind; a cancellation goes where the order went.
const CONTACT_MAIL_KIND: Record<OrderMailType, SupplierMailKind> = {
  request: 'request',
  order: 'order',
  order_canceled: 'order',
}

// The supplier's own addresses, which apply when no contact is flagged.
function recipientFor(type: OrderMailType, supplier: SupplierResponse): string {
  switch (type) {
    case 'request':
      return supplier.request_email ?? supplier.order_email ?? supplier.email ?? ''
    case 'order':
    case 'order_canceled':
      return supplier.order_email ?? supplier.email ?? ''
  }
}

// Explicit, since the type name is not the camelCase key for order_canceled.
const SUBJECT_KEYS: Record<OrderMailType, string> = {
  request: 'requestSubject',
  order: 'orderSubject',
  order_canceled: 'orderCanceledSubject',
}

export function useOrderMailComposer() {
  const { t } = useI18n()
  const toast = useAppToast()
  const currentUserStore = useCurrentUserStore()
  const composing = ref(false)
  const dialogVisible = ref(false)
  const dialogState = reactive<MailComposeState>({
    to: '',
    cc: '',
    replyTo: '',
    subject: '',
    body: '',
    warning: '',
  })
  const pendingOrder = ref<OrderResponse | null>(null)
  const pendingMailType = ref<OrderMailType>('order')
  // The "mail sent, mark the items too?" follow-up.
  const showPostSend = ref(false)

  /**
   * Offers the follow-up after a request or order mail, whose lines the
   * user may now mark requested or ordered. A cancellation notice goes out
   * for an order that is already canceled, so there is nothing to mark.
   */
  function onMailSent(): void {
    showPostSend.value = pendingMailType.value !== 'order_canceled'
  }

  async function composeOrderMail(order: OrderResponse, type: OrderMailType): Promise<void> {
    pendingOrder.value = order
    pendingMailType.value = type
    composing.value = true
    try {
      const supplier = await getSupplier(order.supplier_id)

      // Mail content follows the supplier's template language, not the UI locale.
      const language = languageFor(type, supplier)

      let template = supplierTemplateFor(type, supplier)

      if (!template) {
        // Falls back to the admin default. A failed lookup leaves the template null,
        // so the "no template configured" warning fires instead of a generic error.
        try {
          const fallback = await getDefaultMailTemplate(type, language)
          if (fallback.configured) template = fallback.body
        } catch {
          // template stays null.
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

      const columnLabels = Object.fromEntries(
        TABLE_COLUMN_KEYS.map((k) => [k, tm(`orders.mail.columns.${k}`)]),
      ) as TableColumnLabels

      const orderItems = order.items ?? []
      const totalPrice = order.net_total === null ? '-' : formatPrice(order.net_total, mailLocale)
      const extras = order.extra_costs.map((cost) => ({
        name: extraCostName(tm, cost),
        amount: formatPrice(signedExtraCost(cost.kind, cost.amount), mailLocale),
      }))

      const vars: Record<string, string> = {
        order_number: order.order_number,
        supplier_order_numbers: order.supplier_order_numbers.join(', '),
        supplier: supplier.name,
        note: order.note ?? '',
        ordered_date: order.ordered_date ?? '-',
        expected_delivery: order.expected_delivery_date ?? '-',
        total: String(orderItems.length),
        total_price: totalPrice,
        user_full_name: currentUserStore.user?.full_name ?? '',
        user_email: currentUserStore.user?.email ?? '',
      }

      const body = resolveOrderTemplate(
        template,
        vars,
        orderItems,
        columnLabels,
        mailLocale,
        extras,
      )
      const subject = tm(`orders.mail.${SUBJECT_KEYS[type]}`, {
        order_number: order.order_number,
        supplier: supplier.name,
      })
      const to =
        (await flaggedSupplierRecipients(supplier.id, CONTACT_MAIL_KIND[type])) ??
        recipientFor(type, supplier)

      dialogState.to = to
      dialogState.cc = currentUserStore.user?.email ?? ''
      dialogState.replyTo = currentUserStore.user?.email ?? ''
      dialogState.subject = subject
      dialogState.body = body
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

  return {
    composing,
    composeOrderMail,
    dialogVisible,
    dialogState,
    pendingOrder,
    pendingMailType,
    showPostSend,
    onMailSent,
  }
}
