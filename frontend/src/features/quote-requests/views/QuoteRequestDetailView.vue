<script setup lang="ts">
// One quote request: its lines against the suppliers asked, with each
// offer, the cheapest per line and overall, and the actions that send the
// request, record offers and award the lines onto draft orders. A closed
// request on which an award was voided since offers Reopen. Its changelog
// sits below the comparison.
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useConfirm } from 'openvue/useconfirm'
import type { MenuItem } from 'openvue/menuitem'

import { Permission } from '@/core/auth/permissions'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePageTitle } from '@/core/composables/usePageTitle'
import { useAppToast } from '@/core/composables/useAppToast'
import { formatDateOrDash } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import { MailComposeDialog } from '@/features/mail'
import ChangelogCard from '@/shared/components/changelog/ChangelogCard.vue'
import { HelpButton } from '@/shared/help'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ShareButton from '@/shared/components/resource-view/ShareButton.vue'
import { useQuoteRequestChangelog } from '../composables/useQuoteRequestChangelog'
import { useQuoteRequestDetail } from '../composables/useQuoteRequestDetail'
import { useQuoteRequestMailComposer } from '../composables/useQuoteRequestMailComposer'
import { dropQuoteRequestLine } from '../api/dropQuoteRequestLine'
import { endQuoteRequest } from '../api/endQuoteRequest'
import { markQuoteRequestSupplierSent } from '../api/markQuoteRequestSupplierSent'
import { removeQuoteRequestLine } from '../api/removeQuoteRequestLine'
import { removeQuoteRequestSupplier } from '../api/removeQuoteRequestSupplier'
import { reopenQuoteRequest } from '../api/reopenQuoteRequest'
import { isQuoteRequestOpen, quoteRequestStatusSeverity } from '../utils/quoteRequestFormat'
import QuoteComparisonTable from '../components/QuoteComparisonTable.vue'
import QuoteOfferDialog from '../components/QuoteOfferDialog.vue'
import QuoteAwardDialog from '../components/QuoteAwardDialog.vue'
import QuoteLineSubstituteDialog from '../components/QuoteLineSubstituteDialog.vue'
import QuoteRequestEditDialog from '../components/QuoteRequestEditDialog.vue'
import QuoteRequestReopenButton from '../components/QuoteRequestReopenButton.vue'
import QuoteRequestSuppliersDialog from '../components/QuoteRequestSuppliersDialog.vue'
import type {
  QuoteRequestLineResponse,
  QuoteRequestResponse,
  QuoteRequestSupplierResponse,
} from '../types/quoteRequestsResponse'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const confirm = useConfirm()
const toast = useAppToast()
const { missing } = useMissingPermission()

// The route constrains :id to `\d+`.
const requestId = Number(route.params.id)
const { request, loading, notFound, loadError, reload, replace } = useQuoteRequestDetail(requestId)
watchLoadingBar(loading)

// Every new state of the request may have added changelog lines.
const {
  entries: changelogEntries,
  loading: changelogLoading,
  error: changelogError,
  reload: reloadChangelog,
} = useQuoteRequestChangelog(requestId)
watch(request, (current) => {
  if (current) void reloadChangelog()
})

const heading = computed(() =>
  request.value
    ? t('quoteRequests.detail.title', { number: request.value.request_number })
    : t('pageTitles.quoteRequestDetail'),
)
const { setPageTitle } = usePageTitle()
watch(heading, setPageTitle, { immediate: true })

const writeBlocked = computed(() => missing(Permission.WRITE_ORDERS))
const sendBlocked = computed(() => missing(Permission.WRITE_ORDERS, Permission.SEND_MAIL))
const open = computed(() => (request.value ? isQuoteRequestOpen(request.value) : false))
const actions = computed(() => request.value?.actions ?? [])

// Every disabled header action names its reason: the missing permission,
// else the request's state, else what the action still needs.
const stateBlocked = computed(() => {
  if (!request.value || open.value) return ''
  const status = t(`quoteRequests.status.${request.value.status}`).toLowerCase()
  return t('quoteRequests.blocked.ended', { status })
})
const editBlocked = computed(() => writeBlocked.value || stateBlocked.value)

