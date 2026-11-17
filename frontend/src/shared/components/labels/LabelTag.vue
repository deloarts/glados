<script setup lang="ts">
// A colour-labelled catalogue record (article group, source item type,
// fabrication or inspection method, product family) as a coloured tag, or
// nothing without one. The name may be a language map, which is shown in the
// current UI language.
import { computed } from 'vue'

import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import type { LocalizedText } from '@/shared/utils/localizedText'

const props = defineProps<{
  label:
    | { name: LocalizedText | string; label_color: string; label_font_color: string }
    | null
    | undefined
}>()

const { localize } = useLocalizedText()

const text = computed(() => (props.label ? localize(props.label.name) : ''))
</script>

<template>
  <Tag
    v-if="label"
    :value="text"
    :style="{ color: label.label_font_color, backgroundColor: label.label_color }"
  />
</template>
