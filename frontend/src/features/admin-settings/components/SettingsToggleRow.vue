<script setup lang="ts">
import { useId } from 'vue'

/**
 * One settings row with a toggle: the label, the switch tied to it through a
 * generated id, and an optional hint beside them, laid out by the shared
 * .field-row--toggle grid.
 */
defineProps<{
  label: string
  hint?: string
  disabled?: boolean
}>()

const model = defineModel<boolean>({ required: true })

const id = useId()
</script>

<template>
  <div class="field-row field-row--toggle">
    <label :for="id">{{ label }}</label>
    <ToggleSwitch v-model="model" :input-id="id" :disabled="disabled" />
    <small v-if="hint" class="hint">{{ hint }}</small>
  </div>
</template>
