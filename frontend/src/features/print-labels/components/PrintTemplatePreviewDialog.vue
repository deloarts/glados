<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { previewPrintTemplateImageUrl } from '../api/previewPrintTemplate'
import { downloadPrintTemplate } from '../api/downloadPrintTemplate'
import { PRINT_TEMPLATE_KINDS } from '../utils/printTemplateKinds'
import { extractApiError } from '@/core/utils/errors'

import type { PrintTemplateKind } from '../utils/printTemplateKinds'
import type { PrintTemplateResponse } from '../types/printTemplateResponse'

interface Props {
  kind: PrintTemplateKind
  template?: PrintTemplateResponse | null
}

const props = defineProps<Props>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const toast = useAppToast()

const config = computed(() => PRINT_TEMPLATE_KINDS[props.kind])
const p = computed(() => config.value.i18nPrefix)

const rootId = ref<number | null>(null)
const loading = ref(false)
const downloading = ref(false)
const errorMessage = ref<string | null>(null)
const imageUrl = ref<string | null>(null)
const warnings = ref<string[]>([])

function revoke(): void {
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  imageUrl.value = null
}

async function runPreview(): Promise<void> {
  if (!props.template || !rootId.value) return
  loading.value = true
  errorMessage.value = null
  try {
    const result = await previewPrintTemplateImageUrl(
      props.template.classifier,
      props.template.root_type,
      rootId.value,
    )
    revoke()
    imageUrl.value = result.url
    warnings.value = result.warnings
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t(`${p.value}.preview.errors.unknown`)
  } finally {
    loading.value = false
  }
}

async function runDownload(): Promise<void> {
  if (!props.template || !rootId.value) return
  downloading.value = true
  try {
    const result = await downloadPrintTemplate(
      props.template.classifier,
      props.template.root_type,
      rootId.value,
    )
    if (result.warnings.length) {
      toast.warn(
        t(`${p.value}.classifiers.${props.template.classifier}`),
        result.warnings.join(', '),
      )
    }
  } catch (e) {
    toast.error(t(`${p.value}.download.errors.unknown`), extractApiError(e) ?? undefined)
  } finally {
    downloading.value = false
  }
}

watch(visible, (isVisible) => {
  if (!isVisible) {
    revoke()
    return
  }
  rootId.value = null
  imageUrl.value = null
  errorMessage.value = null
  warnings.value = []
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t(`${p}.previewAction`)"
    :style="{ width: config.previewDialogWidth }"
  >
    <div class="preview-dialog">
      <div class="field">
        <label :for="`${config.idPrefix}d-id`">{{ t(`${p}.editor.preview.recordId`) }}</label>
        <div class="record-id-row">
          <InputNumber
            :id="`${config.idPrefix}d-id`"
            v-model="rootId"
            :min="1"
            :use-grouping="false"
            fluid
          />
          <Button
            icon="mdi mdi-eye-outline"
            :disabled="!rootId"
            :loading="loading"
            v-tooltip.top.focus="config.download ? t(`${p}.previewAction`) : undefined"
            :aria-label="t(`${p}.previewAction`)"
            @click="runPreview"
          />
          <Button
            v-if="config.download"
            icon="mdi mdi-download-outline"
            severity="secondary"
            :disabled="!rootId"
            :loading="downloading"
            v-tooltip.top.focus="t(`${p}.download.action`)"
            :aria-label="t(`${p}.download.action`)"
            @click="runDownload"
          />
        </div>
      </div>

      <Message v-if="errorMessage" severity="error">{{ errorMessage }}</Message>
      <img
        v-else-if="imageUrl"
        :src="imageUrl"
        :alt="t(`${p}.previewAction`)"
        class="preview-image"
      />
      <Message v-for="warning in warnings" :key="warning" severity="warn">{{ warning }}</Message>
    </div>
  </Dialog>
</template>

<style scoped lang="scss">
.preview-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.record-id-row {
  display: flex;
  gap: var(--space-2);
}

.preview-image {
  max-width: 100%;
  border: 1px solid var(--p-content-border-color);
  background: var(--paper);
}
</style>
