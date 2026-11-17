<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { TOAST_LIFE_LONG, useAppToast } from '@/core/composables/useAppToast'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { useConfirm } from 'openvue/useconfirm'
import { storeToRefs } from 'pinia'
import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { usePrintTemplatesStore } from '../stores/printTemplatesStore'
import { PRINT_TEMPLATE_KINDS } from '../utils/printTemplateKinds'
import { testPrintPrinter } from '@/features/printers'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { extractApiError } from '@/core/utils/errors'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'

import type { PrintTemplateKind } from '../utils/printTemplateKinds'
import type { PrintTemplateResponse } from '../types/printTemplateResponse'

const props = defineProps<{ kind: PrintTemplateKind }>()

const emit = defineEmits<{
  edit: [template: PrintTemplateResponse]
  preview: [template: PrintTemplateResponse]
}>()

const { t } = useI18n()
const toast = useAppToast()
const { withErrorToast } = useErrorToast()
const confirm = useConfirm()
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const config = computed(() => PRINT_TEMPLATE_KINDS[props.kind])
const p = computed(() => config.value.i18nPrefix)

const store = usePrintTemplatesStore()
const storeRefs = storeToRefs(store)
const { loading, search } = storeRefs
const templates = computed(() => storeRefs[config.value.templatesKey].value)
watchLoadingBar(loading)

onMounted(() => store.refresh())

const canWrite = computed(() => hasPermission(Permission.WRITE_PRINTERS))
const canPrint = computed(() => hasPermission(Permission.PRINT_DOCUMENTS))

const filteredItems = computed(() => {
  const term = search.value.trim().toLowerCase()
  if (!term) return templates.value
  return templates.value.filter((tpl) =>
    t(`${p.value}.classifiers.${tpl.classifier}`).toLowerCase().includes(term),
  )
})

function onEdit(template: PrintTemplateResponse): void {
  emit('edit', template)
}

function onPreview(template: PrintTemplateResponse): void {
  emit('preview', template)
}

const testPrinting = ref<string | null>(null)

async function onTestPrint(template: PrintTemplateResponse): Promise<void> {
  if (!template.printer_id) return
  testPrinting.value = template.classifier
  try {
    await testPrintPrinter(template.printer_id)
    toast.success(template.printer_name, t('printers.testPrintSent'))
  } catch (e) {
    toast.error(template.printer_name, extractApiError(e) ?? t(`${p.value}.errors.unknown`))
  } finally {
    testPrinting.value = null
  }
}

function onReset(template: PrintTemplateResponse): void {
  confirm.require({
    message: t(`${p.value}.resetConfirm`, {
      name: t(`${p.value}.classifiers.${template.classifier}`),
    }),
    header: t(`${p.value}.reset`),
    icon: 'mdi mdi-backup-restore',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t(`${p.value}.reset`), severity: 'danger' },
    accept: () =>
      void withErrorToast(
        async () => {
          await store.reset(template.classifier)
          toast.success(t(`${p.value}.classifiers.${template.classifier}`), t(`${p.value}.resetDone`))
        },
        { summary: t(`${p.value}.errors.unknown`), life: TOAST_LIFE_LONG },
      ),
  })
}

// ── Context menu ─────────────────────────────────────────────────────

const cm = ref()
const contextMenuItem = ref<PrintTemplateResponse | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const template = contextMenuItem.value
  if (!template) return []

  return [
    {
      label: t(`${p.value}.previewAction`),
      icon: 'mdi mdi-eye-outline',
      disabled: !template.source,
      command: () => onPreview(template),
    },
    {
      label: t('printers.testPrint'),
      icon: 'mdi mdi-printer-check',
      disabled:
        !canPrint.value || !template.printer_id || testPrinting.value === template.classifier,
      command: () => void onTestPrint(template),
    },
    {
      label: t(`${p.value}.editTemplate`),
      icon: 'mdi mdi-pencil',
      disabled: !canWrite.value,
      command: () => onEdit(template),
    },
    { separator: true },
    {
      label: t(`${p.value}.reset`),
      icon: 'mdi mdi-backup-restore',
      disabled: !canWrite.value,
      command: () => onReset(template),
    },
  ]
})
</script>

