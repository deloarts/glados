<script setup lang="ts">
import { computed } from 'vue'

import CalculationsTable from './CalculationsTable.vue'

/**
 * The calculations of one project or product, for its Calculations tab:
 * the table of the Calculations page without filters, views or controls.
 * The page around it offers New Calculation. On a product the calculations
 * of its projects can be listed too.
 */

const props = defineProps<{
  projectId?: number
  productId?: number
  /** Also lists the calculations of the projects built on `productId`. */
  includeProductProjects?: boolean
}>()

const context = computed(() => (props.projectId !== undefined ? 'project' : 'product'))
</script>

<template>
  <CalculationsTable
    :context="context"
    :project-id="projectId"
    :product-id="productId"
    :include-product-projects="includeProductProjects"
  />
</template>
