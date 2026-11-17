<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODate, formatISODateTime } from '@/core/utils/dates'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import type { SavedCalculation } from '../composables/useSavedCalculation'

/**
 * The identity strip of the tools page. For a saved calculation it reads
 * document number, revision, status, title, the project or product it
 * belongs to and its creator; otherwise it warns that the figures on screen
 * are not saved.
 */

const props = defineProps<{
  saved: SavedCalculation
  /** The tool's own one-line description of its current inputs, shown while nothing is saved. */
  description?: string
}>()

const { t } = useI18n()

const calc = computed(() => props.saved.calculation.value)

const association = computed(() => {
  const c = calc.value
  if (!c) return null
  if (c.project_id !== null) {
    return {
      icon: 'mdi mdi-folder-outline',
      label: c.project_number ?? '',
      link: `/workspace/projects/${c.project_id}`,
      tooltip: t('tools.calculations.owner.project'),
    }
  }
  if (c.product_id !== null) {
    return {
      icon: 'mdi mdi-package-variant-closed',
      label: c.product_number ?? '',
      link: `/workspace/products/${c.product_id}`,
      tooltip: t('tools.calculations.owner.product'),
    }
  }
  return {
    icon: 'mdi mdi-account-outline',
    label: t('tools.calculations.owner.personal'),
    link: null,
    tooltip: t('tools.calculations.info.personalTooltip'),
  }
})

const releasedTooltip = computed(() => {
  const c = calc.value
  if (!c?.released_at) return ''
  return t('tools.calculations.status.releasedBy', {
    name: c.released_by_full_name ?? '',
    date: formatISODateTime(c.released_at),
  })
})

const changedTooltip = computed(() => {
  const c = calc.value
  if (!c?.changed || c.changed === c.created) return ''
  return t('tools.calculations.info.changed', { date: formatISODateTime(c.changed) })
})
</script>

<template>
  <InfoBar>
    <template v-if="calc">
      <span class="info-title" data-testid="calc-number">{{ calc.document_number }}</span>
      <span class="info-sep" />
      <Tag
        v-tooltip.bottom="calc.revision_reason ?? ''"
        :value="t('documents.revision.tag', { revision: calc.revision })"
        severity="secondary"
        data-testid="calc-revision"
      />
      <span class="info-sep" />
      <Tag
        v-if="saved.released.value"
        v-tooltip.bottom="releasedTooltip"
        :value="t('tools.calculations.status.released')"
        severity="success"
        data-testid="calc-status-released"
      />
      <Tag v-else :value="t('tools.calculations.status.draft')" severity="secondary" />
      <Tag
        v-if="calc.invalid_at"
        :value="t('tools.calculations.status.invalid')"
        severity="danger"
        data-testid="calc-status-invalid"
      />
      <Tag
        v-if="saved.editing.value"
        :value="t('tools.calculations.status.editing')"
        severity="info"
        data-testid="calc-status-editing"
      />
      <Tag
        v-if="saved.dirty.value"
        :value="t('tools.calculations.status.unsaved')"
        severity="warn"
        data-testid="calc-status-unsaved"
      />
      <span class="info-sep" />
      <span class="info-muted" data-testid="calc-title-display">{{ calc.title }}</span>
      <span class="info-sep" />
      <span v-if="association" v-tooltip.bottom="association.tooltip" class="info-muted" data-testid="calc-association">
        <i :class="association.icon" aria-hidden="true" />
        <RouterLink v-if="association.link" :to="association.link" class="info-link">
          {{ association.label }}
        </RouterLink>
        <template v-else>{{ association.label }}</template>
      </span>
      <template v-if="calc.product_device_name">
        <span class="info-sep" />
        <span
          v-tooltip.bottom="t('tools.calculations.info.device')"
          class="info-muted"
          data-testid="calc-device"
        >
          <i class="mdi mdi-engine-outline" aria-hidden="true" />
          {{ calc.product_device_name }}
        </span>
      </template>
      <span class="info-sep" />
      <span v-tooltip.bottom="changedTooltip" class="info-muted" data-testid="calc-creator">
        {{
          t('tools.calculations.info.created', {
            name: calc.creator_full_name,
            date: formatISODate(calc.created),
          })
        }}
      </span>
    </template>
    <template v-else>
      <span class="info-not-saved" data-testid="calc-not-saved">
        <i class="mdi mdi-alert-outline" aria-hidden="true" />
        {{ t('tools.calculations.status.notSaved') }}
      </span>
      <template v-if="description">
        <span class="info-sep" />
        <span class="info-muted" data-testid="calc-description">{{ description }}</span>
      </template>
    </template>
  </InfoBar>
</template>

<style scoped lang="scss">
.info-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.info-muted {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}

.info-link {
  color: inherit;
}

.info-not-saved {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--p-orange-500);
}
</style>