<template>
  <DataTable
    :value="filteredItems"
    v-model:context-menu-selection="contextMenuItem"
    data-key="classifier"
    scrollable
    scroll-height="flex"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    resizable-columns
    column-resize-mode="fit"
    @row-contextmenu="onRowContextMenu"
  >
    <Column header="#" header-style="width: 3rem" body-class="row-number">
      <template #body="{ index }">{{ index + 1 }}</template>
    </Column>
    <Column
      v-if="store.showActions"
      :header="t(`${p}.columns.actions`)"
      style="width: 10rem"
    >
      <template #body="{ data }">
        <div class="row-actions">
          <Button
            icon="mdi mdi-eye-outline"
            size="small"
            severity="secondary"
            text
            :disabled="!(data as PrintTemplateResponse).source"
            v-tooltip.top.focus="t(`${p}.previewAction`)"
            :aria-label="t(`${p}.previewAction`)"
            @click="onPreview(data as PrintTemplateResponse)"
          />
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            :disabled="!canWrite"
            v-tooltip.top.focus="t(`${p}.editTemplate`)"
            :aria-label="t(`${p}.editTemplate`)"
            @click="onEdit(data as PrintTemplateResponse)"
          />
          <Button
            icon="mdi mdi-backup-restore"
            size="small"
            severity="danger"
            text
            :disabled="!canWrite"
            v-tooltip.top.focus="t(`${p}.reset`)"
            :aria-label="t(`${p}.reset`)"
            @click="onReset(data as PrintTemplateResponse)"
          />
        </div>
      </template>
    </Column>

    <Column :header="t(`${p}.columns.classifier`)" style="min-width: 14rem">
      <template #body="{ data }">
        <span :class="{ 'text-muted': !(data as PrintTemplateResponse).source }">
          {{ t(`${p}.classifiers.${(data as PrintTemplateResponse).classifier}`) }}
        </span>
      </template>
    </Column>

    <Column :header="t(`${p}.columns.enabled`)" style="width: 6rem">
      <template #body="{ data }">
        <i
          :class="
            (data as PrintTemplateResponse).enabled
              ? 'mdi mdi-check-circle-outline text-success'
              : 'mdi mdi-close-circle-outline text-muted'
          "
          aria-hidden="true"
        />
      </template>
    </Column>

    <Column :header="t(`${p}.columns.autoPrint`)" style="width: 6rem">
      <template #body="{ data }">
        <i
          v-tooltip.top="
            (data as PrintTemplateResponse).trigger
              ? undefined
              : t(`${p}.manualOnlyHint`)
          "
          :class="
            (data as PrintTemplateResponse).auto_print
              ? 'mdi mdi-flash text-success'
              : 'mdi mdi-flash-off text-muted'
          "
          aria-hidden="true"
        />
      </template>
    </Column>

    <Column :header="t(`${p}.columns.trigger`)" style="min-width: 12rem">
      <template #body="{ data }">
        <span v-if="(data as PrintTemplateResponse).trigger">
          {{ t(`${p}.triggers.${(data as PrintTemplateResponse).trigger}`) }}
        </span>
        <Tag v-else :value="t(`${p}.manualOnly`)" severity="secondary" />
      </template>
    </Column>

    <Column :header="t(`${p}.columns.copiesRule`)" style="min-width: 10rem">
      <template #body="{ data }">
        {{ t(`${p}.copiesRules.${(data as PrintTemplateResponse).copies_rule}`) }}
      </template>
    </Column>

    <Column v-if="config.paper" :header="t(`${p}.columns.pageSize`)" style="width: 7rem">
      <template #body="{ data }">
        <span v-if="(data as PrintTemplateResponse).paper">{{
          t(`${p}.pageSizes.${(data as PrintTemplateResponse).paper}`)
        }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>

    <Column :header="t(`${p}.columns.printer`)" style="min-width: 10rem">
      <template #body="{ data }">
        <span v-if="(data as PrintTemplateResponse).printer_id">{{
          (data as PrintTemplateResponse).printer_name
        }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>

    <Column :header="t(`${p}.columns.created`)" style="width: 10rem">
      <template #body="{ data }">
        <UserDateCell
          :date="(data as PrintTemplateResponse).created"
          :user-id="(data as PrintTemplateResponse).creator_id"
          :name="(data as PrintTemplateResponse).creator_full_name"
        />
      </template>
    </Column>

    <Column :header="t(`${p}.columns.changed`)" style="width: 10rem">
      <template #body="{ data }">
        <UserDateCell
          :date="(data as PrintTemplateResponse).changed"
          :user-id="(data as PrintTemplateResponse).changed_by_id"
          :name="(data as PrintTemplateResponse).changed_by_full_name"
        />
      </template>
    </Column>

    <Column style="width: 100%" />

    <template #empty>
      <EmptyState :message="t(`${p}.table.empty`)" />
    </template>
  </DataTable>

  <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />
</template>

<style scoped lang="scss">
.text-success {
  color: var(--p-green-500);
}

.text-muted {
  color: var(--p-text-muted-color);
}
</style>
