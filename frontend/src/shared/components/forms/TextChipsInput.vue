<script setup lang="ts">
import { useTemplateRef } from 'vue'

import { normaliseChips } from './textChips'

/**
 * A list of free-text values as chips, such as the supplier order numbers of
 * an order. Enter or a comma takes the typed text as a new chip, the chip's
 * remove icon drops one. Each value is trimmed, and a value typed again in
 * another case is kept once in its first spelling. `commitPending` takes
 * text typed but not confirmed yet, so a save does not lose it.
 */
const props = defineProps<{
  inputId?: string
  ariaLabel?: string
  placeholder?: string
  invalid?: boolean
  autofocus?: boolean
}>()

const model = defineModel<string[]>({ default: () => [] })

const root = useTemplateRef<{ $el: HTMLElement }>('root')

function onUpdate(value: unknown): void {
  model.value = normaliseChips(Array.isArray(value) ? value.map(String) : [])
}

/** Adds the text in the input as a chip and empties the input. */
function commit(input: HTMLInputElement): void {
  if (input.value.trim()) model.value = normaliseChips([...model.value, input.value])
  input.value = ''
  input.dispatchEvent(new Event('input'))
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key !== ',' && event.key !== 'Enter') return
  const input = event.target as HTMLInputElement | null
  if (!input || !('value' in input)) return
  event.preventDefault()
  event.stopPropagation()
  commit(input)
}

function commitPending(): void {
  const input = root.value?.$el.querySelector('input')
  if (input?.value.trim()) commit(input)
}

defineExpose({ commitPending })
</script>

<template>
  <!-- The keydown listener falls through to the root and hears the input's keys bubble up. -->
  <AutoComplete
    ref="root"
    :model-value="model"
    :input-id="props.inputId"
    :aria-label="props.ariaLabel"
    :placeholder="props.placeholder"
    :invalid="props.invalid"
    :autofocus="props.autofocus"
    :suggestions="[]"
    :typeahead="false"
    :show-empty-message="false"
    multiple
    fluid
    data-testid="text-chips-input"
    @update:model-value="onUpdate"
    @keydown="onKeydown"
  />
</template>
