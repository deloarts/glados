<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { WidgetConfigOf, WidgetDataOf } from '../../types/infoscreenFeed'
import { joinParts } from '../../utils/infoscreenFormat'
import WidgetFrame from './WidgetFrame.vue'

// The active projects by number, with the product each one builds.
defineProps<{
  config: WidgetConfigOf<'projects'>
  data: WidgetDataOf<'projects'>
}>()

const { t } = useI18n()
</script>

<template>
  <WidgetFrame
    :title="config.title || t('infoscreenRuntime.widgets.projects.title')"
    :count="data.projects.length"
  >
    <ul v-if="data.projects.length > 0" class="project-rows">
      <li
        v-for="project in data.projects"
        :key="project.project_id"
        class="project-row"
        data-testid="project-row"
      >
        <span class="project-row-number">{{ project.project_number }}</span>
        <div class="project-row-main">
          <span v-if="project.description" class="project-row-name">{{ project.description }}</span>
          <span
            v-if="project.product_number || project.customer_name"
            class="project-row-detail"
          >
            {{
              joinParts(
                joinParts(project.product_number, project.product_designation),
                project.customer_name,
              )
            }}
          </span>
        </div>
      </li>
    </ul>
    <p v-else class="widget-empty">{{ t('infoscreenRuntime.widgets.projects.empty') }}</p>
  </WidgetFrame>
</template>

<style scoped lang="scss">
.project-rows {
  list-style: none;
  margin: 0;
  padding: 0;
}

.project-row {
  display: flex;
  align-items: baseline;
  gap: 0.8em;
  padding: 0.35em 0;
  border-bottom: 1px solid var(--p-content-border-color);
  min-width: 0;
}

.project-row-number {
  flex: 0 0 auto;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.project-row-main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.project-row-name,
.project-row-detail {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.project-row-detail {
  font-size: 0.8em;
  color: var(--p-text-muted-color);
}

.widget-empty {
  margin: 0;
  color: var(--p-text-muted-color);
}
</style>
