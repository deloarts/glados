<script setup lang="ts">
import { useHelp, type HelpContext } from './useHelp'

defineProps<{
  /** Doc to show. Defaults to whatever the current route declares. */
  slug?: string
  /** Heading id to scroll to, e.g. the section describing the clicked action. */
  anchor?: string
  context?: HelpContext
}>()

const visible = defineModel<boolean>('visible', { default: false })

const help = useHelp()
</script>

<template>
  <component
    :is="help.drawer"
    v-model:visible="visible"
    :slug="slug"
    :anchor="anchor"
    :context="context"
  />
</template>