function actionBlocked(action: 'award' | 'close' | 'cancel'): string {
  if (writeBlocked.value) return writeBlocked.value
  if (actions.value.includes(action)) return ''
  if (stateBlocked.value) return stateBlocked.value
  if (action === 'award') return t('quoteRequests.blocked.noOpenLine')
  if (action === 'close') return t('quoteRequests.blocked.noAwardedLine')
  return t('quoteRequests.blocked.hasAwardedLine')
}

const awardSelectedBlocked = computed(
  () => actionBlocked('award') || (selection.value.size === 0 ? t('quoteRequests.blocked.noSelection') : ''),
)
const awardAllBlocked = computed(
  () =>
    actionBlocked('award') ||
    (request.value?.suppliers.length === 0 ? t('quoteRequests.blocked.noSuppliers') : ''),
)

// ── Award selection ───────────────────────────────────────────────────

const selection = ref<Map<number, number>>(new Map())
watch(request, (current) => {
  if (!current) return
  const openLines = new Set(current.lines.filter((l) => l.state === 'open').map((l) => l.id))
  const rows = new Set(current.suppliers.map((s) => s.id))
  selection.value = new Map(
    [...selection.value].filter(([line, row]) => openLines.has(line) && rows.has(row)),
  )
})

function selectCheapest(): void {
  const current = request.value
  if (!current) return
  const next = new Map<number, number>()
  for (const line of current.lines) {
    if (line.state === 'open' && line.cheapest_supplier_id !== null) {
      next.set(line.id, line.cheapest_supplier_id)
    }
  }
  selection.value = next
}

function awardAllTo(row: QuoteRequestSupplierResponse): void {
  const current = request.value
  if (!current) return
  const next = new Map<number, number>()
  for (const line of current.lines) {
    const quote = row.quotes.find((q) => q.line_id === line.id)
    if (line.state === 'open' && !quote?.no_offer) next.set(line.id, row.id)
  }
  selection.value = next
  openAward()
}

const awardAllItems = computed<MenuItem[]>(() =>
  (request.value?.suppliers ?? []).map((row) => ({
    label: row.supplier_name,
    icon: 'mdi mdi-domain',
    command: () => awardAllTo(row),
  })),
)
const awardAllMenu = ref()

// ── Dialogs ───────────────────────────────────────────────────────────

const offerDialog = ref<InstanceType<typeof QuoteOfferDialog> | null>(null)
const awardDialog = ref<InstanceType<typeof QuoteAwardDialog> | null>(null)
const editDialog = ref<InstanceType<typeof QuoteRequestEditDialog> | null>(null)
const suppliersDialog = ref<InstanceType<typeof QuoteRequestSuppliersDialog> | null>(null)
const substituteDialog = ref<InstanceType<typeof QuoteLineSubstituteDialog> | null>(null)

function openAward(): void {
  if (request.value && selection.value.size > 0) {
    void awardDialog.value?.open(request.value, selection.value)
  }
}

function onAwarded(): void {
  selection.value = new Map()
  void reload({ quiet: true })
}

async function act(
  action: () => Promise<QuoteRequestResponse>,
  title: string,
): Promise<void> {
  try {
    replace(await action())
  } catch (e) {
    toast.error(title, extractApiError(e) ?? t('quoteRequests.detail.errors.unknown'))
  }
}

function confirmThen(
  header: string,
  message: string,
  label: string,
  action: () => Promise<QuoteRequestResponse>,
): void {
  confirm.require({
    header,
    message,
    icon: 'mdi mdi-alert-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label, severity: 'danger' },
    accept: () => void act(action, header),
  })
}

function onRemoveLine(line: QuoteRequestLineResponse): void {
  confirmThen(
    t('quoteRequests.actions.removeLine'),
    t('quoteRequests.detail.removeLineConfirm', { line: line.item_name }),
    t('quoteRequests.actions.removeLine'),
    () => removeQuoteRequestLine(requestId, line.id),
  )
}

