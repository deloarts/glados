<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useConfirm } from 'openvue/useconfirm'
import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { Permission } from '@/core/auth/permissions'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { useAppToast } from '@/core/composables/useAppToast'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { LiveResource } from '@/core/realtime/resources'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { extractApiError } from '@/core/utils/errors'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import { documentRowMenu, documentRowStep, documentRowSteps, editingBy, useDocumentRowLinks } from '@/shared/documents'
import type { DocumentPageAction } from '@/shared/documents'
import { createSequence, deleteSequence, getSequence, getSequences } from '../api/sequencesApi'
import { useSequencesViewStore } from '../stores/sequencesViewStore'
import type { SequenceSummaryResponse } from '../types/sequence'
import { sequenceLocation } from '../utils/routes'
import ProductVariantsDialog from './ProductVariantsDialog.vue'
import SequenceCreateDialog from './SequenceCreateDialog.vue'
import SequenceStatusTag from './SequenceStatusTag.vue'

/**
 * The Sequences tab of a product: the latest revision of each of its flow
 * sequences with document number, revision, status and steps. A row opens
 * the sequence's page; its context menu offers the document steps, which
 * the page carries out, and copying a sequence into a new draft of the
 * same product. New Sequence and Variants sit in the product page's
 * controls bar (SequencesControls). The list follows changes made
 * elsewhere live.
 */
const props = defineProps<{
  productId: number
  /** Whether the product's variants may be changed. */
  canEditVariants: boolean
}>()

const { t } = useI18n()
const router = useRouter()
const toast = useAppToast()
const confirm = useConfirm()
const links = useDocumentRowLinks()
const currentUserStore = useCurrentUserStore()
const { createRequests, variantsRequests } = storeToRefs(useSequencesViewStore())
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const sequences = ref<SequenceSummaryResponse[]>([])
const loading = ref(false)
watchLoadingBar(loading)

