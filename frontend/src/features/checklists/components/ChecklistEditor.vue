<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useResizablePanelWidth } from '@/shared/composables/useResizablePanelWidth'
import type { OwnerData } from '../composables/useOwnerData'
import type { ChecklistOwner } from '../types/checklist'
import { itemDomId, partTitleKey } from '../utils/definitions'
import { isProblem } from '../utils/evaluation'
import type { HeaderTextField } from '../utils/state'
import { checklistResults } from '../utils/summary'
import { VERIFICATION_METHODS } from '../utils/types'
import type {
  Answer,
  ChecklistDefinition,
  ChecklistItem,
  ChecklistPart,
  ChecklistSection as Section,
  ChecklistState,
} from '../utils/types'
import ChecklistHeaderForm from './ChecklistHeaderForm.vue'
import ChecklistSection from './ChecklistSection.vue'
import type { ChecklistFilter } from './ChecklistSection.vue'
import ChecklistSummaryCard from './ChecklistSummaryCard.vue'
import PanelResizeHandle from '@/shared/components/layout/PanelResizeHandle.vue'

/**
 * One checklist on screen: its header, the parts with their sections and
 * items, and the result card. The state belongs to the caller; every edit
 * comes back as an event. With `changedIds` the items changed since the
 * revision before are marked and can be filtered on.
 */

const props = defineProps<{
  definition: ChecklistDefinition
  state: ChecklistState
  owner: ChecklistOwner
  ownerFields: OwnerData
  readOnly?: boolean
  releaseRequired: boolean
  releasedBy: string | null
  changedIds?: ReadonlySet<string> | null
}>()

const emit = defineEmits<{
  answer: [id: string, value: Answer | null]
  remark: [id: string, value: string]
  header: [field: HeaderTextField, value: string]
}>()

const { t } = useI18n()

const results = computed(() => checklistResults(props.definition, props.state))
const hasChanges = computed(() => (props.changedIds?.size ?? 0) > 0)

const filterOptions = computed(() => {
  const filters: ChecklistFilter[] = ['all', 'unanswered', 'problems']
  if (hasChanges.value) filters.push('changes')
  return filters.map((value) => ({ value, label: t(`checklists.filters.${value}`) }))
})

// ── Sections and filters ──────────────────────────────────────────────────

const filter = ref<ChecklistFilter>('all')
const expanded = reactive<Record<string, boolean>>({})

const isExpanded = (section: Section) => expanded[section.key] === true

function toggleSection(section: Section) {
  expanded[section.key] = !isExpanded(section)
}

function setAllExpanded(open: boolean) {
  for (const section of props.definition.sections) expanded[section.key] = open
}

function matches(item: ChecklistItem): boolean {
  const answer = props.state.answers[item.id]
  if (filter.value === 'unanswered') return answer === undefined
  if (filter.value === 'problems') return isProblem(answer)
  if (filter.value === 'changes') return props.changedIds?.has(item.id) === true
  return true
}

const activeFilter = computed<ChecklistFilter>(() => filter.value)
const sectionVisible = (section: Section) => activeFilter.value === 'all' || section.items.some(matches)
const partVisible = (part: ChecklistPart) => part.sections.some(sectionVisible)
const anyVisible = computed(() => props.definition.sections.some(sectionVisible))

// Choosing a filter opens every section that has matching items, so the
// filtered list can be worked through without opening sections one by one.
watch(filter, (next) => {
  if (next === 'all') return
  for (const section of props.definition.sections) {
    if (section.items.some(matches)) expanded[section.key] = true
  }
})

// A list without changes has no changes filter to stay on.
watch(hasChanges, (has) => {
  if (!has && filter.value === 'changes') filter.value = 'all'
})

// The left column with result, checklist data and methods; dragging the
// handle between the columns resizes it, and the width is remembered.
const {
  width: sideWidth,
  isResizing,
  min: sideMin,
  max: sideMax,
  onResizeStart,
  onResizeKey,
} = useResizablePanelWidth({
  defaultWidth: 480,
  min: 320,
  max: () => window.innerWidth * 0.6,
  storageKey: 'glados.checklists.sidePanelWidth',
})

async function focusItem(id: string) {
  const item = props.definition.itemById.get(id)
  if (!item) return
  if (!matches(item)) filter.value = 'all'
  expanded[item.sectionKey] = true
  await nextTick()
  document.getElementById(itemDomId(props.definition.type, item))?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
}
</script>

