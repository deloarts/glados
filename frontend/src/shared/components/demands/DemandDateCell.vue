<script setup lang="ts">
// A date cell that falls back to the host's configured empty placeholder,
// the `value ?? getEmptyPlaceholder()` pattern repeated across every demand
// table's desired-delivery column.
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

defineProps<{
  value: string | null | undefined
}>()
</script>

<template>{{ value ?? getEmptyPlaceholder() }}</template>
