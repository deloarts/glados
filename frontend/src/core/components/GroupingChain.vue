<script setup lang="ts">
import { useI18n } from 'vue-i18n'

export interface GroupingChainItem {
  id: number
  label: string
  sublabel?: string
  // False for an item that can never share a group with a neighbour (a QA
  // inspection, which is always its own position, see the backend's
  // validate_position_grouping / validate_process_grouping). Such an item
  // is excluded from grouping entirely: it renders as a standalone chip
  // with no toggle on either side, since grouping a QA inspection with a
  // fabrication method is meaningless rather than merely disallowed.
  groupable?: boolean
  icon?: string
  // Tooltip for the chip, used to explain a standalone one.
  note?: string
  // Compact second line of extra detail rendered below the sublabel (e.g.
  // a process's setup/per-piece minutes), opt-in per caller, see
  // MadeItemProcessGrouping.vue's `showTimes` prop. Unset by every other
  // consumer (LotPositionGrouping, MadeItemProcessStagedGrouping), so
  // their chips are unaffected. Only read in `chipLayout: 'compact'` (the
  // default); see `metaLines` below for the `'regular'` layout's per-line
  // equivalent.
  meta?: string
  // One or more extra detail lines, each rendered as its own row: the
  // `chipLayout: 'regular'` equivalent of `meta` above (used instead of a
  // single "·"-joined string so each value gets its own line). Only read in
  // `'regular'` layout; a `'regular'` chip with `meta` set but no
  // `metaLines` falls back to rendering `meta` as a single line, so a
  // caller migrating from `meta` isn't forced to change both at once.
  metaLines?: string[]
}

// `chipLayout` is opt-in per caller, not per item: a whole chain renders one
// way or the other. `'compact'` (the default) is every existing consumer's
// current look (small font, `#n` below the name, one `meta` line), and is
// left completely untouched by the `'regular'` branch below (separate
// template branch, not shared markup with conditional classes) so
// LotPositionGrouping/MadeItemProcessStagedGrouping and the dialog's own
// MadeItemProcessGrouping instance render byte-for-byte as before.
// `'regular'` is the item-detail page's Processes card only: `#n` to the
// left of the name on one line, then one row per `metaLines` entry, all at
// the app's normal body font size
// (`--font-size-md`) instead of the chip's small default.
withDefaults(
  defineProps<{
    items: GroupingChainItem[]
    readonly?: boolean
    chipLayout?: 'compact' | 'regular'
  }>(),
  { chipLayout: 'compact' },
)

const { t } = useI18n()

const boundaries = defineModel<Set<number>>('boundaries', { required: true })

function isGroupable(item: GroupingChainItem): boolean {
  return item.groupable !== false
}

// A boundary exists between two adjacent items only when both may be
// grouped at all. The separation around a standalone item is a fact, not
// a choice, so it gets a plain marker instead of a disabled control, and the
// owning component still keeps that boundary in the model.
function hasToggle(items: GroupingChainItem[], index: number): boolean {
  return index > 0 && isGroupable(items[index - 1]!) && isGroupable(items[index]!)
}

function toggleBoundary(id: number): void {
  const next = new Set(boundaries.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  boundaries.value = next
}

// `'regular'` layout only. See `metaLines`'s doc comment above for the
// fallback-to-`meta` reasoning.
function metaLinesFor(item: GroupingChainItem): string[] {
  if (item.metaLines) return item.metaLines
  if (item.meta) return [item.meta]
  return []
}
</script>

<template>
  <div v-if="items.length" class="grouping-chain">
    <template v-for="(item, index) in items" :key="item.id">
      <button
        v-if="hasToggle(items, index)"
        type="button"
        class="boundary-toggle"
        :class="{ 'boundary-toggle--active': boundaries.has(item.id) }"
        :disabled="readonly"
        :aria-label="t('common.groupingChain.boundaryToggle')"
        @click="toggleBoundary(item.id)"
      >
        <i
          :class="boundaries.has(item.id) ? 'mdi mdi-arrow-split-vertical' : 'mdi mdi-link'"
          aria-hidden="true"
        />
      </button>
      <span v-else-if="index > 0" class="boundary-fixed" aria-hidden="true">
        <i class="mdi mdi-arrow-split-vertical" aria-hidden="true" />
      </span>
      <div
        class="step-chip"
        :class="{
          'step-chip--standalone': !isGroupable(item),
          'step-chip--regular': chipLayout === 'regular',
        }"
        v-tooltip.top="item.note"
      >
        <!-- 'regular': #n to the left of the name on one line, then one row
             per metaLines entry, kept as its own branch rather than
             conditional classes on shared markup so 'compact' (every other
             branch below) stays exactly what it was before this layout
             existed. -->
        <template v-if="chipLayout === 'regular'">
          <span class="step-chip-title">
            <span v-if="item.sublabel" class="step-chip-seq">{{ item.sublabel }}</span>
            <span class="step-chip-method">
              <i v-if="item.icon" :class="item.icon" aria-hidden="true" />
              {{ item.label }}
            </span>
          </span>
          <span
            v-for="(line, metaIndex) in metaLinesFor(item)"
            :key="metaIndex"
            class="step-chip-meta-line"
            >{{ line }}</span
          >
        </template>
        <template v-else>
          <span class="step-chip-method">
            <i v-if="item.icon" :class="item.icon" aria-hidden="true" />
            {{ item.label }}
          </span>
          <span v-if="item.sublabel" class="step-chip-seq">{{ item.sublabel }}</span>
          <span v-if="item.meta" class="step-chip-meta">{{ item.meta }}</span>
        </template>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.grouping-chain {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1);
}

.step-chip {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  background: var(--p-surface-50);
}

.p-dark .step-chip {
  background: var(--p-surface-800);
}

.step-chip--standalone {
  border-style: dashed;
  background: transparent;
}

.p-dark .step-chip--standalone {
  background: transparent;
}

.step-chip-method {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.step-chip-seq {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.step-chip-meta {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

// 'regular' layout: the item-detail page's Processes card only (see the
// `chipLayout` prop's doc comment). Overrides `.step-chip-method`/
// `.step-chip-seq` above via higher selector specificity (two classes vs.
// one), not `!important`, so it never affects a 'compact' chip.
.step-chip--regular {
  gap: var(--space-1);
}

.step-chip-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.step-chip--regular .step-chip-method {
  font-size: var(--font-size-md);
}

.step-chip--regular .step-chip-seq {
  font-size: var(--font-size-md);
  color: var(--p-text-muted-color);
}

.step-chip-meta-line {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.boundary-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  border: none;
  background: transparent;
  color: var(--p-text-muted-color);
  cursor: pointer;
  border-radius: 50%;

  &:hover:not(:disabled) {
    background: var(--p-surface-100);
  }

  &:disabled {
    cursor: default;
  }
}

.p-dark .boundary-toggle:hover:not(:disabled) {
  background: var(--p-surface-800);
}

.boundary-toggle--active {
  color: var(--p-primary-color);
}

.boundary-fixed {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  color: var(--p-text-muted-color);
  opacity: 0.5;
}
</style>
