<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import HelpDrawer from './HelpDrawer.vue'
import { useHelp, type HelpContext } from './useHelp'

const props = withDefaults(
  defineProps<{
    /**
     * Doc to open. Defaults to the current route's `handbook` meta, and
     * failing that to the route's own path, see `slug` below.
     */
    slug?: string
    anchor?: string
    context?: HelpContext
    label?: string
    severity?: string
    // Pass-throughs so the button can match whatever toolbar or panel header
    // it is dropped into, rather than every host restyling it. A dialog
    // header passes the plain help icon, the shape of the explain buttons
    // next to a dialog's close icon.
    size?: string
    rounded?: boolean
    icon?: string
  }>(),
  { severity: 'secondary', icon: 'mdi mdi-help-circle-outline' },
)

const { t } = useI18n()
const route = useRoute()
const help = useHelp()

// Slugs are <section>/<page>, the shape of a route path, so the button falls
// back to its route's path and appears as soon as the .md file exists. An
// explicit slug wins for buttons that explain a dialog or panel. The route
// is read defensively, since a router may not be installed.
const slug = computed(() => {
  if (props.slug) return props.slug
  if (!route) return undefined
  const declared = route.meta.handbook as string | undefined
  if (declared) return declared
  return route.path.replace(/^\/+/, '').split('/').slice(0, 2).join('/')
})

// A page without a doc renders nothing, so no dead control shows.
const available = computed(() => help.has(slug.value))

const open = ref(false)
</script>

<template>
  <template v-if="available">
    <Button
      :label="label"
      :icon="icon"
      :severity="severity"
      :size="size"
      :rounded="rounded"
      text
      v-tooltip.top="t('handbook.tooltip')"
      :aria-label="t('handbook.tooltip')"
      @click="open = true"
    />
    <HelpDrawer v-model:visible="open" :slug="slug" :anchor="anchor" :context="context" />
  </template>
</template>