function onRemoveSupplier(row: QuoteRequestSupplierResponse): void {
  confirmThen(
    t('quoteRequests.actions.removeSupplier'),
    t('quoteRequests.detail.removeSupplierConfirm', { supplier: row.supplier_name }),
    t('quoteRequests.actions.removeSupplier'),
    () => removeQuoteRequestSupplier(requestId, row.id),
  )
}

function onEnd(action: 'close' | 'cancel'): void {
  const current = request.value
  if (!current) return
  const label = t(action === 'close' ? 'quoteRequests.actions.close' : 'quoteRequests.actions.cancel')
  confirmThen(
    label,
    t(action === 'close' ? 'quoteRequests.detail.closeConfirm' : 'quoteRequests.detail.cancelConfirm'),
    label,
    () => endQuoteRequest(requestId, action, current.edit_version),
  )
}

function onReopen(): void {
  const current = request.value
  if (!current) return
  void act(() => reopenQuoteRequest(requestId, current.edit_version), t('quoteRequests.actions.reopen'))
}

// ── Mail ──────────────────────────────────────────────────────────────

const {
  compose,
  dialogVisible: mailVisible,
  dialogState: mailState,
  pendingRow: mailRow,
} = useQuoteRequestMailComposer()

function onSendMail(row: QuoteRequestSupplierResponse): void {
  if (request.value) void compose(request.value, row)
}

function onMailSent(): void {
  const row = mailRow.value
  if (row) void act(() => markQuoteRequestSupplierSent(requestId, row.id), row.supplier_name)
}
</script>