let loadSeq = 0
async function load(quiet = false): Promise<void> {
  const seq = ++loadSeq
  if (!quiet) loading.value = true
  try {
    const page = await getSequences({ product_id: props.productId, limit: API_MAX_PAGE_SIZE, order_by: 'title' })
    if (seq === loadSeq) sequences.value = page.items
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

onMounted(() => void load())
watch(() => props.productId, () => void load())

useLiveRefresh([LiveResource.SEQUENCES], () => load(true), { debounceMs: 300 })

// ── Create and variants ───────────────────────────────────────────────

const createVisible = ref(false)
const creating = ref(false)
// The sequence the create dialog copies; null for a new, empty one.
const copySource = ref<SequenceSummaryResponse | null>(null)
const variantsVisible = ref(false)
watch(createRequests, () => {
  copySource.value = null
  createVisible.value = true
})
watch(variantsRequests, () => (variantsVisible.value = true))

function askCopy(row: SequenceSummaryResponse): void {
  copySource.value = row
  createVisible.value = true
}

async function onCreate(name: string): Promise<void> {
  creating.value = true
  const source = copySource.value
  try {
    // A copy takes the steps of the revision the list shows, so it starts
    // as a new draft that reads exactly like it.
    const steps = source ? (await getSequence(source.id)).steps : []
    const created = await createSequence({ product_id: props.productId, name, steps })
    createVisible.value = false
    toast.success(created.name, t(source ? 'sequences.toasts.copied' : 'sequences.toasts.created'))
    await router.push(sequenceLocation(created, { action: 'edit' }))
  } catch (e) {
    toast.error(t('sequences.title'), extractApiError(e) ?? t('sequences.errors.unknown'))
  } finally {
    creating.value = false
  }
}

// ── Rows ──────────────────────────────────────────────────────────────

function open(row: SequenceSummaryResponse, action?: DocumentPageAction): void {
  void router.push(sequenceLocation(row, { action }))
}

const { missing } = useMissingPermission()

// Each step first asks whether the row's state allows it, then which
// permission or lock still blocks it; that blocker is the entry's title.
function steps(row: SequenceSummaryResponse) {
  const write = missing(Permission.WRITE_SEQUENCES)
  const manage = missing(Permission.MANAGE_SEQUENCES)
  const userId = currentUserStore.user?.id ?? null
  const ownOrManage = row.creator_id === userId ? '' : manage
  const released = row.released_at != null
  const draft = row.is_latest && !released
  const editor = editingBy(row)
  const locked = editor !== null && row.locked_by_id !== userId ? t('documents.table.editing', { name: editor }) : ''
  return documentRowSteps({
    edit: documentRowStep(draft && !row.read_only, [write, ownOrManage, locked]),
    revise: documentRowStep(row.is_latest && released, [write]),
    release: documentRowStep(draft && row.step_count > 0, [missing(Permission.RELEASE_SEQUENCES)]),
    invalidate: documentRowStep(released && row.invalid_at == null, [manage]),
    delete: documentRowStep(draft, [write, ownOrManage]),
  })
}

const menu = ref<{ show: (event: Event) => void } | null>(null)
const menuRow = ref<SequenceSummaryResponse | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  menuRow.value = event.data as SequenceSummaryResponse
  menu.value?.show(event.originalEvent)
}

// Copy needs Write Flow Sequences; without it the entry stays in the menu,
// disabled, and names the missing permission as its title.
const copyBlocked = computed(() => missing(Permission.WRITE_SEQUENCES))

const menuItems = computed<MenuItem[]>(() => {
  const row = menuRow.value
  if (!row) return []
  return documentRowMenu(
    {
      open: () => open(row),
      openInNewTab: () => links.openInNewTab(sequenceLocation(row)),
      copyLink: () => void links.copyLink(sequenceLocation(row)),
      remove: () => askRemove(row),
      pageAction: (action) => open(row, action),
      ...steps(row),
      extra: [
        {
          label: t('sequences.copy.menu'),
          icon: 'mdi mdi-content-copy',
          disabled: copyBlocked.value !== '',
          title: copyBlocked.value || undefined,
          command: () => askCopy(row),
        },
      ],
    },
    t,
  )
})

function askRemove(row: SequenceSummaryResponse): void {
  async function onAccept(): Promise<void> {
    try {
      await deleteSequence(row.id)
      toast.success(row.name, t('sequences.toasts.deleted'))
      await load(true)
    } catch (e) {
      toast.error(row.name, extractApiError(e) ?? t('sequences.errors.unknown'))
    }
  }

  confirm.require({
    group: 'sequences-tab',
    header: t('sequences.confirm.delete.header'),
    message: t('sequences.confirm.delete.message'),
    icon: 'mdi mdi-alert-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('sequences.confirm.delete.accept'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}
</script>

<template>
  <div class="sequences-tab">
    <DataTable
      :value="sequences"
      data-key="id"
      size="small"
      scrollable
      scroll-height="flex"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      v-model:context-menu-selection="menuRow"
      context-menu
      selection-mode="single"
      class="sequences-table clickable-rows"
      data-testid="sequences-table"
      @row-click="open($event.data as SequenceSummaryResponse)"
      @row-contextmenu="onRowContextMenu"
    >
      <template #empty>
        <EmptyState />
      </template>
      <Column header="#" class="column-fit" body-class="row-number">
        <template #body="{ index }">{{ index + 1 }}</template>
      </Column>
      <Column :header="t('sequences.list.number')" class="column-fit">
        <template #body="{ data }: { data: SequenceSummaryResponse }">
          <span class="document-number">
            {{ data.document_number }}
            <i
              v-if="editingBy(data) !== null"
              v-tooltip.bottom="t('documents.table.editing', { name: editingBy(data) })"
              class="mdi mdi-lock-outline lock-icon"
              :aria-label="t('documents.table.editing', { name: editingBy(data) })"
            />
          </span>
        </template>
      </Column>
      <Column :header="t('sequences.list.status')" class="column-fit">
        <template #body="{ data }: { data: SequenceSummaryResponse }">
          <SequenceStatusTag :sequence="data" />
        </template>
      </Column>
      <Column :header="t('sequences.fields.name')" class="column-fit">
        <template #body="{ data }: { data: SequenceSummaryResponse }">
          <span class="name">{{ data.name }}</span>
        </template>
      </Column>
      <Column :header="t('sequences.list.steps')" class="column-fit">
        <template #body="{ data }: { data: SequenceSummaryResponse }">{{ data.step_count }}</template>
      </Column>
      <Column :header="t('documents.table.revision')" class="column-fit">
        <template #body="{ data }: { data: SequenceSummaryResponse }">{{ data.revision }}</template>
      </Column>
      <Column :header="t('documents.table.released')" class="column-fit">
        <template #body="{ data }: { data: SequenceSummaryResponse }">
          <UserDateCell
            :date="data.released_at"
            :user-id="data.released_by_id"
            :name="data.released_by_full_name"
            with-time
          />
        </template>
      </Column>
      <Column :header="t('sequences.list.author')" class="column-fit">
        <template #body="{ data }: { data: SequenceSummaryResponse }">
          <UserDateCell :date="data.created" :user-id="data.creator_id" :name="data.creator_full_name" with-time />
        </template>
      </Column>
      <Column :header="t('sequences.list.changed')" class="column-fit">
        <template #body="{ data }: { data: SequenceSummaryResponse }">
          <UserDateCell
            :date="data.changed ?? data.created"
            :user-id="data.changed ? data.changed_by_id : data.creator_id"
            :name="data.changed ? data.changed_by_full_name : data.creator_full_name"
            with-time
          />
        </template>
      </Column>
      <!-- Every column is as wide as its content; this empty one takes the rest of the width. -->
      <Column />
    </DataTable>

    <ContextMenu
      ref="menu"
      :model="menuItems"
      :pt="disabledItemTooltipPt"
      @hide="menuRow = null"
    />
    <ConfirmDialog group="sequences-tab" />

    <SequenceCreateDialog
      v-model:visible="createVisible"
      :busy="creating"
      :copy-of="copySource?.name ?? null"
      @create="onCreate"
    />
    <ProductVariantsDialog v-model:visible="variantsVisible" :product-id="productId" :can-edit="canEditVariants" />
  </div>
</template>

<style scoped lang="scss">
.sequences-tab {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.sequences-table {
  flex: 1;
  min-height: 0;
}

.name {
  font-weight: 500;
}

.document-number {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

.lock-icon {
  color: var(--p-text-muted-color);
}
</style>
