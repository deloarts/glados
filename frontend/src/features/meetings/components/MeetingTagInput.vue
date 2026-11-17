<script setup lang="ts">
import { onMounted, ref, useTemplateRef } from 'vue'
import type { AutoCompleteCompleteEvent } from 'openvue/autocomplete'

import { getMeetingTagSuggestions } from '../api/meetingsApi'
import { normaliseTags, tagOptions } from '../utils/meetingTags'

/**
 * The free-text tags of a meeting as chips. Typing offers the tags other
 * meetings carry, most used first; Enter takes the highlighted option,
 * which is the typed text unless an arrow key moved on to a tag in use, and
 * a comma takes the typed text as it is. `commitPending` takes text typed
 * but not confirmed yet, so a save does not lose it.
 */
const props = defineProps<{
  inputId?: string
  invalid?: boolean
  placeholder?: string
}>()

const model = defineModel<string[]>({ default: () => [] })

const root = useTemplateRef<{ $el: HTMLElement }>('root')
const known = ref<string[]>([])
const options = ref<string[]>([])

onMounted(async () => {
  try {
    const response = await getMeetingTagSuggestions({ limit: 100 })
    known.value = response.suggestions.map((suggestion) => suggestion.name)
  } catch {
    // The suggestions only help typing; any new text is a valid tag.
    known.value = []
  }
})

function onComplete(event: AutoCompleteCompleteEvent): void {
  options.value = tagOptions(known.value, event.query, model.value)
}

function onUpdate(value: unknown): void {
  model.value = normaliseTags(Array.isArray(value) ? value.map(String) : [])
}

/** Adds the text in the input as a tag, in the spelling of a tag in use. */
function commit(input: HTMLInputElement): void {
  const typed = tagOptions(known.value, input.value, model.value)[0]
  if (input.value.trim() && typed) model.value = normaliseTags([...model.value, typed])
  input.value = ''
  // An empty input closes the options the typed text opened.
  input.dispatchEvent(new Event('input'))
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key !== ',') return
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
    :suggestions="options"
    :invalid="props.invalid"
    :placeholder="props.placeholder"
    :delay="0"
    :show-empty-message="false"
    multiple
    auto-option-focus
    fluid
    data-testid="meeting-tag-input"
    @complete="onComplete"
    @update:model-value="onUpdate"
    @keydown="onKeydown"
  />
</template>
