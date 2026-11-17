<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { ProductRenumberImpact } from '../api/getRenumberImpact'

/**
 * Asks before a product's number changes and lists what that affects:
 * device names (and with them CAD file names), released documents and
 * exported reports that keep the old number, and external systems that
 * look the product up by number. Sections with nothing affected are left
 * out; the external systems note is always shown.
 */
defineProps<{
  impact: ProductRenumberImpact | null
  oldNumber: string
  newNumber: string
}>()

const emit = defineEmits<{ confirm: []; cancel: [] }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()

// The answer is emitted before closing, since closing also emits `cancel`
// through the dialog's hide event and the first answer counts.
function cancel(): void {
  emit('cancel')
  visible.value = false
}

function confirm(): void {
  emit('confirm')
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('resources.products.renumber.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
    :pt="{ content: { 'data-testid': 'product-renumber-dialog' } }"
    @hide="emit('cancel')"
  >
    <div v-if="impact" class="renumber">
      <p>
        {{ t('resources.products.renumber.intro', { old: oldNumber, new: newNumber }) }}
      </p>

      <section v-if="impact.device_count > 0" data-testid="renumber-devices">
        <h4>
          <i class="mdi mdi-engine-outline" aria-hidden="true" />
          {{ t('resources.products.renumber.devices', { count: impact.device_count }) }}
        </h4>
        <ul class="examples">
          <li v-for="example in impact.device_examples" :key="example.old_name">
            <code>{{ example.old_name }}</code>
            <i class="mdi mdi-arrow-right" aria-hidden="true" />
            <code>{{ example.new_name }}</code>
          </li>
          <li v-if="impact.device_count > impact.device_examples.length" class="muted">
            {{
              t('resources.products.renumber.more', {
                count: impact.device_count - impact.device_examples.length,
              })
            }}
          </li>
        </ul>
        <p class="muted">{{ t('resources.products.renumber.cadFiles') }}</p>
      </section>

      <section
        v-if="impact.released_document_count > 0 || impact.export_count > 0"
        data-testid="renumber-documents"
      >
        <h4>
          <i class="mdi mdi-file-certificate-outline" aria-hidden="true" />
          {{ t('resources.products.renumber.documentsTitle') }}
        </h4>
        <p>
          {{
            t('resources.products.renumber.documents', {
              documents: impact.released_document_count,
              exports: impact.export_count,
            })
          }}
        </p>
      </section>

      <section data-testid="renumber-external">
        <h4>
          <i class="mdi mdi-api" aria-hidden="true" />
          {{ t('resources.products.renumber.externalTitle') }}
        </h4>
        <p>{{ t('resources.products.renumber.external', { old: oldNumber }) }}</p>
      </section>
    </div>

    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="cancel" />
      <Button
        :label="t('resources.products.renumber.confirm')"
        severity="warn"
        data-testid="renumber-confirm"
        @click="confirm"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.renumber {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);

  p {
    margin: 0;
  }

  h4 {
    margin: 0 0 var(--space-1);
    font-size: var(--font-size-md);
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }
}

.examples {
  margin: 0 0 var(--space-1);
  padding-left: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);

  li {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
}

.muted {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}
</style>
