<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import HandbookContent from '../components/HandbookContent.vue'
import { useHandbookDoc } from '../composables/useHandbookDoc'

const route = useRoute()

const slug = computed(() => {
  const { section, page } = route.params
  return typeof section === 'string' && typeof page === 'string' ? `${section}/${page}` : undefined
})

const { doc, loading, missing } = useHandbookDoc(slug)
</script>

<template>
  <div class="handbook-page">
    <h1 v-if="doc" class="handbook-page-title">{{ doc.frontmatter.title }}</h1>
    <p v-if="doc?.frontmatter.summary" class="handbook-page-summary">
      {{ doc.frontmatter.summary }}
    </p>

    <Divider v-if="doc" />

    <HandbookContent :doc="doc" :loading="loading" :missing="missing" />
  </div>
</template>

<style scoped lang="scss">
// Width and outer padding come from .handbook-page-frame in the layout, so
// every handbook route lines up.
.handbook-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.handbook-page-title {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: 600;
}

.handbook-page-summary {
  margin: 0;
  color: var(--p-text-muted-color);
}
</style>
