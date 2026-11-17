<script setup lang="ts">
/**
 * A reference table of a tools tab: one labelled row per class or size, the
 * row and column that match the current input highlighted, their crossing
 * cell outlined. Gridlines and striped rows follow the user's table settings,
 * like the app's data tables. A long table scrolls inside the card under its
 * fixed header row, and with `scrollToActive` it scrolls itself to the
 * highlighted row. The optional `sketch` slot shows a drawing that explains
 * the column symbols next to it.
 */
import { storeToRefs } from 'pinia'
import { onMounted, useTemplateRef, watch } from 'vue'

import { useLayoutStore } from '@/core/stores/layoutStore'

export interface ToolReferenceRow {
  key: string
  label: string
  cells: string[]
}

const props = defineProps<{
  tableKey: string
  title: string
  unit: string
  /** Header of the first column, which labels the rows. */
  rowHeader: string
  columns: string[]
  rows: ToolReferenceRow[]
  /** Key of the row that matches the current input; it is highlighted. */
  activeRow: string | null
  /** Index of the column that matches the current input; it is highlighted. */
  activeColumn: number | null
  /**
   * Scrolls the table to the highlighted row when it mounts and whenever
   * `activeRow` changes, for tables long enough to hide it.
   */
  scrollToActive?: boolean
}>()

const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const scrollBox = useTemplateRef<HTMLElement>('scrollBox')

/**
 * Scrolls the table's own scroll box, never the page, so the highlighted row
 * shows below the sticky header. A row already in view stays where it is; one
 * out of view is brought to the middle so its neighbours show as well. Rows
 * and boxes without a layout, as in jsdom, measure as in view and are left
 * alone.
 */
function revealActiveRow(instant: boolean) {
  const box = scrollBox.value
  const row = box?.querySelector<HTMLElement>('tbody tr[aria-current="true"]')
  if (!box || !row) return
  const header = box.querySelector('thead')?.getBoundingClientRect().height ?? 0
  const boxTop = box.getBoundingClientRect().top + box.clientTop
  const viewTop = boxTop + header
  const viewBottom = boxTop + box.clientHeight
  const rowRect = row.getBoundingClientRect()
  if (rowRect.top >= viewTop && rowRect.bottom <= viewBottom) return

  const offset = (viewBottom - viewTop - rowRect.height) / 2
  const top = Math.max(0, Math.round(box.scrollTop + rowRect.top - viewTop - offset))
  // A new selection glides there through the box's scroll-behavior; a table
  // that has just appeared jumps, so it never animates in from the top.
  if (typeof box.scrollTo === 'function') box.scrollTo(instant ? { top, behavior: 'instant' } : { top })
  else box.scrollTop = top
}

onMounted(() => {
  if (props.scrollToActive) revealActiveRow(true)
})

watch(
  () => props.activeRow,
  () => {
    if (props.scrollToActive) revealActiveRow(false)
  },
  { flush: 'post' },
)
</script>

<template>
  <section class="gtt" :data-testid="`ref-table-${tableKey}`">
    <header class="gtt-header">
      <h4 class="gtt-title">{{ title }}</h4>
      <span class="gtt-unit">{{ unit }}</span>
    </header>
    <div class="gtt-body">
      <div v-if="$slots.sketch" class="gtt-sketch">
        <slot name="sketch" />
      </div>
      <div ref="scrollBox" class="gtt-scroll" :data-testid="`ref-scroll-${tableKey}`">
        <table
          class="gtt-table"
          :class="{ 'gtt-table--gridlines': isTableGridlinesEnabled, 'gtt-table--striped': isTableStripedEnabled }"
        >
          <thead>
            <tr>
              <th scope="col" class="gtt-class">{{ rowHeader }}</th>
              <th
                v-for="(column, index) in columns"
                :key="index"
                scope="col"
                :class="{ 'gtt-col--active': index === activeColumn }"
              >
                {{ column }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in rows"
              :key="row.key"
              :class="{ 'gtt-row--active': row.key === activeRow }"
              :aria-current="row.key === activeRow ? 'true' : undefined"
              :data-testid="row.key === activeRow ? `ref-row-${tableKey}` : undefined"
            >
              <th scope="row" class="gtt-class">{{ row.label }}</th>
              <td
                v-for="(cell, index) in row.cells"
                :key="index"
                :class="{
                  'gtt-col--active': index === activeColumn,
                  'gtt-hit': row.key === activeRow && index === activeColumn,
                }"
                :data-testid="row.key === activeRow && index === activeColumn ? `ref-hit-${tableKey}` : undefined"
              >
                {{ cell }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss">
.gtt {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.gtt-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.gtt-title {
  margin: 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.gtt-unit {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.gtt-body {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: var(--space-3);
}

.gtt-sketch {
  flex: 0 1 24rem;
  min-width: 14rem;
  display: flex;
  justify-content: center;
}

.gtt-scroll {
  flex: 1 1 28rem;
  min-width: 0;
  max-height: 24rem;
  overflow: auto;
  // Scrolling to a newly highlighted row animates, so the reader sees where
  // the table moved.
  scroll-behavior: smooth;
}

@media (prefers-reduced-motion: reduce) {
  .gtt-scroll {
    scroll-behavior: auto;
  }
}

.gtt-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;

  th,
  td {
    padding: var(--space-1) var(--space-2);
    text-align: center;
    border-bottom: 1px solid var(--p-content-border-color);
  }

  // Values such as "±1° 30′" stay on one line; only the range headers wrap.
  td {
    white-space: nowrap;
  }

  // The header row stays in view while the body scrolls.
  thead th {
    position: sticky;
    top: 0;
    z-index: 1;
    background: var(--p-content-background);
    font-size: var(--font-size-xs);
    font-weight: 600;
    color: var(--p-text-muted-color);
    vertical-align: bottom;
  }

  th.gtt-class {
    text-align: left;
    white-space: nowrap;
  }
}

tbody .gtt-class {
  font-weight: 500;
}

.gtt-table--gridlines {
  th,
  td {
    border: 1px solid var(--p-content-border-color);
  }
}

// A light tint of the text colour, so the stripes read in light and dark mode.
.gtt-table--striped tbody tr:nth-child(even) {
  background: color-mix(in srgb, var(--p-text-color) 4%, transparent);
}

.gtt-col--active,
.gtt-table thead th.gtt-col--active {
  background: var(--p-content-hover-background);
}

// Hovered row, then the row of the current input, win over stripes and the
// column highlight. The current row takes the theme's selection colours, like
// a selected row of a data table, and a primary bar on its label so it still
// stands out where the selection tint is close to the stripes.
.gtt-table tbody tr:hover > * {
  background: var(--p-content-hover-background);
}

.gtt-table tbody tr.gtt-row--active,
.gtt-table tbody tr.gtt-row--active > * {
  background: var(--p-highlight-background);
}

.gtt-table tbody tr.gtt-row--active > th {
  color: var(--p-highlight-color);
  font-weight: 700;
  box-shadow: inset 3px 0 0 var(--p-primary-color);
}

.gtt-hit {
  font-weight: 700;
  color: var(--p-primary-color);
  outline: 2px solid var(--p-primary-color);
  outline-offset: -2px;
}
</style>
