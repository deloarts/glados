<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, provide, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODate } from '@/core/utils/dates'
import { helpContextKey, type HelpContext } from '@/shared/help'

import { useHandbookOutlineSink } from '../utils/handbookOutline'
import type { HandbookDoc } from '../utils/handbookContent'

const props = defineProps<{
  doc: HandbookDoc | null
  loading?: boolean
  missing?: boolean
  // Passed down to the components a doc embeds, so the same prose can react to
  // where it is being read from. See useHelpContext() in @/shared/help.
  context?: HelpContext
}>()

const { t } = useI18n()

provide(
  helpContextKey,
  computed(() => props.context ?? {}),
)

// The headings only exist once the doc's chunk has rendered, so they are read
// back off the DOM rather than parsed out of the markdown. Null when nothing
// is collecting them, which is the case in the drawer.
const prose = ref<HTMLElement | null>(null)
const outline = useHandbookOutlineSink()

if (outline) {
  watch(
    () => props.doc,
    async (doc) => {
      if (!doc) {
        outline.value = []
        return
      }
      await nextTick()
      outline.value = [...(prose.value?.querySelectorAll('h2[id], h3[id]') ?? [])].map(
        (heading) => ({
          id: heading.id,
          text: heading.textContent?.trim() ?? '',
          level: Number(heading.tagName.slice(1)),
        }),
      )
    },
    { immediate: true },
  )

  // Leaving a doc must not leave its headings listed beside the next one.
  onBeforeUnmount(() => {
    outline.value = []
  })
}
</script>

<template>
  <div class="handbook-content">
    <div v-if="loading" class="handbook-skeleton">
      <Skeleton v-for="line in 6" :key="line" height="1rem" class="handbook-skeleton-line" />
    </div>

    <Message v-else-if="missing || !doc" severity="warn" :closable="false">
      {{ t('handbook.missing') }}
    </Message>

    <template v-else>
      <Message v-if="!doc.translated" severity="secondary" :closable="false">
        {{ t('handbook.untranslated') }}
      </Message>

      <article ref="prose" class="handbook-prose">
        <component :is="doc.component" />
      </article>

      <p v-if="doc.frontmatter.lastVerified" class="handbook-verified">
        {{ t('handbook.lastVerified', { date: formatISODate(doc.frontmatter.lastVerified) }) }}
      </p>
    </template>
  </div>
</template>

<style scoped lang="scss">
.handbook-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.handbook-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.handbook-skeleton-line:nth-child(3n) {
  width: 70%;
}

// The markdown compiles to its own component, so its elements never carry this
// component's scope attribute, and every prose rule has to reach through :deep().
.handbook-prose {
  line-height: 1.55;
  color: var(--p-text-color);
}

// One descending step per level. h3 has to stay clearly below h2 but at or
// above body text: a sub-heading smaller than the paragraph under it reads as
// a caption, not a heading.
.handbook-prose :deep(h1) {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-xl);
  font-weight: 600;
}

.handbook-prose :deep(h2) {
  margin: var(--space-5) 0 var(--space-2);
  font-size: var(--font-size-lg);
  font-weight: 600;
  scroll-margin-top: 1rem;
}

.handbook-prose :deep(h3) {
  margin: var(--space-4) 0 var(--space-1);
  font-size: var(--font-size-md);
  font-weight: 600;
  // Also an outline target, so it needs the same offset h2 gets.
  scroll-margin-top: 1rem;
}

// Only the gap above the first heading is wrong: it would push the doc off
// the top of its own container.
.handbook-prose :deep(h1:first-child),
.handbook-prose :deep(h2:first-child),
.handbook-prose :deep(h3:first-child) {
  margin-top: 0;
}

.handbook-prose :deep(p) {
  margin: 0 0 var(--space-3);
}

.handbook-prose :deep(ul),
.handbook-prose :deep(ol) {
  margin: 0 0 var(--space-3);
  padding-left: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  color: var(--p-text-muted-color);
}

.handbook-prose :deep(strong) {
  font-weight: 600;
  color: var(--p-text-color);
}

.handbook-prose :deep(a) {
  color: var(--p-primary-color);
}

.handbook-prose :deep(code) {
  padding: var(--space-1) var(--space-1);
  border-radius: var(--p-content-border-radius);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  // Relative, so inline code tracks the surrounding prose size.
  font-size: 0.875em;
}

// Tables are the one thing a doc can produce that outgrows a narrow drawer.
.handbook-prose :deep(.handbook-table-wrap),
.handbook-prose :deep(table) {
  display: block;
  max-width: 100%;
  overflow-x: auto;
}

.handbook-prose :deep(table) {
  border-collapse: collapse;
  margin: 0 0 var(--space-3);
}

.handbook-prose :deep(th),
.handbook-prose :deep(td) {
  border: 1px solid var(--p-content-border-color);
  padding: var(--space-1) var(--space-2);
  text-align: left;
}

.handbook-prose :deep(blockquote) {
  margin: 0 0 var(--space-3);
  padding-left: var(--space-3);
  border-left: 3px solid var(--p-content-border-color);
  color: var(--p-text-muted-color);
}

/* stylelint-disable-next-line selector-disallowed-list -- the Messages come from the handbook page components, which the prose cannot class */
.handbook-prose :deep(.p-message) {
  margin: 0 0 var(--space-3);
}

.handbook-verified {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
