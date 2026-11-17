<script setup lang="ts">
// The demand status cell: a plain Tag pairing a translated label with a
// severity color. Each table resolves both from its own status/severity map
// (or, for bought items, a derived display status) and passes the result in,
// so this component carries no status enum or i18n key of its own.
defineProps<{
  label: string
  severity?: string
}>()
</script>

<template>
  <Tag :value="label" :severity="severity" />
</template>
