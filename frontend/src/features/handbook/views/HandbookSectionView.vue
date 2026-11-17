<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { HANDBOOK_SECTIONS } from '../utils/handbookSections'
import { loadHandbookTree, type HandbookDoc } from '../utils/handbookContent'
import type { AppLocale } from '@/core/i18n'

const { t, locale } = useI18n()
const route = useRoute()

const section = computed(() =>
  typeof route.params.section === 'string' ? route.params.section : '',
)

const meta = computed(() => HANDBOOK_SECTIONS.find((entry) => entry.key === section.value))

const docs = ref<HandbookDoc[]>([])

watch(
  [section, locale],
  async ([current, currentLocale]) => {
    const tree = await loadHandbookTree(currentLocale as AppLocale)
    docs.value = tree.find((entry) => entry.section === current)?.docs ?? []
  },
  { immediate: true },
)
</script>

<template>
  <div class="handbook-section">
    <h1 v-if="meta" class="handbook-section-title">{{ t(meta.labelKey) }}</h1>

    <Message v-if="docs.length === 0" severity="secondary" :closable="false">
      {{ t('handbook.sectionEmpty') }}
    </Message>

    <div v-else class="handbook-section-list">
      <RouterLink
        v-for="doc in docs"
        :key="doc.slug"
        class="handbook-section-card"
        :to="{ name: 'HandbookPage', params: { section: doc.section, page: doc.page } }"
      >
        <span class="handbook-section-card-title">{{ doc.frontmatter.title }}</span>
        <span v-if="doc.frontmatter.summary" class="handbook-section-card-summary">
          {{ doc.frontmatter.summary }}
        </span>
      </RouterLink>
    </div>
  </div>
</template>

<style scoped lang="scss">
// Width and outer padding come from .handbook-page-frame in the layout, so
// every handbook route lines up.
.handbook-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.handbook-section-title {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: 600;
}

.handbook-section-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.handbook-section-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-4) var(--space-4);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  text-decoration: none;
  color: inherit;
}

.handbook-section-card:hover {
  border-color: var(--p-primary-color);
}

.handbook-section-card-title {
  font-weight: 600;
}

.handbook-section-card-summary {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
