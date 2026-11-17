<script setup lang="ts">
// The fabrication-method capability picker of the supplier form. Loads its
// own options lazily.
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import { labelName } from '@/shared/utils/localizeLabel'

const modelValue = defineModel<number[]>({ required: true })

const { t } = useI18n()
const store = useFabricationMethodsStore()

onMounted(async () => {
  if (!store.items.length) await store.refresh()
})
</script>

<template>
  <div class="field field-wide">
    <label id="s-capabilities-label" for="s-capabilities">{{ t('resources.suppliers.fields.capabilities') }}</label>
    <MultiSelect
      id="s-capabilities"
      aria-labelledby="s-capabilities-label"
      v-model="modelValue"
      :options="store.items"
      :option-label="labelName"
      option-value="id"
      display="chip"
      :placeholder="t('resources.suppliers.fields.capabilitiesPlaceholder')"
      filter
      fluid
    />
  </div>
</template>

<style scoped lang="scss">
.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.field-wide {
  grid-column: 1 / -1;
}
</style>
