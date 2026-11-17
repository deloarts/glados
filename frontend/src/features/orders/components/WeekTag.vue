<script setup lang="ts">
import { computed } from 'vue'
import { useOrderFormatters } from '../composables/useOrderFormatters'

const props = defineProps<{
  date: string | null
}>()

const { weekTagFor } = useOrderFormatters()

const tag = computed(() => weekTagFor(props.date))
</script>

<template>
  <Tag v-if="tag" :value="tag.label" :severity="tag.severity" size="small" />
</template>
