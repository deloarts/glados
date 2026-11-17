<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import HandbookContent from './HandbookContent.vue'
import { useHandbookDoc } from '../composables/useHandbookDoc'
import type { HelpContext } from '@/shared/help'

const props = defineProps<{
  /** Doc to show. Defaults to whatever the current route declares. */
  slug?: string
  /** Heading id to scroll to, e.g. the section describing the clicked action. */
  anchor?: string
  context?: HelpContext
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const route = useRoute()

const slug = computed(() => props.slug ?? (route.meta.handbook as string | undefined))
const { doc, loading, missing } = useHandbookDoc(slug)

const body = ref<HTMLElement | null>(null)

// The anchor can only be resolved once the doc's chunk has arrived and been
// rendered, which is usually after the drawer itself opens, so this watches
// the doc rather than firing on open.
watch([visible, doc, () => props.anchor], async ([open, loaded, anchor]) => {
  if (!open || !loaded || !anchor) return
  await nextTick()
  // Attribute selector rather than `#id`, so an id needing escaping does not
  // throw, and it avoids CSS.escape, which jsdom does not provide.
  const target = body.value?.querySelector(`[id="${anchor.replace(/"/g, '\\"')}"]`)
  target?.scrollIntoView({ block: 'start' })
})
</script>

<template>
  <Drawer v-model:visible="visible" position="right" class="handbook-drawer sized-drawer">
    <template #header>
      <div class="handbook-drawer-heading">
        <i class="mdi mdi-book-open-variant" aria-hidden="true" />
        <span>{{ doc?.frontmatter.title ?? t('handbook.title') }}</span>
      </div>
    </template>

    <div ref="body" class="handbook-drawer-body">
      <HandbookContent :doc="doc" :loading="loading" :missing="missing" :context="context" />

      <template v-if="doc">
        <Divider />
        <RouterLink
          class="handbook-drawer-link"
          :to="{ name: 'HandbookPage', params: { section: doc.section, page: doc.page } }"
          @click="visible = false"
        >
          <i class="mdi mdi-open-in-new" aria-hidden="true" />
          {{ t('handbook.openFullPage') }}
        </RouterLink>
      </template>
    </div>
  </Drawer>
</template>

<style lang="scss">
// Unscoped, since OpenVue teleports the Drawer to <body>.
.handbook-drawer {
  --drawer-width: 34rem;
}

.handbook-drawer .handbook-drawer-heading {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-md);
  font-weight: 600;
}

.handbook-drawer .handbook-drawer-heading .mdi {
  font-size: var(--font-size-xl);
  color: var(--p-primary-color);
}

.handbook-drawer .handbook-drawer-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.handbook-drawer .handbook-drawer-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--p-primary-color);
  text-decoration: none;
}

.handbook-drawer .handbook-drawer-link:hover {
  text-decoration: underline;
}
</style>
