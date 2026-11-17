<script setup lang="ts">
// The demand quantity cell: a number followed by its unit. The caller
// resolves the unit label first (some tables format it, e.g. formatUnit,
// others pass the raw string), so this component only lays the two out.
defineProps<{
  quantity: number
  unit: string
}>()
</script>

<template>{{ quantity }} {{ unit }}</template>
