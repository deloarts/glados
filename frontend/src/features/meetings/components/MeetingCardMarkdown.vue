<script setup lang="ts">
import { computed } from 'vue'

import { useUsersStore } from '@/core/stores/usersStore'
import { renderCardMarkdown } from '../utils/cardMarkdownRender'

/**
 * The reading view of a card body: the Markdown rendered and sanitised,
 * mentions with the user's current name and the card's images once they
 * have loaded.
 */
const props = defineProps<{
  body: string
  imageUrl?: (fileId: number) => string | undefined
  /** Bumped whenever another image finished loading. */
  imageVersion?: number
}>()

const usersStore = useUsersStore()

const html = computed(() => {
  void props.imageVersion
  return renderCardMarkdown(props.body, {
    userName: (id) => usersStore.users.find((user) => user.id === id)?.full_name,
    imageUrl: props.imageUrl,
  })
})
</script>

<template>
  <div class="card-markdown" data-testid="meeting-card-body" v-html="html" />
</template>

<style scoped lang="scss">
.card-markdown {
  overflow-wrap: anywhere;

  :deep(p) {
    margin: 0 0 var(--space-2);
  }

  :deep(h3) {
    margin: var(--space-2) 0;
    font-size: var(--font-size-md);
  }

  :deep(ul),
  :deep(ol) {
    margin: 0 0 var(--space-2);
    padding-left: var(--space-5);
  }

  :deep(> :last-child) {
    margin-bottom: 0;
  }

  :deep(a) {
    color: var(--p-primary-color);
  }

  :deep(.card-mention) {
    padding: 0 var(--space-1);
    border-radius: var(--p-border-radius-sm);
    background: var(--p-highlight-background);
    color: var(--p-highlight-color);
    white-space: nowrap;
  }

  :deep(.card-image) {
    max-width: 100%;
    max-height: 20rem;
    border-radius: var(--p-border-radius-sm);
  }
}
</style>