<template>
  <PageLayout data-class="rfq-detail-data">
    <template #info>
      <InfoBar>
        <template v-if="request">
          <span class="request-number">{{ request.request_number }}</span>
          <span class="info-sep" />
          <Tag
            :value="t(`quoteRequests.status.${request.status}`)"
            :severity="quoteRequestStatusSeverity(request.status)"
          />
          <span class="info-sep" />
          <span class="info-field">
            <i
              class="mdi mdi-calendar-clock"
              aria-hidden="true"
              v-tooltip.bottom="t('quoteRequests.detail.deadline')"
            />
            <span class="info-muted">
              {{ request.deadline ? formatDateOrDash(request.deadline) : t('quoteRequests.detail.noDeadline') }}
            </span>
          </span>
          <span class="info-sep" />
          <span class="info-muted">{{ request.creator?.full_name ?? '' }}</span>
          <template v-if="request.note">
            <span class="info-sep" />
            <span class="info-muted note">{{ request.note }}</span>
          </template>
        </template>
      </InfoBar>
    </template>

    <template #controls>
      <ControlsBar>
        <template #start>
          <Button
            icon="mdi mdi-arrow-left"
            :label="t('quoteRequests.detail.back')"
            severity="contrast"
            text
            @click="router.push('/procurement/quotes')"
          />
          <template v-if="request">
            <Divider layout="vertical" />
            <span v-tooltip.bottom="editBlocked">
              <Button
                icon="mdi mdi-domain-plus"
                :label="t('quoteRequests.actions.addSuppliers')"
                severity="contrast"
                text
                :disabled="editBlocked !== ''"
                @click="suppliersDialog?.open(request)"
              />
            </span>
            <span v-tooltip.bottom="editBlocked">
              <Button
                icon="mdi mdi-pencil"
                :label="t('quoteRequests.actions.edit')"
                severity="contrast"
                text
                :disabled="editBlocked !== ''"
                @click="editDialog?.open(request)"
              />
            </span>
            <Divider layout="vertical" />
            <span v-tooltip.bottom="actionBlocked('award')">
              <Button
                icon="mdi mdi-sort-numeric-ascending"
                :label="t('quoteRequests.actions.chooseCheapest')"
                severity="contrast"
                text
                :disabled="actionBlocked('award') !== ''"
                @click="selectCheapest"
              />
            </span>
            <span v-tooltip.bottom="awardSelectedBlocked">
              <Button
                icon="mdi mdi-gavel"
                :label="t('quoteRequests.actions.awardSelected', { count: selection.size })"
                severity="contrast"
                text
                :disabled="awardSelectedBlocked !== ''"
                data-testid="award-selected"
                @click="openAward"
              />
            </span>
            <span v-tooltip.bottom="awardAllBlocked">
              <Button
                icon="mdi mdi-gavel"
                :label="t('quoteRequests.actions.awardAllTo')"
                severity="contrast"
                text
                :disabled="awardAllBlocked !== ''"
                @click="awardAllMenu?.toggle($event)"
              />
            </span>
            <Divider layout="vertical" />
            <span v-tooltip.bottom="actionBlocked('close')">
              <Button
                icon="mdi mdi-check-decagram-outline"
                :label="t('quoteRequests.actions.close')"
                severity="contrast"
                text
                :disabled="actionBlocked('close') !== ''"
                @click="onEnd('close')"
              />
            </span>
            <span v-tooltip.bottom="actionBlocked('cancel')">
              <Button
                icon="mdi mdi-close-circle-outline"
                :label="t('quoteRequests.actions.cancel')"
                severity="contrast"
                text
                :disabled="actionBlocked('cancel') !== ''"
                @click="onEnd('cancel')"
              />
            </span>
            <QuoteRequestReopenButton :request="request" :write-blocked="writeBlocked" @reopen="onReopen" />
          </template>
        </template>
        <template #handbook>
          <ShareButton :public-id="request?.public_id" />
          <HelpButton rounded />
        </template>
      </ControlsBar>
    </template>

    <div v-if="loading" class="state-center" />
    <div v-else-if="notFound" class="state-center state-message">
      <i class="mdi mdi-alert-circle-outline state-icon" aria-hidden="true" />
      <span>{{ t('quoteRequests.detail.notFound') }}</span>
    </div>
    <div v-else-if="loadError" class="state-center state-message">
      <i class="mdi mdi-alert-outline state-icon" aria-hidden="true" />
      <span>{{ t('quoteRequests.detail.loadError') }}</span>
    </div>
    <template v-else-if="request">
      <QuoteComparisonTable
        v-model:selection="selection"
        :request="request"
        :write-blocked="writeBlocked"
        :send-blocked="sendBlocked"
        @enter-offer="offerDialog?.open(request, $event)"
        @send-mail="onSendMail"
        @mark-sent="(row) => act(() => markQuoteRequestSupplierSent(requestId, row.id), row.supplier_name)"
        @remove-supplier="onRemoveSupplier"
        @drop-line="(line) => act(() => dropQuoteRequestLine(requestId, line.id), line.item_name)"
        @restore-line="(line) => act(() => dropQuoteRequestLine(requestId, line.id, true), line.item_name)"
        @remove-line="onRemoveLine"
        @substitute-line="substituteDialog?.open(request, $event)"
      />
      <ChangelogCard
        class="rfq-changelog"
        :entries="changelogEntries"
        :loading="changelogLoading"
        :error="changelogError"
      />
    </template>
  </PageLayout>

  <Menu ref="awardAllMenu" :model="awardAllItems" popup />
  <QuoteOfferDialog ref="offerDialog" @saved="replace" />
  <QuoteAwardDialog ref="awardDialog" @awarded="onAwarded" />
  <QuoteLineSubstituteDialog ref="substituteDialog" @saved="replace" />
  <QuoteRequestEditDialog ref="editDialog" @saved="replace" />
  <QuoteRequestSuppliersDialog ref="suppliersDialog" @saved="replace" />
  <MailComposeDialog
    v-model:visible="mailVisible"
    :to="mailState.to"
    :cc="mailState.cc"
    :reply-to="mailState.replyTo"
    :subject="mailState.subject"
    :body="mailState.body"
    :warning="mailState.warning"
    @sent="onMailSent"
  />
</template>

<style scoped lang="scss">
:deep(.rfq-detail-data) {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.request-number {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.info-muted {
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}

.info-field {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--p-text-muted-color);

  i {
    font-size: var(--font-size-md);
  }
}

.note {
  max-width: 30rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rfq-changelog {
  margin-top: var(--space-4);
}

.state-center {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
}

.state-message {
  flex-direction: column;
  gap: var(--space-2);
  color: var(--p-text-muted-color);
}

.state-icon {
  font-size: var(--font-size-3xl);
}
</style>
