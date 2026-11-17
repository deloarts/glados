<script setup lang="ts">
import { useId } from 'vue'

/**
 * Owns the label/control association a form would otherwise do by hand: the
 * `<label>` points at its control through `for`, and a required field gets a
 * `*` that screen readers skip plus an `aria-required` value for the control.
 *
 * The default slot exposes `id` and `inputId` (the same generated id under
 * both names) because OpenVue's own inputs are inconsistent about which
 * prop pairs a `<label for>` to their focusable element: `InputText`/
 * `Textarea` take `id`, while `Select`/`InputNumber`/`DatePicker` take
 * `inputId`. A Select's focusable element is a span that a label cannot
 * name, so the slot also exposes `labelId` for its `aria-labelledby`. It
 * also exposes `ariaRequired`, already reduced to the
 * `'true' | undefined` shape an `aria-required` binding wants. Composite
 * OpenVue controls (`Select`, `InputNumber`, `DatePicker`) render their
 * focusable element as a nested sub-component, so a plain
 * `aria-required="..."` attribute lands on their non-interactive outer
 * wrapper instead, so those call sites must route `ariaRequired` through the
 * control's `pt` option to reach the real element (see the forms that use
 * this wrapper for the exact shape per control).
 */
defineProps<{
  label: string
  required?: boolean
}>()

const id = useId()
</script>

<template>
  <label :id="`${id}-label`" :for="id">{{ label }}<span v-if="required" aria-hidden="true"> *</span></label>
  <slot :id="id" :input-id="id" :label-id="`${id}-label`" :aria-required="required ? 'true' : undefined" />
</template>
