<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { WidgetConfigOf, WidgetDataOf } from '../../types/infoscreenFeed'
import { joinParts } from '../../utils/infoscreenFormat'
import WidgetFrame from './WidgetFrame.vue'

// The active products (the machines being built), by number, each with its
// active projects when the screen asks for them.
defineProps<{
  config: WidgetConfigOf<'products'>
  data: WidgetDataOf<'products'>
}>()

const { t } = useI18n()
</script>

<template>
  <WidgetFrame
    :title="config.title || t('infoscreenRuntime.widgets.products.title')"
    :count="data.products.length"
  >
    <ul v-if="data.products.length > 0" class="product-rows">
      <li
        v-for="product in data.products"
        :key="product.product_id"
        class="product-row"
        data-testid="product-row"
      >
        <div class="product-row-head">
          <span class="product-row-number">{{ product.product_number }}</span>
          <span class="product-row-name">
            {{ product.designation ?? product.description }}
          </span>
        </div>
        <span
          v-if="product.machine_type || product.customer_name"
          class="product-row-detail"
        >
          {{ joinParts(product.machine_type, product.customer_name) }}
        </span>
        <ul v-if="config.show_projects && product.projects.length > 0" class="product-projects">
          <li
            v-for="project in product.projects"
            :key="project.project_id"
            class="product-project"
            data-testid="product-project"
          >
            <span class="product-project-number">{{ project.project_number }}</span>
            <span v-if="project.description" class="product-row-detail">
              {{ project.description }}
            </span>
          </li>
        </ul>
      </li>
    </ul>
    <p v-else class="widget-empty">{{ t('infoscreenRuntime.widgets.products.empty') }}</p>
  </WidgetFrame>
</template>

<style scoped lang="scss">
.product-rows {
  list-style: none;
  margin: 0;
  padding: 0;
}

.product-row {
  display: flex;
  flex-direction: column;
  gap: 0.1em;
  padding: 0.35em 0;
  border-bottom: 1px solid var(--p-content-border-color);
  min-width: 0;
}

.product-row-head {
  display: flex;
  align-items: baseline;
  gap: 0.6em;
  min-width: 0;
}

.product-row-number,
.product-project-number {
  flex: 0 0 auto;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.product-row-name {
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.product-row-detail {
  font-size: 0.8em;
  color: var(--p-text-muted-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.product-projects {
  list-style: none;
  margin: 0.15em 0 0;
  padding: 0 0 0 0.8em;
  border-left: 2px solid var(--p-content-border-color);
}

.product-project {
  display: flex;
  align-items: baseline;
  gap: 0.5em;
  min-width: 0;
  font-size: 0.9em;
}

.widget-empty {
  margin: 0;
  color: var(--p-text-muted-color);
}
</style>