<template>
  <div class="cl" :class="{ 'cl--resizing': isResizing }">
    <div class="cl-side" :style="{ width: `${sideWidth}px` }" data-testid="cl-side">
      <ChecklistSummaryCard
        :definition="definition"
        :counts="results.counts"
        :completion="results.completion"
        :verdict="results.verdict"
        :problems="results.problems"
        @select="focusItem"
      />

      <ChecklistHeaderForm
        :header="state.header"
        :owner="owner"
        :owner-fields="ownerFields"
        :verdict="results.verdict"
        :read-only="readOnly"
        :release-required="releaseRequired"
        :released-by="releasedBy"
        @update="(field, value) => emit('header', field, value)"
      />

      <section v-if="definition.type === 'robotics'" class="cl-panel cl-legend" data-testid="cl-methods-legend">
        <h3 class="cl-legend-title">{{ t('checklists.methodsLegend') }}</h3>
        <dl class="cl-legend-list">
          <div v-for="method in VERIFICATION_METHODS" :key="method" class="cl-legend-entry">
            <dt>{{ method }}</dt>
            <dd>{{ t(`checklists.methods.${method}`) }}</dd>
          </div>
        </dl>
      </section>
    </div>

    <PanelResizeHandle class="cl-resize" data-testid="cl-resize" :width="sideWidth" :min="sideMin" :max="sideMax" @start="onResizeStart" @key="onResizeKey" />

    <section class="cl-panel cl-list" data-testid="cl-list">
      <div class="cl-controls">
        <SelectButton
          v-model="filter"
          :options="filterOptions"
          option-value="value"
          option-label="label"
          :allow-empty="false"
          :aria-label="t('checklists.filters.label')"
          data-testid="cl-filter"
        />
        <span class="cl-controls-spacer" />
        <Button
          :label="t('checklists.expandAll')"
          icon="mdi mdi-unfold-more-horizontal"
          severity="secondary"
          size="small"
          text
          data-testid="cl-expand-all"
          @click="setAllExpanded(true)"
        />
        <Button
          :label="t('checklists.collapseAll')"
          icon="mdi mdi-unfold-less-horizontal"
          severity="secondary"
          size="small"
          text
          data-testid="cl-collapse-all"
          @click="setAllExpanded(false)"
        />
      </div>

      <div class="cl-parts">
        <section v-for="part in definition.parts" v-show="partVisible(part)" :key="part.key" class="cl-part">
          <h3 class="cl-part-title">{{ part.number }} {{ t(partTitleKey(definition.type, part.key)) }}</h3>
          <ChecklistSection
            v-for="section in part.sections"
            v-show="sectionVisible(section)"
            :key="section.key"
            :definition="definition"
            :section="section"
            :answers="state.answers"
            :remarks="state.remarks"
            :legal-basis="ownerFields.legalBasis"
            :expanded="isExpanded(section)"
            :filter="activeFilter"
            :read-only="readOnly"
            :changed-ids="changedIds"
            @toggle="toggleSection(section)"
            @answer="(id, value) => emit('answer', id, value)"
            @remark="(id, value) => emit('remark', id, value)"
          />
        </section>
        <p v-if="!anyVisible" class="cl-empty" data-testid="cl-no-matches">
          {{ t('checklists.noMatches') }}
        </p>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
// Result, checklist data and the method legend run down a narrow column on
// the left, which scrolls on its own when it is taller than the screen; the
// checklist card fills the rest and its items always scroll inside it, so
// the page itself never scrolls. On a narrow screen everything stacks in
// one scrolling column.
.cl {
  height: 100%;
  min-height: 0;
  display: flex;
  align-items: stretch;

  &--resizing {
    user-select: none;
    cursor: ew-resize;
  }
}

.cl-side {
  flex: 0 0 auto;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.cl-list {
  flex: 1 1 40rem;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.cl-parts {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

// The handle between the columns, as the other resizable panels draw it.
.cl-resize {
  flex-shrink: 0;
  width: 8px;
  cursor: ew-resize;
  display: flex;
  justify-content: center;
  padding: var(--space-4) 0;

  &::after {
    content: '';
    display: block;
    height: 100%;
    width: 2px;
    border-radius: 1px;
    background: var(--p-content-border-color);
    transition: background 0.15s;
  }

  &:hover::after,
  &:active::after {
    background: var(--p-primary-color);
  }
}

@media (max-width: $bp-lg) {
  .cl {
    flex-direction: column;
    gap: var(--space-2);
    overflow-y: auto;
  }

  .cl-side {
    width: auto !important;
  }

  .cl-resize {
    display: none;
  }

  .cl-side,
  .cl-list,
  .cl-parts {
    flex: 0 0 auto;
    overflow-y: visible;
  }
}

.cl-panel {
  padding: var(--space-3) var(--space-4);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.cl-legend-title {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.cl-legend-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr));
  gap: var(--space-1) var(--space-4);
  margin: 0;
  font-size: var(--font-size-sm);
}

.cl-legend-entry {
  display: flex;
  gap: var(--space-2);

  dt {
    min-width: 1rem;
    font-weight: 600;
  }

  dd {
    margin: 0;
    color: var(--p-text-muted-color);
  }
}

.cl-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.cl-controls-spacer {
  flex: 1;
}

.cl-parts {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.cl-part {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.cl-part-title {
  margin: var(--space-2) 0 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.cl-empty {
  margin: 0;
  padding: var(--space-4);
  text-align: center;
  color: var(--p-text-muted-color);
}
</style>
