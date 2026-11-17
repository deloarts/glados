<script setup lang="ts">
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import ChecklistsControls from '../components/ChecklistsControls.vue'
import ChecklistsTable from '../components/ChecklistsTable.vue'
import ChecklistsViews from '../components/ChecklistsViews.vue'

/**
 * Every checklist the user can see: their own, and those kept with a
 * project or product. Laid out like the catalogue: the controls bar with
 * New Checklist, the views bar, and the table with its filter row and pages.
 */
</script>

<template>
  <PageLayout>
    <template #controls>
      <ChecklistsControls />
    </template>
    <template #views>
      <ChecklistsViews context="page" show-owner />
    </template>
    <ChecklistsTable context="page" />
  </PageLayout>
</template>
