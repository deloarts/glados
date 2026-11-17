<script setup lang="ts">
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import CalculationsControls from '../components/CalculationsControls.vue'
import CalculationsTable from '../components/CalculationsTable.vue'
import CalculationsViews from '../components/CalculationsViews.vue'

/**
 * Every saved calculation the user can see: their own, and those kept with a
 * project or product. Laid out like the catalogue: the controls bar with New
 * Calculation, the views bar, and the table with its filter row and pages.
 */
</script>

<template>
  <PageLayout>
    <template #controls>
      <CalculationsControls />
    </template>
    <template #views>
      <CalculationsViews context="page" />
    </template>
    <CalculationsTable context="page" />
  </PageLayout>
</template>
