<script setup lang="ts">
import { computed } from 'vue'

import ChecklistsTable from './ChecklistsTable.vue'

/**
 * The checklists of one project or product, for its Checklists tab: the
 * table of the Checklists page without filters, views or controls. The
 * page around it offers New Checklist. On a product the checklists of its
 * projects can be listed too.
 */

const props = defineProps<{
  projectId?: number
  productId?: number
  /** Also lists the checklists of the projects built on `productId`. */
  includeProductProjects?: boolean
}>()

const context = computed(() => (props.projectId !== undefined ? 'project' : 'product'))
</script>

<template>
  <ChecklistsTable
    :context="context"
    :project-id="projectId"
    :product-id="productId"
    :include-product-projects="includeProductProjects"
  />
</template>
