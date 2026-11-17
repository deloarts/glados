<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'
import { useAppToast } from '@/core/composables/useAppToast'
import { storeToRefs } from 'pinia'

import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { disableAllPrinters } from '@/features/printers'
import { usePrintTemplatesStore } from '../stores/printTemplatesStore'
import { PRINT_TEMPLATE_KINDS } from '../utils/printTemplateKinds'
import { extractApiError } from '@/core/utils/errors'

import type { PrintTemplateKind } from '../utils/printTemplateKinds'

const props = defineProps<{ kind: PrintTemplateKind }>()

const { t } = useI18n()
const confirm = useConfirm()
const toast = useAppToast()
const { hasPermission } = usePermissions()

const store = usePrintTemplatesStore()
const storeRefs = storeToRefs(store)

const config = computed(() => PRINT_TEMPLATE_KINDS[props.kind])
const p = computed(() => config.value.i18nPrefix)
const templates = computed(() => storeRefs[config.value.templatesKey].value)

const canWritePrinters = computed(() => hasPermission(Permission.WRITE_PRINTERS))
const canWriteTemplates = computed(() => hasPermission(Permission.WRITE_PRINTERS))

const disablingPrinters = ref(false)
const disablingAutoPrint = ref(false)

function onDisableAllPrinters(): void {
  async function onAccept(): Promise<void> {
    disablingPrinters.value = true
    try {
      const count = await disableAllPrinters()
      toast.success(
        t(`${p.value}.controls.disableAllPrinters`),
        t(`${p.value}.controls.disableAllPrintersDone`, { count }),
      )
    } catch (e) {
      toast.error(t(`${p.value}.errors.unknown`), extractApiError(e) ?? undefined)
    } finally {
      disablingPrinters.value = false
    }
  }

  confirm.require({
    message: t(`${p.value}.controls.disableAllPrintersConfirm`),
    header: t(`${p.value}.controls.disableAllPrinters`),
    icon: 'mdi mdi-printer-off',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t(`${p.value}.controls.disableAllPrinters`), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

function onDisableAutoPrint(): void {
  async function onAccept(): Promise<void> {
    disablingAutoPrint.value = true
    try {
      const armed = templates.value.filter((tpl) => tpl.auto_print)
      await Promise.all(armed.map((tpl) => store.update(tpl.classifier, { auto_print: false })))
      toast.success(
        t(`${p.value}.controls.disableAutoPrint`),
        t(`${p.value}.controls.disableAutoPrintDone`, { count: armed.length }),
      )
    } catch (e) {
      toast.error(t(`${p.value}.errors.unknown`), extractApiError(e) ?? undefined)
    } finally {
      disablingAutoPrint.value = false
    }
  }

  confirm.require({
    message: t(`${p.value}.controls.disableAutoPrintConfirm`),
    header: t(`${p.value}.controls.disableAutoPrint`),
    icon: 'mdi mdi-flash-off',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t(`${p.value}.controls.disableAutoPrint`), severity: 'danger' },
    accept: () => void onAccept(),
  })
}
</script>

<template>
  <!-- Rendered into ManagementCrudShell's #extra-controls slot in place of
       Create. The backend ensures one print-template row per classifier at
       startup, as an unconfigured slot, and rows are never created or
       deleted here. Editing and reset
       happen per row in the table, so these two bulk actions are the
       page's real actions. -->
  <Button
    :label="t(`${p}.controls.disableAllPrinters`)"
    icon="mdi mdi-printer-off"
    severity="contrast"
    text
    :loading="disablingPrinters"
    :disabled="!canWritePrinters"
    @click="onDisableAllPrinters"
  />
  <Button
    :label="t(`${p}.controls.disableAutoPrint`)"
    icon="mdi mdi-flash-off"
    severity="contrast"
    text
    :loading="disablingAutoPrint"
    :disabled="!canWriteTemplates"
    @click="onDisableAutoPrint"
  />
</template>
