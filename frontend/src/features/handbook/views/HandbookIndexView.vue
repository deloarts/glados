<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { HANDBOOK_SECTIONS } from '../utils/handbookSections'
import { loadHandbookTree, type HandbookSectionDocs } from '../utils/handbookContent'
import type { AppLocale } from '@/core/i18n'

const { t, locale } = useI18n()

const sections = ref<HandbookSectionDocs[]>([])
const loading = ref(true)

watch(
  locale,
  async (current) => {
    loading.value = true
    sections.value = await loadHandbookTree(current as AppLocale)
    loading.value = false
  },
  { immediate: true },
)

// Every section, documented or not. Showing the gaps is the point: an empty
// handbook that lists only what exists looks broken, where one that shows the
// whole app with most of it still blank reads as a map of what is coming.
const tiles = computed(() =>
  HANDBOOK_SECTIONS.map((meta) => ({
    ...meta,
    label: t(meta.labelKey),
    docs: sections.value.find((entry) => entry.section === meta.key)?.docs ?? [],
  })),
)

const documentedCount = computed(() => tiles.value.filter((tile) => tile.docs.length > 0).length)
</script>

<template>
  <div class="handbook-index">
    <header class="handbook-index-header">
      <h1 class="handbook-index-title">{{ t('handbook.title') }}</h1>
      <p class="handbook-index-lead">{{ t('handbook.lead') }}</p>
      <p v-if="!loading" class="handbook-index-coverage">
        {{ t('handbook.coverage', { done: documentedCount, total: tiles.length }) }}
      </p>
    </header>

    <div class="handbook-index-grid">
      <article
        v-for="tile in tiles"
        :key="tile.key"
        class="handbook-index-tile"
        :class="{ 'handbook-index-tile-empty': !loading && tile.docs.length === 0 }"
      >
        <RouterLink
          class="handbook-index-tile-header"
          :to="{ name: 'HandbookSection', params: { section: tile.key } }"
        >
          <i :class="`mdi ${tile.icon}`" aria-hidden="true" />
          <span class="handbook-index-tile-name">{{ tile.label }}</span>
          <span v-if="tile.docs.length" class="handbook-index-tile-count">
            {{ tile.docs.length }}
          </span>
        </RouterLink>

        <div class="handbook-index-tile-body">
          <Skeleton v-if="loading" height="1rem" />

          <p v-else-if="tile.docs.length === 0" class="handbook-index-tile-hint">
            {{ t('handbook.sectionEmpty') }}
          </p>

          <RouterLink
            v-for="doc in tile.docs"
            :key="doc.slug"
            class="handbook-index-tile-link"
            :to="{ name: 'HandbookPage', params: { section: doc.section, page: doc.page } }"
          >
            {{ doc.frontmatter.title }}
          </RouterLink>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped lang="scss">
// Width and outer padding come from .handbook-page-frame in the layout, so
// every handbook route lines up.
.handbook-index {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.handbook-index-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.handbook-index-title {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: 600;
}

.handbook-index-lead {
  margin: 0;
  color: var(--p-text-muted-color);
}

.handbook-index-coverage {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.handbook-index-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
  gap: var(--space-3);
}

.handbook-index-tile {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

// Undocumented sections stay visible but recede, so the eye lands on what can
// actually be read right now.
.handbook-index-tile-empty {
  border-style: dashed;
  opacity: 0.65;
}

.handbook-index-tile-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: inherit;
  text-decoration: none;
}

.handbook-index-tile-header:hover .handbook-index-tile-name {
  color: var(--p-primary-color);
}

.handbook-index-tile-header .mdi {
  font-size: var(--font-size-lg);
  color: var(--p-primary-color);
}

.handbook-index-tile-empty .handbook-index-tile-header .mdi {
  color: var(--p-text-muted-color);
}

.handbook-index-tile-name {
  flex: 1;
  font-weight: 600;
}

.handbook-index-tile-count {
  min-width: 1.4rem;
  padding: 0 var(--space-1);
  border-radius: 999px;
  background: var(--p-content-hover-background);
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
  line-height: 1.4rem;
  text-align: center;
}

.handbook-index-tile-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.handbook-index-tile-link {
  padding: var(--space-1) 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
  text-decoration: none;
}

.handbook-index-tile-link:hover {
  color: var(--p-primary-color);
}

.handbook-index-tile-hint {
  margin: 0;
  padding: var(--space-1) 0;
  font-size: var(--font-size-sm);
  font-style: italic;
  color: var(--p-text-muted-color);
}
</style>
