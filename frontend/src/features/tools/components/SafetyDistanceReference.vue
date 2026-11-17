<script setup lang="ts">
/**
 * The reference tables of the current mode under the calculation, with the
 * row and column the calculation used highlighted (see referenceTables.ts).
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { numberOptions } from '../utils/safetyDistance/format'
import { referenceTables } from '../utils/safetyDistance/referenceTables'
import type { SafetyDistanceInputs } from '../utils/safetyDistance/types'
import ToolReferenceTable from './ToolReferenceTable.vue'

const props = defineProps<{ inputs: SafetyDistanceInputs }>()

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()

const P = 'tools.safetyDistance.tables'

const tables = computed(() =>
  referenceTables(props.inputs, t, (value, digits) => formatNumber(value, numberOptions(digits, true))),
)
</script>

<template>
  <section v-if="tables.length > 0" class="sd-reference" data-testid="sd-reference">
    <h3 class="sd-reference-title">{{ t(`${P}.title`) }}</h3>
    <div class="sd-reference-tables">
      <div v-for="table in tables" :key="table.key" class="sd-reference-table" :class="`sd-reference-table--${table.key}`">
        <ToolReferenceTable
          :table-key="table.key"
          :title="table.title"
          :unit="table.unit"
          :row-header="table.rowHeader"
          :columns="table.columns"
          :rows="table.rows"
          :active-row="table.activeRow"
          :active-column="table.activeColumn"
        />
        <small class="sd-reference-note">{{ table.note }}</small>
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss">
.sd-reference {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.sd-reference-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.sd-reference-tables {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  gap: var(--space-3);
  align-items: start;
}

// Table 2 and the beam tables need the full width; the one-column tables
// share a row.
.sd-reference-table--reachOver,
.sd-reference-table--structure,
.sd-reference-table--structureLowRisk,
.sd-reference-table--beamHeights,
.sd-reference-table--beamHeightsIndustrial,
.sd-reference-table--hingeGap {
  grid-column: 1 / -1;
}

.sd-reference-table {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.sd-reference-note {
  color: var(--p-text-muted-color);
  line-height: 1.35;
}
</style>
